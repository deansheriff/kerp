from contextlib import contextmanager
from uuid import uuid4

from app.models.auth import AuthProvider, UserCredential
from app.models.person import Person, PersonStatus
from app.services.auth_flow import hash_password
from scripts import seed_demo_tech_company


def test_demo_seed_attaches_admin_to_demo_org(db_session, monkeypatch):
    original_org_id = uuid4()
    demo_org_id = uuid4()
    email = f"demo-admin-{uuid4().hex}@example.com"
    username = f"demo-admin-{uuid4().hex}"
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

    monkeypatch.setattr(
        seed_demo_tech_company, "cross_org_session", fake_cross_org_session
    )
    monkeypatch.delenv("DEMO_ATTACH_ADMIN_TO_ORG", raising=False)
    monkeypatch.setenv("ADMIN_USERNAME", username)

    seed_demo_tech_company._attach_admin_to_demo_org(demo_org_id)

    db_session.refresh(person)
    assert person.organization_id == demo_org_id
    assert person.is_active is True
    assert person.status == PersonStatus.active
