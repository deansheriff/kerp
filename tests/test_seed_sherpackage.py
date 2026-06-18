from contextlib import contextmanager
from uuid import uuid4

from app.models.auth import AuthProvider, UserCredential
from app.models.person import Person, PersonStatus
from app.services.auth_flow import hash_password
from scripts import seed_sherpackage


def test_sherpackage_employee_seed_has_exactly_five_work_emails(monkeypatch):
    monkeypatch.delenv("SHERPACKAGE_WORK_EMAIL_DOMAIN", raising=False)

    emails = [
        seed_sherpackage._work_email(row["first_name"], row["last_name"])
        for row in seed_sherpackage.SHERPACKAGE_EMPLOYEES
    ]

    assert len(seed_sherpackage.SHERPACKAGE_EMPLOYEES) == 5
    assert len(set(emails)) == 5
    assert all(email.endswith("@sherpackageonline.com") for email in emails)


def test_sherpackage_seed_attaches_admin_to_sherpackage_org(db_session, monkeypatch):
    original_org_id = uuid4()
    sherpackage_org_id = uuid4()
    email = f"sherpackage-admin-{uuid4().hex}@example.com"
    username = f"sherpackage-admin-{uuid4().hex}"
    person = Person(
        organization_id=original_org_id,
        first_name="Admin",
        last_name="User",
        email=email,
        is_active=True,
        status=PersonStatus.active,
    )
    db_session.add(person)
    db_session.flush()
    db_session.add(
        UserCredential(
            person_id=person.id,
            provider=AuthProvider.local,
            username=username,
            password_hash=hash_password("admin123"),
            is_active=True,
        )
    )
    db_session.commit()

    @contextmanager
    def fake_cross_org_session():
        yield db_session

    monkeypatch.setattr(seed_sherpackage, "cross_org_session", fake_cross_org_session)
    monkeypatch.delenv("SHERPACKAGE_ATTACH_ADMIN_TO_ORG", raising=False)
    monkeypatch.setenv("ADMIN_USERNAME", username)

    seed_sherpackage._attach_admin_to_sherpackage_org(sherpackage_org_id)

    db_session.refresh(person)
    assert person.organization_id == sherpackage_org_id
    assert person.is_active is True
    assert person.status == PersonStatus.active
