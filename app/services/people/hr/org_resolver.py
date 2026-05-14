"""
Position-based organization resolver.

Centralizes manager and approval-chain resolution from the HR position tree.

Vacancy policy
--------------
Resolving "who is my manager?" through positions has four cases. The policy
this module implements is uniform across ``get_manager``, ``get_approval_chain``,
and ``get_direct_reports`` so callers get consistent answers:

1. Parent position has an active PRIMARY incumbent — return that employee.
2. Parent position has only ACTING/INTERIM incumbents — return the most
   recently appointed one (PRIMARY > ACTING > INTERIM via
   ``_assignment_type_priority``; ties broken by latest ``start_date``).
3. Parent position is vacant — walk one level further up the tree and try
   again. Routing therefore "rolls up" past empty seats to the first warm
   body. This is by design: approval flows should never silently drop on
   the floor because a seat is open.
4. Position chain has a gap (parent exists but has no current incumbent and
   so does each ancestor up to the root) — return ``None``. Callers must
   decide whether to block the action or surface to HR.

``get_direct_reports`` applies the mirror image of rule 3: it walks *down*
through vacant intermediate positions so a director still sees their indirect
reports when a middle-manager seat is empty.

Cycle protection: every walk maintains a ``visited_position_ids`` set so a
mis-configured tree (A reports to B reports to A) terminates cleanly rather
than looping forever.

The ``as_of`` parameter on every method enables historical resolution
("who was the manager on 2024-03-15?") for audit and replay scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from typing import Any

from sqlalchemy import case, select
from sqlalchemy.orm import Session, selectinload

from app.models.people.hr import (
    Employee,
    EmployeeStatus,
    Position,
    PositionAssignment,
    PositionAssignmentType,
    PositionVacancyRoutingPolicy,
)


@dataclass(frozen=True)
class VacancyRoutingAlert:
    """Vacant position crossed while resolving with NOTIFY_HR_THEN_SKIP."""

    organization_id: UUID
    position_id: UUID
    position_code: str
    position_name: str


class OrgResolver:
    """Resolve reporting relationships through positions and assignments."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._vacancy_routing_alerts: list[VacancyRoutingAlert] = []

    def get_manager(
        self,
        employee_id: UUID,
        organization_id: UUID,
        *,
        as_of: date | None = None,
    ) -> Employee | None:
        """Return the first active incumbent above the employee's position."""
        assignment = self.get_active_assignment(
            employee_id,
            organization_id,
            as_of=as_of,
        )
        if not assignment:
            return None

        position = assignment.position or self._get_position(
            assignment.position_id,
            organization_id,
        )
        if not position or not position.parent_position_id:
            return None

        return self._find_incumbent_up_tree(
            position.parent_position_id,
            organization_id,
            as_of=as_of,
            visited_position_ids={position.position_id},
        )

    def get_approval_chain(
        self,
        employee_id: UUID,
        organization_id: UUID,
        *,
        as_of: date | None = None,
    ) -> list[Employee]:
        """Return active incumbents up the position hierarchy to the root."""
        assignment = self.get_active_assignment(
            employee_id,
            organization_id,
            as_of=as_of,
        )
        if not assignment:
            return []

        position = assignment.position or self._get_position(
            assignment.position_id,
            organization_id,
        )
        if not position:
            return []

        chain: list[Employee] = []
        visited_position_ids = {position.position_id}
        next_position_id = position.parent_position_id

        while next_position_id and next_position_id not in visited_position_ids:
            visited_position_ids.add(next_position_id)
            position = self._get_position(next_position_id, organization_id)
            if not position:
                break

            incumbent = self.get_position_incumbent(
                position.position_id,
                organization_id,
                as_of=as_of,
            )
            if incumbent:
                chain.append(incumbent)

            if not self._handle_vacant_position(position, organization_id):
                break

            next_position_id = position.parent_position_id

        return chain

    def get_position_chain(
        self,
        employee_id: UUID,
        organization_id: UUID,
        *,
        as_of: date | None = None,
    ) -> list[tuple[Position, Employee | None]]:
        """
        Return the employee's position and each ancestor up the tree.

        The first tuple is the employee's own position (with themselves as
        incumbent if active). Each subsequent tuple is a parent position
        with its current incumbent (or ``None`` if the position is vacant).
        Vacant ancestor positions are still included in the returned list
        so the caller can render gaps — unlike ``get_approval_chain``
        which skips them.

        Returns an empty list if the employee has no active position
        assignment.
        """
        assignment = self.get_active_assignment(
            employee_id,
            organization_id,
            as_of=as_of,
        )
        if not assignment:
            return []

        position = assignment.position or self._get_position(
            assignment.position_id,
            organization_id,
        )
        if not position:
            return []

        chain: list[tuple[Position, Employee | None]] = []
        visited_position_ids: set[UUID] = set()
        current_position: Position | None = position

        while (
            current_position
            and current_position.position_id not in visited_position_ids
        ):
            visited_position_ids.add(current_position.position_id)
            incumbent = self.get_position_incumbent(
                current_position.position_id,
                organization_id,
                as_of=as_of,
            )
            chain.append((current_position, incumbent))

            parent_id = current_position.parent_position_id
            if not parent_id:
                break
            current_position = self._get_position(parent_id, organization_id)

        return chain

    def get_direct_reports(
        self,
        manager_employee_id: UUID,
        organization_id: UUID,
        *,
        as_of: date | None = None,
    ) -> list[Employee]:
        """
        Return employees who currently report to the manager through positions.

        If an intermediate child position is vacant, the search walks down that
        vacant branch until it finds the first active incumbents, matching the
        vacancy roll-up behavior used by get_manager().
        """
        manager_assignment = self.get_active_assignment(
            manager_employee_id,
            organization_id,
            as_of=as_of,
        )
        if not manager_assignment:
            return []

        manager_position = manager_assignment.position or self._get_position(
            manager_assignment.position_id,
            organization_id,
        )
        if not manager_position:
            return []

        reports: list[Employee] = []
        visited_position_ids = {manager_position.position_id}
        positions_to_check = self._get_child_positions(
            manager_position.position_id,
            organization_id,
        )

        while positions_to_check:
            position = positions_to_check.pop(0)
            if position.position_id in visited_position_ids:
                continue
            visited_position_ids.add(position.position_id)

            incumbent = self.get_position_incumbent(
                position.position_id,
                organization_id,
                as_of=as_of,
            )
            if incumbent:
                reports.append(incumbent)
                continue

            if not self._handle_vacant_position(position, organization_id):
                continue

            positions_to_check.extend(
                self._get_child_positions(position.position_id, organization_id)
            )

        return reports

    def get_active_assignment(
        self,
        employee_id: UUID,
        organization_id: UUID,
        *,
        as_of: date | None = None,
    ) -> PositionAssignment | None:
        """Return the employee's active position assignment."""
        as_of = as_of or date.today()
        stmt = (
            select(PositionAssignment)
            .options(selectinload(PositionAssignment.position))
            .where(
                PositionAssignment.organization_id == organization_id,
                PositionAssignment.employee_id == employee_id,
                PositionAssignment.start_date <= as_of,
                (
                    PositionAssignment.end_date.is_(None)
                    | (PositionAssignment.end_date >= as_of)
                ),
            )
            .order_by(
                self._assignment_type_priority(), PositionAssignment.start_date.desc()
            )
            .limit(1)
        )
        return self.db.scalar(stmt)

    def get_position_incumbent(
        self,
        position_id: UUID,
        organization_id: UUID,
        *,
        as_of: date | None = None,
    ) -> Employee | None:
        """Return the current active employee occupying a position."""
        as_of = as_of or date.today()
        stmt = (
            select(Employee)
            .join(
                PositionAssignment,
                PositionAssignment.employee_id == Employee.employee_id,
            )
            .where(
                Employee.organization_id == organization_id,
                Employee.status == EmployeeStatus.ACTIVE,
                PositionAssignment.organization_id == organization_id,
                PositionAssignment.position_id == position_id,
                PositionAssignment.start_date <= as_of,
                (
                    PositionAssignment.end_date.is_(None)
                    | (PositionAssignment.end_date >= as_of)
                ),
            )
            .options(selectinload(Employee.person), selectinload(Employee.grade))
            .order_by(
                self._assignment_type_priority(),
                PositionAssignment.start_date.desc(),
            )
            .limit(1)
        )
        return self.db.scalar(stmt)

    def _find_incumbent_up_tree(
        self,
        position_id: UUID,
        organization_id: UUID,
        *,
        as_of: date | None,
        visited_position_ids: set[UUID],
    ) -> Employee | None:
        next_position_id: UUID | None = position_id

        while next_position_id and next_position_id not in visited_position_ids:
            visited_position_ids.add(next_position_id)
            position = self._get_position(next_position_id, organization_id)
            if not position:
                return None

            incumbent = self.get_position_incumbent(
                position.position_id,
                organization_id,
                as_of=as_of,
            )
            if incumbent:
                return incumbent

            if not self._handle_vacant_position(position, organization_id):
                return None

            next_position_id = position.parent_position_id

        return None

    def drain_vacancy_routing_alerts(self) -> list[VacancyRoutingAlert]:
        """Return and clear accumulated NOTIFY_HR_THEN_SKIP vacancy events."""
        alerts = self._vacancy_routing_alerts
        self._vacancy_routing_alerts = []
        return alerts

    def notify_hr_for_vacancy_routing_alerts(
        self,
        organization_id: UUID,
        *,
        actor_id: UUID | None = None,
    ) -> int:
        """Create in-app HR alerts for accumulated vacancy routing events."""
        alerts = self.drain_vacancy_routing_alerts()
        if not alerts:
            return 0

        from app.models.notification import (
            EntityType,
            NotificationChannel,
            NotificationType,
        )
        from app.models.person import Person
        from app.models.rbac import PersonRole, Role
        from app.services.notification import NotificationService

        recipients = list(
            self.db.scalars(
                select(Person.id)
                .join(PersonRole, PersonRole.person_id == Person.id)
                .join(Role, Role.id == PersonRole.role_id)
                .where(
                    Person.organization_id == organization_id,
                    Person.is_active.is_(True),
                    Role.is_active.is_(True),
                    Role.name.in_(["hr_manager", "hr_director", "admin"]),
                )
                .distinct()
            ).all()
        )
        if not recipients:
            return 0

        unique_alerts = {alert.position_id: alert for alert in alerts}.values()
        notification_service = NotificationService()
        since = datetime.utcnow() - timedelta(hours=24)
        created_count = 0
        for alert in unique_alerts:
            for recipient_id in recipients:
                created = notification_service.create_if_not_sent_since(
                    self.db,
                    organization_id=organization_id,
                    recipient_id=recipient_id,
                    entity_type=EntityType.SYSTEM,
                    entity_id=alert.position_id,
                    notification_type=NotificationType.ALERT,
                    title="Vacant position used in approval routing",
                    message=(
                        f"Position {alert.position_code} - {alert.position_name} "
                        "is vacant and was skipped during approval routing."
                    ),
                    since=since,
                    channel=NotificationChannel.IN_APP,
                    action_url=f"/people/hr/positions/{alert.position_id}/edit",
                    actor_id=actor_id,
                )
                if created is not None:
                    created_count += 1
        return created_count

    def _handle_vacant_position(
        self,
        position: Position,
        organization_id: UUID,
    ) -> bool:
        policy = getattr(
            position,
            "vacancy_routing_policy",
            PositionVacancyRoutingPolicy.SKIP_UP,
        )
        if isinstance(policy, str):
            try:
                policy = PositionVacancyRoutingPolicy(policy)
            except ValueError:
                return True
        if policy == PositionVacancyRoutingPolicy.NOTIFY_HR_THEN_SKIP:
            self._vacancy_routing_alerts.append(
                VacancyRoutingAlert(
                    organization_id=organization_id,
                    position_id=position.position_id,
                    position_code=position.position_code,
                    position_name=position.position_name,
                )
            )
        return policy != PositionVacancyRoutingPolicy.BLOCK

    def _get_position(
        self,
        position_id: UUID,
        organization_id: UUID,
    ) -> Position | None:
        stmt = select(Position).where(
            Position.position_id == position_id,
            Position.organization_id == organization_id,
            Position.is_active.is_(True),
        )
        return self.db.scalar(stmt)

    def _get_child_positions(
        self,
        parent_position_id: UUID,
        organization_id: UUID,
    ) -> list[Position]:
        stmt = (
            select(Position)
            .where(
                Position.parent_position_id == parent_position_id,
                Position.organization_id == organization_id,
                Position.is_active.is_(True),
            )
            .order_by(Position.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    @staticmethod
    def _assignment_type_priority() -> Any:
        return case(
            (PositionAssignment.assignment_type == PositionAssignmentType.PRIMARY, 0),
            (PositionAssignment.assignment_type == PositionAssignmentType.ACTING, 1),
            (PositionAssignment.assignment_type == PositionAssignmentType.INTERIM, 2),
            else_=3,
        )
