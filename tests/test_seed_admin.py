import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.models.auth import AuthProvider, UserCredential
from app.models.person import Person, PersonStatus
from app.services.auth_flow import hash_password, verify_password
from scripts import seed_admin


def test_seed_admin_repairs_existing_credential_and_login(
    monkeypatch, engine, client
):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "admin123")
    monkeypatch.setenv(
        "BOOTSTRAP_ADMIN_ORGANIZATION_ID", str(seed_admin.DEFAULT_ORGANIZATION_ID)
    )

    seed_admin.main([], session_factory=Session)

    with Session() as db:
        credential = db.scalar(
            select(UserCredential)
            .where(UserCredential.provider == AuthProvider.local)
            .where(UserCredential.username == "admin")
        )
        assert credential is not None
        credential.password_hash = hash_password("stale-password")
        credential.failed_login_attempts = 5
        credential.is_active = False
        db.commit()

    seed_admin.main([], session_factory=Session)

    with Session() as db:
        credential = db.scalar(
            select(UserCredential)
            .where(UserCredential.provider == AuthProvider.local)
            .where(UserCredential.username == "admin")
        )
        assert credential is not None
        assert verify_password("admin123", credential.password_hash)
        assert credential.failed_login_attempts == 0
        assert credential.locked_until is None
        assert credential.is_active is True

    response = client.post(
        "/auth/admin-login",
        json={"username": "admin", "password": "admin123"},
    )

    assert response.status_code == 200
    assert response.json()["mfa_required"] is False


def test_seed_admin_reuses_existing_email_across_org(monkeypatch, engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    existing_org_id = uuid.uuid4()
    email = f"crossorg-admin-{uuid.uuid4().hex}@example.com"
    username = f"crossorg-admin-{uuid.uuid4().hex}"

    with Session() as db:
        db.info["organization_id"] = existing_org_id
        person = Person(
            organization_id=existing_org_id,
            first_name="Existing",
            last_name="Admin",
            email=email,
            email_verified=False,
            is_active=False,
            status=PersonStatus.inactive,
        )
        db.add(person)
        db.commit()
        existing_person_id = person.id

    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", email)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", username)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "admin123")
    monkeypatch.setenv(
        "BOOTSTRAP_ADMIN_ORGANIZATION_ID", str(seed_admin.DEFAULT_ORGANIZATION_ID)
    )

    seed_admin.main([], session_factory=Session)

    with Session() as db:
        people_count = db.scalar(
            select(func.count()).select_from(Person).where(Person.email == email)
        )
        credential = db.scalar(
            select(UserCredential)
            .where(UserCredential.provider == AuthProvider.local)
            .where(UserCredential.username == username)
        )
        person = db.get(Person, existing_person_id)

    assert people_count == 1
    assert credential is not None
    assert credential.person_id == existing_person_id
    assert person is not None
    assert person.email_verified is True
    assert person.is_active is True
    assert person.status == PersonStatus.active
