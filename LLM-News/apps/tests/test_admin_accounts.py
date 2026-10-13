import time

from app.core import admin_accounts
from app.core import admin_auth
from app.core.database import connect


def test_named_account_password_mfa_session_and_reset(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    secret = admin_accounts.new_totp_secret()
    now = int(time.time())
    code = admin_accounts._totp(secret, now // 30)
    user_id = admin_accounts.create_user("Editor.One", "a-long-test-password", "editor", secret)
    assert user_id > 0
    assert admin_accounts.login("editor.one", "wrong-password", code) is None
    assert admin_accounts.login("editor.one", "a-long-test-password", "000000") is None
    with connect("admin") as database:
        assert database.execute("SELECT COUNT(*) AS count FROM admin_audit WHERE action='login_failed'").fetchone()["count"] == 2

    token, identity = admin_accounts.login("editor.one", "a-long-test-password", code)
    assert identity == {"id": user_id, "username": "editor.one", "role": "editor", "mfa_enabled": True}
    assert admin_accounts.session_user(token)["role"] == "editor"
    admin_accounts.logout(token)
    assert admin_accounts.session_user(token) is None

    admin_accounts.reset_password("editor.one", "another-long-password")
    new_code = admin_accounts._totp(secret, int(time.time()) // 30)
    assert admin_accounts.login("editor.one", "a-long-test-password", new_code) is None
    assert admin_accounts.login("editor.one", "another-long-password", new_code)


def test_password_hash_uses_unique_salts():
    first = admin_accounts.hash_password("same-secure-password")
    second = admin_accounts.hash_password("same-secure-password")
    assert first != second
    assert admin_accounts.verify_password("same-secure-password", first)
    assert not admin_accounts.verify_password("different-password", first)


def test_named_accounts_disable_the_shared_bootstrap_token(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("ADMIN_TOKEN", "a-secure-bootstrap-token-that-is-long")
    admin_accounts.create_user("owner", "a-long-owner-password", "owner", admin_accounts.new_totp_secret())
    assert admin_accounts.owner_mfa_ready()
    assert not admin_auth.valid_password("a-secure-bootstrap-token-that-is-long")
    monkeypatch.setenv("ALLOW_LEGACY_ADMIN_TOKEN", "true")
    assert admin_auth.valid_password("a-secure-bootstrap-token-that-is-long")
