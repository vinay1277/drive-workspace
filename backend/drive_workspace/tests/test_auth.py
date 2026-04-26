"""Unit tests for FileAuthenticator. No real Google API contact."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from drive_workspace.auth import SCOPES, FileAuthenticator

# Minimally-shaped service-account key payload. Just enough JSON for our path
# and shape assertions; the actual credential build is mocked, so the
# private_key value is never parsed.
_FAKE_SA_KEY: dict[str, str] = {
    "type": "service_account",
    "project_id": "fake-project",
    "private_key_id": "fakekeyid",
    "private_key": "-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----\n",
    "client_email": "fake-sa@fake-project.iam.gserviceaccount.com",
    "client_id": "000000000000000000000",
    "token_uri": "https://oauth2.googleapis.com/token",
}


@pytest.fixture
def fake_sa_key_file(tmp_path: Path) -> Path:
    p = tmp_path / "sa.json"
    p.write_text(json.dumps(_FAKE_SA_KEY))
    return p


def test_scopes_include_drive_and_sheets() -> None:
    assert "https://www.googleapis.com/auth/drive" in SCOPES
    assert "https://www.googleapis.com/auth/spreadsheets" in SCOPES


def test_resolves_path_at_construction(fake_sa_key_file: Path) -> None:
    auth = FileAuthenticator(fake_sa_key_file)
    assert auth.key_path == fake_sa_key_file.resolve()


def test_accepts_str_path(fake_sa_key_file: Path) -> None:
    auth = FileAuthenticator(str(fake_sa_key_file))
    assert auth.key_path == fake_sa_key_file.resolve()


def test_missing_file_raises_at_construction(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    with pytest.raises(FileNotFoundError):
        FileAuthenticator(missing)


def test_credential_delegates_to_google_auth_with_scopes(
    fake_sa_key_file: Path,
) -> None:
    sentinel = object()
    with patch(
        "drive_workspace.auth.Credentials.from_service_account_file",
        return_value=sentinel,
    ) as mocked:
        auth = FileAuthenticator(fake_sa_key_file)
        result = auth.credential()

    assert result is sentinel
    mocked.assert_called_once()
    call = mocked.call_args
    # First positional arg is the path; scopes are kwarg.
    assert call.args[0] == str(fake_sa_key_file.resolve())
    assert call.kwargs["scopes"] == list(SCOPES)


def test_authenticator_protocol_compatibility(fake_sa_key_file: Path) -> None:
    """FileAuthenticator must satisfy the structural Authenticator Protocol."""
    from drive_workspace.workspace import Authenticator

    auth: Authenticator = FileAuthenticator(fake_sa_key_file)
    with patch(
        "drive_workspace.auth.Credentials.from_service_account_file",
        return_value=object(),
    ):
        assert auth.credential() is not None
