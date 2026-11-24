import importlib.util
from pathlib import Path

import pytest
from dotenv import dotenv_values

path = Path(__file__).resolve().parents[2] / "scripts" / "configure_reset_email.py"
spec = importlib.util.spec_from_file_location("reset_email_setup", path)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

KEY = "re_synthetic_test_key_not_for_external_use"


def test_setup_preserves_existing_secrets_database_and_comments(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text(
        "# Keep existing settings\nSECRET_KEY=synthetic-existing-key\nDATABASE_URL=sqlite:///existing.db\nPASSWORD_RESET_DELIVERY=local\n",
        encoding="utf-8",
    )
    values = setup.email_settings(KEY, "sender@example.com", "http://localhost:3000")
    setup.save_settings(env, values)
    result = dotenv_values(env)
    assert result["SECRET_KEY"] == "synthetic-existing-key"
    assert result["DATABASE_URL"] == "sqlite:///existing.db"
    assert result["PASSWORD_RESET_DELIVERY"] == "resend"
    assert result["RESEND_API_KEY"] == KEY
    assert result["PASSWORD_RESET_FROM_EMAIL"] == "sender@example.com"
    assert result["PASSWORD_RESET_BASE_URL"] == "http://localhost:3000"
    assert env.read_text(encoding="utf-8").startswith("# Keep existing settings")
    assert KEY not in capsys.readouterr().out
    assert not list(tmp_path.glob("*.tmp"))


def test_setup_replaces_duplicate_mail_settings(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "RESEND_API_KEY=old\nexport RESEND_API_KEY=duplicate\nPASSWORD_RESET_DELIVERY=local\n",
        encoding="utf-8",
    )
    setup.save_settings(env, setup.email_settings(KEY, "onboarding@resend.dev", "http://localhost:3000/"))
    assert env.read_text(encoding="utf-8").count("RESEND_API_KEY=") == 1
    assert dotenv_values(env)["RESEND_API_KEY"] == KEY


@pytest.mark.parametrize("key", ["", "YOUR_KEY", "re_short", "re_bad\nnew_setting=value"])
def test_setup_rejects_missing_or_malformed_keys_without_echoing_them(key):
    with pytest.raises(ValueError) as failure:
        setup.email_settings(key, "sender@example.com", "http://localhost:3000")
    assert not key or key not in str(failure.value)


@pytest.mark.parametrize(
    "origin",
    [
        "https://user:pass@example.com",
        "https://example.com/path",
        "https://example.com/#token",
        "file:///tmp/app",
    ],
)
def test_setup_rejects_non_origin_frontend_addresses(origin):
    with pytest.raises(ValueError):
        setup.email_settings(KEY, "sender@example.com", origin)


def test_setup_refuses_to_create_or_overwrite_an_unexpected_file(tmp_path):
    with pytest.raises(ValueError):
        setup.save_settings(
            tmp_path / ".env", setup.email_settings(KEY, "sender@example.com", "http://localhost:3000")
        )
