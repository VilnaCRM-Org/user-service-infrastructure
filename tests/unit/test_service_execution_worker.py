"""Closed worker routing and fresh admission checks with simulated APIs."""

import json
import os
import re
import secrets
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import service_execution_worker as worker  # noqa: E402


@pytest.fixture(autouse=True)
def public(monkeypatch, tmp_path):
    """Stand in for the host's ``/public`` bind mount."""
    directory = tmp_path / "public"
    directory.mkdir()
    monkeypatch.setattr(worker, "PUBLIC", directory, raising=False)
    return directory


FRESH_MARKER = secrets.token_hex


@pytest.fixture(autouse=True)
def marker(monkeypatch):
    """Pin the per-run stop-commands marker so stderr oracles stay literal."""
    monkeypatch.setattr("secrets.token_hex", lambda _: MARKER)


@pytest.fixture
def authority(monkeypatch):
    calls = []
    request = {
        "head_sha": "a" * 40,
        "pull_request_number": "19",
        "command": "up",
        "target_environment": "test",
    }
    monkeypatch.setenv("EXPECTED_BASE_SHA", "b" * 40)
    monkeypatch.setattr(
        worker.registry.artifact, "_context", lambda _: ("123", "b" * 40)
    )
    monkeypatch.setattr(
        worker.registry.artifact, "_producer", lambda *_: calls.append("producer")
    )
    monkeypatch.setattr(
        worker.registry, "_verify_checkout", lambda *_: calls.append("checkout")
    )
    monkeypatch.setattr(worker.registry.preflight, "read_request", lambda: request)
    monkeypatch.setattr(
        worker.registry.preflight,
        "revalidate_requester",
        lambda _: calls.append("requester"),
    )
    monkeypatch.setattr(
        worker.registry,
        "verify_reviewed_source",
        lambda *_a, **_k: calls.append("review"),
    )
    return request, calls


def test_native_authority_reused_before_execution(authority):
    _, calls = authority
    assert worker.admit("test_apply") == "a" * 40
    assert calls == ["producer", "checkout", "requester", "review"]
    with pytest.raises(ValueError, match="worker-job"):
        worker.admit("scheduled_prod_drift")


@pytest.mark.parametrize("fault", ["base", "account", "command"])
def test_changed_authority_fails(authority, monkeypatch, fault):
    request, _ = authority
    if fault == "base":
        monkeypatch.setenv("EXPECTED_BASE_SHA", "c" * 40)
    elif fault == "account":
        request["target_environment"] = "prod"
    else:
        request["command"] = "plan"
    with pytest.raises(ValueError):
        worker.admit("test_apply")


def coordinates(monkeypatch, account):
    monkeypatch.setenv("AWS_ACCOUNT_ID", worker.ACCOUNTS[account])
    monkeypatch.setenv("AWS_REGION", "eu-central-1")
    monkeypatch.setenv(
        "PULUMI_BACKEND_URL", f"s3://pulumi-user-service-infrastructure-{account}-state"
    )
    monkeypatch.setenv(
        "PULUMI_SECRETS_PROVIDER",
        f"awskms://alias/pulumi-user-service-infrastructure-{account}-secrets?region=eu-central-1",
    )


@pytest.mark.parametrize("job", tuple(worker.JOBS))
def test_every_route_preserves_checks_and_exports_only_plan(monkeypatch, tmp_path, job):
    account, command = worker.JOBS[job]
    coordinates(monkeypatch, account)
    monkeypatch.setenv("GITHUB_JOB", job)
    for key in (
        *worker.SESSION_KEYS,
        "POC_SOURCE_ARTIFACT_ID",
        "POC_SOURCE_ARCHIVE_SHA256",
        "POC_SOURCE_SHA256",
    ):
        monkeypatch.setenv(key, "synthetic")
    calls = []
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    monkeypatch.setattr(
        worker.registry.artifact,
        "load_verified_contract",
        lambda **_: (
            {
                "source": {"head_sha": "a" * 40, "base_sha": "b" * 40},
                "request": {"target_environment": "test"},
            },
            {"phase": "registry"},
        ),
    )
    monkeypatch.setattr(worker.registry, "_review", lambda _: None)
    monkeypatch.setattr(worker, "admit", lambda _: calls.append("admit") or "a" * 40)

    class Port:
        def __init__(self, area, **kwargs):
            assert calls == ["admit"]
            assert set(kwargs["session"]) == set(worker.SESSION_KEYS)
            self.repo = area
            self.before_program = kwargs["before_program"]
            calls.append("port")

    def execute(*_a, transport=None, **_k):
        calls.append("execute")
        transport.before_program()
        return 0

    monkeypatch.setattr(worker, "ServiceTransport", Port)
    monkeypatch.setattr(worker.registry, "execute", execute)
    monkeypatch.setattr(worker, "_replay_inputs", lambda *_: calls.append("replay"))
    copied = []
    monkeypatch.setattr(worker, "copy_tree", lambda *args: copied.append(args))
    worker.execute(job, tmp_path)
    assert calls[-3:] == ["execute", "admit", "admit"]
    assert ("replay" in calls) == (command == "up-plan")
    assert len(copied) == (2 if command == "plan" else 0)
    assert all(target.parent == Path("/public") for _, target in copied)


def test_workload_branch_routes_saved_plan_and_rejects_drift(monkeypatch):
    for key in (
        "POC_SOURCE_ARTIFACT_ID",
        "POC_SOURCE_ARCHIVE_SHA256",
        "POC_SOURCE_SHA256",
    ):
        monkeypatch.setenv(key, "synthetic")
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    source = {
        "source": {"head_sha": "a" * 40, "base_sha": "b" * 40},
        "request": {"target_environment": "test"},
    }
    contract = {"phase": "workload"}
    calls = []
    monkeypatch.setattr(
        worker.registry.artifact,
        "load_verified_contract",
        lambda **_: (source, contract),
    )
    monkeypatch.setattr(worker.registry, "_review", lambda _: calls.append("review"))
    monkeypatch.setattr(
        worker.registry,
        "execute",
        lambda *_a, **_k: pytest.fail("registry execution after workload admission"),
    )
    monkeypatch.setattr(
        worker.workload,
        "execute",
        lambda command, **kwargs: calls.append((command, kwargs["transport"])) or 0,
    )
    assert worker._test(None, "plan", "a" * 40) == 0
    assert worker._test(None, "up-plan", "a" * 40) == 0
    with pytest.raises(ValueError, match="workload-drift-not-enabled"):
        worker._test(None, "drift", "a" * 40)
    assert calls == ["review", ("plan", None), "review", ("up-plan", None), "review"]
    source["source"]["head_sha"] = "c" * 40
    with pytest.raises(ValueError, match="workload-source-binding"):
        worker._test(None, "plan", "a" * 40)


def test_failure_and_changed_final_head_cannot_publish(monkeypatch, tmp_path):
    coordinates(monkeypatch, "test")
    monkeypatch.setenv("GITHUB_JOB", "test_preview")
    monkeypatch.setattr(
        worker, "ServiceTransport", lambda *_, **__: SimpleNamespace(repo=tmp_path)
    )
    monkeypatch.setattr(worker, "admit", lambda _: "a" * 40)
    monkeypatch.setattr(worker, "_test", lambda *_: 1)
    monkeypatch.setattr(
        worker, "copy_tree", lambda *_: pytest.fail("exported failed plan")
    )
    with pytest.raises(ValueError, match="worker-execution"):
        worker.execute("test_preview", tmp_path)
    monkeypatch.setattr(worker, "_test", lambda *_: 0)
    heads = iter(("a" * 40, "b" * 40))
    monkeypatch.setattr(worker, "admit", lambda _: next(heads))
    with pytest.raises(ValueError, match="worker-final-admission"):
        worker.execute("test_preview", tmp_path)
    with pytest.raises(ValueError, match="worker-job"):
        worker.execute("foreign", tmp_path)
    monkeypatch.setenv("AWS_ACCOUNT_ID", "000000000000")
    with pytest.raises(ValueError, match="worker-coordinates"):
        worker._coordinates("test")


@pytest.mark.parametrize("account", ["test"])
def test_replay_copy_preserves_legacy_input_paths(monkeypatch, tmp_path, account):
    copied = []
    monkeypatch.setattr(worker, "copy_tree", lambda *args: copied.append(args))
    worker._replay_inputs(SimpleNamespace(repo=tmp_path), account)
    source = Path("/trusted" if account == "test" else "/source") / ".artifacts"
    assert copied == [
        (source / name, tmp_path / ".artifacts" / name)
        for name in ("pulumi-plan", "pulumi-preview")
    ]


@pytest.mark.parametrize("success", [True, False])
def test_entrypoint_redacts_private_output(monkeypatch, capsys, success):
    monkeypatch.setattr(worker.os, "geteuid", lambda: 0)
    monkeypatch.setattr(worker.os, "getpid", lambda: 1)
    monkeypatch.setenv("PATH", "/opt/pulumi:/usr/local/bin:/usr/bin:/bin")

    def execute(job, area):
        assert job == "test_preview"
        assert (area / "private.log").stat().st_mode & 0o777 == 0o600
        assert Path(os.environ["HOME"]).stat().st_mode & 0o777 == 0o700
        print("synthetic-private-payload")
        print("synthetic-private-error", file=sys.stderr)
        if not success:
            raise ValueError("synthetic-private-exception")

    monkeypatch.setattr(worker, "execute", execute)
    assert worker.main(["test_preview"]) == (0 if success else 1)
    captured = capsys.readouterr()
    assert "synthetic-private" not in captured.out + captured.err
    monkeypatch.setattr(worker.os, "getpid", lambda: 2)
    assert worker.main(["test_preview"]) == 1


def test_failure_reports_fixed_stage_without_private_data(monkeypatch, capfd):
    monkeypatch.setattr(worker.os, "geteuid", lambda: 0)
    monkeypatch.setattr(worker.os, "getpid", lambda: 1)
    monkeypatch.setenv("PATH", "/opt/pulumi:/usr/local/bin:/usr/bin:/bin")
    monkeypatch.setenv("GITHUB_JOB", "test_preview")
    monkeypatch.setenv("AWS_ACCOUNT_ID", "synthetic-private-account")
    monkeypatch.setattr(worker, "admit", lambda *_: "a" * 40)
    assert worker.main(["test_preview"]) == 1
    captured = capfd.readouterr()
    assert "Trusted worker stage: account coordinates" in captured.err
    assert "synthetic-private-account" not in captured.out + captured.err


# FR-20 / NFR-01 operator diagnostics. Oracles are literal PRD-shaped values:
# a failing ECS service create with the AWS SDK v2 error text Pulumi reports.
WEB_URN = (
    "urn:pulumi:test::user-service-infrastructure::"
    "aws:ecs/service:Service::user-service-web-service"
)
WEB_TYPE = "aws:ecs/service:Service"
FAKE_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
FAKE_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
FAILED = "Service execution failed its trusted prerequisites."
MARKER = "5f3c9a1e7b2d4c6f8a0e1b3d5c7f9a2e"
# Workflow commands are off between these lines (FR-20 / F-02 job-log safety).
START = "::stop-commands::5f3c9a1e7b2d4c6f8a0e1b3d5c7f9a2e\n"
END = "::5f3c9a1e7b2d4c6f8a0e1b3d5c7f9a2e::\n"


def step(kind, urn=WEB_URN, op="create", resource_type=WEB_TYPE):
    return {kind: {"metadata": {"op": op, "urn": urn, "type": resource_type}}}


def error(message, urn=WEB_URN, severity="error"):
    return {"diagnosticEvent": {"urn": urn, "severity": severity, "message": message}}


def aws_message(code, text):
    return (
        "<{%reset%}>creating ECS Service (user-service-web-service): operation "
        "error ECS: CreateService, https response error StatusCode: 400, "
        f"RequestID: 0f1e2d3c, {code}: {text}<{{%reset%}}>\n"
    )


def failing_main(monkeypatch, events, *, private=""):
    monkeypatch.setattr(worker.os, "geteuid", lambda: 0)
    monkeypatch.setattr(worker.os, "getpid", lambda: 1)
    monkeypatch.setenv("PATH", "/opt/pulumi:/usr/local/bin:/usr/bin:/bin")

    def execute(job, area):
        outputs = area / "outputs"
        outputs.mkdir()
        for name, lines in events.items():
            (outputs / name).write_text(
                "\n".join(
                    line if isinstance(line, str) else json.dumps(line)
                    for line in lines
                )
            )
        print(private)
        raise ValueError("synthetic-private-exception")

    monkeypatch.setattr(worker, "execute", execute)
    assert worker.main(["test_preview"]) == 1


def test_failure_summary_has_only_allow_listed_fields(monkeypatch, capsys):
    """FR-20 P: URN, type, operation, AWS error code and message, nothing else."""
    failing_main(
        monkeypatch,
        {
            "events-0001.jsonl": [
                step("resourcePreEvent"),
                {"stdoutEvent": {"message": "private engine stdout"}},
                error("private info detail", severity="info"),
                error(
                    aws_message(
                        "InvalidParameterException",
                        "The container web does not exist in the task definition.",
                    )
                ),
                step("resOpFailedEvent"),
            ]
        },
    )
    assert capsys.readouterr().err == (
        "::stop-commands::5f3c9a1e7b2d4c6f8a0e1b3d5c7f9a2e\n"
        "Operator diagnostics (allow-listed fields only):\n"
        "- urn: urn:pulumi:test::user-service-infrastructure::"
        "aws:ecs/service:Service::user-service-web-service\n"
        "  type: aws:ecs/service:Service\n"
        "  operation: create\n"
        "  aws_error_code: InvalidParameterException\n"
        "  aws_error_message: The container web does not exist in the task "
        "definition.\n"
        "::5f3c9a1e7b2d4c6f8a0e1b3d5c7f9a2e::\n"
        "Service execution failed its trusted prerequisites.\n"
    )


def test_failure_summary_drops_secret_like_values(monkeypatch, capsys):
    """FR-20 N and NFR-01 N: seeded fake secrets never reach the summary."""
    monkeypatch.setenv("AWS_SESSION_TOKEN", "synthetic-session-token-value")
    failing_main(
        monkeypatch,
        {
            "events-0001.jsonl": [
                error(f"secret detail {FAKE_SECRET}", severity="warning"),
                {"stdoutEvent": {"message": f"DB_PASSWORD={FAKE_SECRET}"}},
                error(
                    aws_message(
                        "AccessDeniedException",
                        f"key {FAKE_KEY_ID} secret {FAKE_SECRET} password=hunter2xyz "
                        "session synthetic-session-token-value denied",
                    )
                ),
                step("resOpFailedEvent"),
            ]
        },
        private=f"private.log line {FAKE_SECRET}",
    )
    output = capsys.readouterr()
    assert FAKE_SECRET not in output.out + output.err
    assert "hunter2xyz" not in output.err
    assert "synthetic-session-token-value" not in output.err
    assert "private.log line" not in output.out + output.err
    assert (
        "  aws_error_code: AccessDeniedException\n"
        "  aws_error_message: key [redacted] secret [redacted] password=[redacted] "
        "session [redacted] denied\n"
    ) in output.err


def test_truncated_summary_is_marked_and_still_redacted(monkeypatch, capsys):
    """FR-20 B and NFR-01 B: a field cut at 300 characters keeps no secret part."""
    words = "word " * 58
    failing_main(
        monkeypatch,
        {
            "events-0001.jsonl": [
                error(
                    aws_message("ValidationException", words + FAKE_SECRET + " tail")
                ),
                step("resOpFailedEvent"),
            ]
        },
    )
    err = capsys.readouterr().err
    assert (
        "  aws_error_message: "
        + words
        + "[redacted][truncated]\n"
        + END
        + FAILED
        + "\n"
    ) in err
    assert FAKE_SECRET[:8] not in err


def test_failure_count_and_event_log_size_are_bounded(monkeypatch, capsys):
    """FR-20 B: more than ten failures or an oversized log end with a marker."""
    urns = [f"{WEB_URN}-{index:02d}" for index in range(12)]
    failing_main(
        monkeypatch,
        {
            "events-0001.jsonl": [step("resOpFailedEvent", urn=urn) for urn in urns],
            "events-0002.jsonl": ["x" * (9 * 1024 * 1024)],
        },
    )
    err = capsys.readouterr().err
    assert err.count("- urn: ") == 10
    assert f"- urn: {WEB_URN}-09\n" in err
    assert f"{WEB_URN}-10" not in err
    assert err.endswith("[truncated]\n" + END + FAILED + "\n")


def test_unrecognised_event_fields_are_withheld(monkeypatch, capsys):
    """FR-20 N: values outside the allow-list shapes are replaced, never echoed."""
    failing_main(
        monkeypatch,
        {
            "events-0001.jsonl": [
                "not json",
                "[1, 2]",
                {"resourcePreEvent": "flat"},
                {"resourcePreEvent": {"metadata": {"urn": 7}}},
                error("missing urn", urn=None),
                step(
                    "resOpFailedEvent",
                    urn=f"urn:pulumi:test::p::t::name with {FAKE_SECRET}",
                    op="exfiltrate",
                    resource_type=f"type {FAKE_SECRET}",
                ),
                error(f"plain engine failure {FAKE_SECRET}"),
            ],
        },
    )
    err = capsys.readouterr().err
    assert err == (
        START + "Operator diagnostics (allow-listed fields only):\n"
        "- urn: [redacted]\n"
        "  type: unknown\n"
        "  operation: unknown\n"
        "- urn: urn:pulumi:test::user-service-infrastructure::"
        "aws:ecs/service:Service::user-service-web-service\n"
        "  type: unknown\n"
        "  operation: unknown\n" + END + "Service execution failed its trusted "
        "prerequisites.\n"
    )


def test_untrusted_event_log_paths_are_not_followed(tmp_path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    target = tmp_path / "target.jsonl"
    target.write_text(json.dumps(step("resOpFailedEvent")))
    (outputs / "events-0001.jsonl").symlink_to(target)
    (outputs / "events-0002.jsonl").mkdir()
    assert worker.diagnostics(tmp_path) == []
    assert worker.diagnostics(tmp_path / "absent") == []


def test_short_session_values_are_not_used_as_patterns(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "a")
    assert worker.redact("a plain message") == "a plain message"


def test_report_never_masks_the_failure(monkeypatch, capsys, tmp_path):
    def broken(_):
        raise RuntimeError("synthetic-private-diagnostics")

    monkeypatch.setattr(worker, "diagnostics", broken)
    worker._report(tmp_path)
    assert capsys.readouterr().err == ""


SUMMARY = (
    "Operator diagnostics (allow-listed fields only):\n"
    "- urn: urn:pulumi:test::user-service-infrastructure::"
    "aws:ecs/service:Service::user-service-web-service\n"
    "  type: aws:ecs/service:Service\n"
    "  operation: create\n"
    "  aws_error_code: InvalidParameterException\n"
    "  aws_error_message: The container web does not exist in the task "
    "definition.\n"
)


def web_failure():
    return [
        step("resourcePreEvent"),
        error(
            aws_message(
                "InvalidParameterException",
                "The container web does not exist in the task definition.",
            )
        ),
        step("resOpFailedEvent"),
    ]


def message_line(monkeypatch, public, raw):
    """Run one failing AWS error message through the worker; return its line."""
    events = {
        "events-0001.jsonl": [
            step("resourcePreEvent"),
            error(aws_message("AccessDenied", raw)),
            step("resOpFailedEvent"),
        ]
    }
    failing_main(monkeypatch, events)
    lines = (public / "operator-diagnostics.txt").read_text().splitlines()
    return lines[-1]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("DB_PASSWORD=hunter2xyz", "DB_PASSWORD=[redacted]"),
        (
            "APP_SECRET=aaaaaaaabbbbbbbbccccccccdddddddd",
            "APP_SECRET=[redacted]",
        ),
        ("client_secret=abc123def", "client_secret=[redacted]"),
        ("access_token=abc123def", "access_token=[redacted]"),
        ('{"password":"hunter2xyz"}', '{"password":"[redacted]"}'),
        ('"password": "hunter two"', '"password": "[redacted]"'),
        ("Authorization: Basic dXNlcjpodW50ZXIy", "Authorization: [redacted]"),
        ("Authorization: Bearer opaque-abc123", "Authorization: [redacted]"),
        ("sent Bearer opaque-abc123 header", "sent Bearer [redacted] header"),
        (
            "mongodb://admin:hunter2xyz@docdb.example:27017/users",
            "mongodb://[redacted]@docdb.example:27017/users",
        ),
        ("redis://:authtok3n@host:6379", "redis://[redacted]@host:6379"),
        ("key deadbeefdeadbeefdeadbeefdeadbeef end", "key [redacted] end"),
        ("key q8Zr2Lm4Xw7Tn1Vb6Kd9Hs3Fj5Pa0Gc2 end", "key [redacted] end"),
        ("key q8Zr2Lm4Xw7Tn1Vb-Kd9Hs3Fj5Pa0Gc_ end", "key [redacted] end"),
        ("key ghs_16C7e42F292c6912E7710c838 end", "key [redacted] end"),
        # R3-F1: long tokens, also beside a URL path or a lower-case segment.
        (
            "GET https://example.com/api/q8Zr2Lm4Xw7Tn1Vb-Kd9Hs3Fj5Pa0Gc_ failed",
            "GET [redacted] failed",
        ),
        ("key ab-Zr2Lm4Xw7Tn1VbKd9Hs3Fj5Pa0Gc1 end", "key [redacted] end"),
        ("q8Zr2Lm4Xw7Tn1Vb-kd-Hs3Fj5Pa0Gc_", "[redacted]"),
        ("key Zr2Lm4Xw7Tn1VbKd9Hs3 end", "key [redacted] end"),
        (
            "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
            "q8Zr2Lm4Xw7Tn1VbKd9Hs3Fj5Pa0Gc1",
            "arn:aws:secretsmanager:eu-central-1:891377212104:secret:[redacted]",
        ),
        (
            "arn:aws:s3:::bucket/k+Zr2Lm4XW7TN1VBKD9HS3",
            "arn:aws:s3:::bucket/[redacted]",
        ),
    ],
)
def test_common_credential_shapes_are_redacted(monkeypatch, public, raw, expected):
    """NFR-01 N: identifier, quoted, header, URL, short-key and long-token shapes."""
    assert message_line(monkeypatch, public, raw) == "  aws_error_message: " + expected


@pytest.mark.parametrize(
    "kept",
    [
        "arn:aws:iam::891377212104:role/x",
        "urn:pulumi:test::user-service-infrastructure::"
        "aws:ecs/service:Service::user-service-web-service",
        "user-service-infrastructure-test-web-service-01",
        "RequestID: 3f9a1b2c-4d5e-6f70-8192-a3b4c5d6e7f8",
        "User: arn:aws:sts::891377212104:assumed-role/"
        "GitHubCiApply-user-service-infrastructure-test/"
        "gha-pr-test-apply-12345678901 is not authorized to perform: "
        "secretsmanager:GetSecretValue on resource: "
        "arn:aws:secretsmanager:eu-central-1:891377212104:secret:"
        "user-service-test-app-secret-AbC1dE",
        "InvalidParameterException at docdb.example:27017/users",
    ],
)
def test_resource_identifiers_survive_redaction(monkeypatch, public, kept):
    """FR-20 P: ARNs, URNs, IAM actions and hyphenated names stay readable."""
    assert message_line(monkeypatch, public, kept) == "  aws_error_message: " + kept


@pytest.mark.parametrize(
    "kept",
    ["aws:secretsmanager/secret:Secret", "user-service-test-app-secret-AbC1dE"],
)
def test_types_and_names_outside_messages_survive_redaction(kept):
    """FR-20 P: the long-token rule applies to AWS error messages only."""
    assert worker.redact(kept) == kept


def test_legacy_workflow_commands_are_neutralised(monkeypatch, capsys, public):
    """FR-20 N (R3-F2): no ``##[`` survives, and commands stop inside the block."""
    line = message_line(monkeypatch, public, "a ##[error]forged ##[add-mask]b")
    assert line == "  aws_error_message: a # #[error]forged # #[add-mask]b"
    err = capsys.readouterr().err
    assert "##[" not in err
    assert err.startswith("::stop-commands::5f3c9a1e7b2d4c6f8a0e1b3d5c7f9a2e\n")
    assert err.endswith(
        "a # #[error]forged # #[add-mask]b\n"
        "::5f3c9a1e7b2d4c6f8a0e1b3d5c7f9a2e::\n"
        "Service execution failed its trusted prerequisites.\n"
    )


def test_stop_commands_marker_is_fresh_per_run(monkeypatch, capsys):
    """FR-20 N (R3-F2): a forged end marker cannot be guessed from a past run."""
    monkeypatch.setattr("secrets.token_hex", FRESH_MARKER)
    markers = []
    for _ in range(2):
        failing_main(monkeypatch, {"events-0001.jsonl": web_failure()})
        lines = capsys.readouterr().err.splitlines()
        start = re.fullmatch(r"::stop-commands::([0-9a-f]{32})", lines[0])
        assert start
        assert lines[-2] == "::" + start[1] + "::"
        markers.append(start[1])
    assert markers[0] != markers[1]


def test_control_characters_become_spaces_in_every_field():
    """FR-20 N: C0/C1, line/paragraph separators and bidi controls never pass."""
    raw = "a\rb\x00c\x1bd\x7fe\x85f\x9bg\u2028h\u2029i\u202ej\u2066k\u2069l"
    assert worker._field(raw) == "a b c d e f g h i j k l"


def test_crafted_message_cannot_inject_log_or_summary_lines(
    monkeypatch, capsys, public
):
    """FR-20 N (F-02): CR payloads stay inside one aws_error_message line."""
    message = "a\r::add-mask::b\r- urn: urn:pulumi:forged::x::y\x1b[8m"
    events = {
        "events-0001.jsonl": [
            step("resourcePreEvent"),
            error(aws_message("AccessDenied", message)),
            step("resOpFailedEvent"),
        ]
    }
    failing_main(monkeypatch, events)
    expected = (
        "Operator diagnostics (allow-listed fields only):\n"
        "- urn: urn:pulumi:test::user-service-infrastructure::"
        "aws:ecs/service:Service::user-service-web-service\n"
        "  type: aws:ecs/service:Service\n"
        "  operation: create\n"
        "  aws_error_code: AccessDenied\n"
        "  aws_error_message: a ::add-mask::b - urn: urn:pulumi:forged::x::y [8m\n"
    )
    assert capsys.readouterr().err == START + expected + END + FAILED + "\n"
    assert (public / "operator-diagnostics.txt").read_text() == expected


def test_late_failure_in_a_long_event_log_is_reported(monkeypatch, capsys):
    """FR-20 B: a failure after the first 8 MiB of a log is still reported."""
    filler = json.dumps({"stdoutEvent": {"message": "x" * 1000}})
    failing_main(
        monkeypatch,
        {"events-0001.jsonl": [filler] * (9 * 1024) + web_failure()},
    )
    assert capsys.readouterr().err == START + SUMMARY + END + FAILED + "\n"


def test_cut_log_without_a_parsed_failure_still_marks_truncation(monkeypatch, capsys):
    """FR-20 B: an over-long line still yields the header and the marker."""
    failing_main(monkeypatch, {"events-0001.jsonl": ["x" * (9 * 1024 * 1024)]})
    assert capsys.readouterr().err == (
        START + "Operator diagnostics (allow-listed fields only):\n"
        "[truncated]\n" + END + FAILED + "\n"
    )


def test_failure_lines_are_published_for_the_job_summary(
    monkeypatch, capsys, public, tmp_path
):
    """FR-20 P/N/E: the host gets exactly the sanitized lines, never a secret.

    No diagnostics publish nothing, and a planted link is never written through.
    """
    failing_main(monkeypatch, {})
    assert capsys.readouterr().err == FAILED + "\n"
    assert list(public.iterdir()) == []
    monkeypatch.setenv("AWS_SESSION_TOKEN", "synthetic-session-token-value")
    events = {
        "events-0001.jsonl": [
            *web_failure(),
            error(f"secret detail {FAKE_SECRET}", severity="warning"),
        ]
    }
    failing_main(
        monkeypatch,
        events,
        private=f"private.log line {FAKE_SECRET} synthetic-session-token-value",
    )
    capsys.readouterr()
    published = public / "operator-diagnostics.txt"
    assert published.exists()
    assert published.read_text() == SUMMARY
    assert published.stat().st_mode & 0o777 == 0o644
    published.unlink()
    target = tmp_path / "target.txt"
    published.symlink_to(target)
    failing_main(monkeypatch, events)
    assert capsys.readouterr().err == START + SUMMARY + END + FAILED + "\n"
    assert not target.exists()
