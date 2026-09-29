"""A previously admitted command loses execution authority when its writer does."""

from datetime import datetime, timezone

import pytest
from test_pulumi_command_preflight import fixture_data, preflight


@pytest.mark.parametrize("permission", ["write", "maintain", "admin", "read", "none"])
def test_current_requester_permission_is_checked_after_initial_admission(
    monkeypatch, permission
):
    request, origin = fixture_data()
    origin["now"] = datetime(2027, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(preflight, "collect_intake_evidence", lambda value: origin)
    calls = []

    def gh(path):
        calls.append(path)
        return {"permission": permission}

    monkeypatch.setattr(preflight, "gh", gh)
    if permission in {"read", "none"}:
        with pytest.raises(ValueError, match="revoked"):
            preflight.revalidate_requester(request)
    else:
        preflight.revalidate_requester(request)
    assert calls == ["repos/org/repo/collaborators/dmytrocraft/permission"]
    # The same old request still cannot enter initial admission again.
    with pytest.raises(ValueError, match="Expired command"):
        preflight.validate_request(request, origin, governance=True)


@pytest.mark.parametrize("change", ["edit", "actor", "artifact", "foreign-comment"])
def test_revalidation_retains_immutable_comment_origin(monkeypatch, change):
    request, origin = fixture_data()
    if change == "edit":
        origin["comment"]["updated_at"] = "2026-09-05T12:02:00Z"
    elif change == "actor":
        origin["comment"]["user"]["id"] = 99
    elif change == "artifact":
        origin["artifact"]["head_sha"] = "f" * 40
    else:
        origin["comment"]["issue_url"] += "9"
    monkeypatch.setattr(preflight, "collect_intake_evidence", lambda value: origin)

    def forbidden(_):
        raise AssertionError("Origin must be authenticated before authorizing a login")

    monkeypatch.setattr(preflight, "gh", forbidden)
    with pytest.raises(ValueError):
        preflight.revalidate_requester(request)


@pytest.mark.parametrize("action", ["plan", "up"])
def test_requester_recheck_preserves_apply_separation(monkeypatch, action):
    request, origin = fixture_data(action=action)
    origin["comment"]["user"]["login"] = "Kravalg"
    monkeypatch.setattr(preflight, "collect_intake_evidence", lambda value: origin)
    monkeypatch.setattr(preflight, "gh", lambda _: {"permission": "admin"})
    if action == "up":
        with pytest.raises(ValueError, match="sole approver"):
            preflight.revalidate_requester(request)
    else:
        preflight.revalidate_requester(request)
