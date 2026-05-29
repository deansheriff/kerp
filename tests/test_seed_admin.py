from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models.auth import AuthProvider, UserCredential
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
