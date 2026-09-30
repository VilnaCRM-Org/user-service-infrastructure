"""Workload apply documentation must match the installed worker routing."""

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import service_execution_worker as worker  # noqa: E402

# Wording that claims workload apply is disabled. Any match contradicts a worker
# that routes a workload-phase ``up-plan`` to the protected runner.
DISABLED_APPLY_CLAIMS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"no (aws|workload) apply is (enabled|admitted)",
        r"rejects? workload (`?up-plan`?|apply)\b",
        r"forbids? workload apply",
        r"apply stops before",
        r"routes only `?test_preview`?",
        r"workflow selection remains registry-only",
        r"execution stops remain",
        r"does not enable the workload worker",
        r"preview admission is not apply authority",
        r"first-topology gate for previews only",
        r"does not execute a workload graph",
        r"worker remains disabled",
        r"does not enable workload execution",
        r"stops? remains? unchanged",
        r"still rejects workload requests",
        r"no cli or config dispatches to this class",
        r"before wiring it into the trusted controller",
        r"before\s+removing that stop",
        r"unconnected workload (helper|runner)",
        r"preview-only worker",
        r"(observer/publisher )?helpers? remains? unconnected",
        r"no workload phase is admitted",
        r"next gate is a trusted root dispatcher",
        r"before any future workload execution",
        r"workload (routes?|execution)[^.]{0,80}\babsent\b",
        r"admits only[^.]{0,40}registry-phase",
        r"future (authenticated )?result observer",
        r"future (root-owned generated program|root materializer|protected launcher)",
        r"network gate remains\s+fail-closed",
    )
)
HISTORICAL_CLAIMS = (
    "log storage. No AWS apply is enabled.",
    "It rejects workload `up-plan` and drift before invoking the runner",
    "Admit a validated preview; the worker still forbids workload apply.",
    "[workload admission](poc-workload-admission.md). Apply stops before this path.",
    "The installed worker routes only `test_preview` to the workload runner.",
    "Workflow selection remains registry-only until these checks are executable.",
    "The existing workload execution stops remain enabled.",
    "rejects workload apply and drift before invoking that runner",
    "It does not enable the workload worker. Both existing execution stops remain",
    "No workload apply is admitted; a successful preview is not an acceptance result.",
    # Stale wording found in the worker, bridge, bridge docs and workload stack.
    "point observes workload prerequisites but does not execute a workload graph.",
    "The existing worker remains disabled until native plan/replay gates are "
    "connected.",
    "It does not enable workload execution. The worker's capability/plan stop and "
    "fallback execution stop remain unchanged.",
    "but the installed worker still rejects workload requests. Complete "
    "capability/input admission",
    "observation, phase-aware drift and actual health/release/rollback before "
    "removing that stop.",
    "No CLI or config dispatches to this class; verified releases",
    "separate prerequisites before wiring it into the trusted controller.",
    # Stale wording found by the attempt-3 gate.
    "The unconnected workload helper reuses the original registry completion verifier",
    "The preview-only worker invokes the bounded role/input prerequisite reader.",
    "The registry completion observer/publisher helpers remain unconnected.",
    "The TEST-only source prerequisite still blocks PROD promotion, and no workload "
    "phase is admitted by this change.",
    "The next gate is a trusted root dispatcher that authenticates the baseline and",
    "must be checked independently before any future workload execution.",
    # Stale wording found by the pre-gate audit of attempt 5.
    "The TEST controller admits only authenticated registry-phase plan/apply/drift",
    "PROD and workload routes remain absent.",
    "PROD, workload execution, registry-completion proofs, publisher dispatch, and "
    "promotion are absent from this controller.",
    "This is one component of a future authenticated result observer.",
    "Encode detached nonsecret data for a future root-owned generated program.",
    "The future root materializer must protect this program",
    "Return the future protected launcher; never execute or install it here.",
    "The saved-plan network gate remains fail-closed while complete resource",
)


def _documents():
    """Yield Markdown text and Python docstrings that describe the PoC runner."""
    for pattern in ("docs/**/*.md", "specs/**/*.md", "*.md"):
        for path in sorted(ROOT.glob(pattern)):
            yield path.relative_to(ROOT), path.read_text(encoding="utf-8")
    for base, pattern in (
        ("scripts", "poc_*.py"),
        ("scripts", "service_execution_*.py"),
        ("pulumi/app", "*.py"),
    ):
        for path in sorted((ROOT / base).glob(pattern)):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(
                    node,
                    (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
                ):
                    docstring = ast.get_docstring(node)
                    if docstring:
                        yield path.relative_to(ROOT), docstring


def _disabled_apply_claims():
    claims = []
    for path, text in _documents():
        flat = " ".join(text.split())
        claims.extend(
            (str(path), match.group(0))
            for claim in DISABLED_APPLY_CLAIMS
            for match in claim.finditer(flat)
        )
    return claims


def _routes_workload(monkeypatch, command):
    """Return whether the worker hands a workload-phase command to the runner."""
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
    calls = []
    monkeypatch.setattr(
        worker.registry.artifact,
        "load_verified_contract",
        lambda **_: (source, {"phase": "workload"}),
    )
    monkeypatch.setattr(worker.registry, "_review", lambda _: None)
    monkeypatch.setattr(
        worker.registry,
        "execute",
        lambda *_a, **_k: pytest.fail("registry execution for a workload contract"),
    )
    monkeypatch.setattr(
        worker.workload,
        "execute",
        lambda routed, **_: calls.append(routed) or 0,
    )
    try:
        worker._test(None, command, "a" * 40)
    except ValueError:
        return False
    return calls == [command]


@pytest.mark.parametrize("sentence", HISTORICAL_CLAIMS)
def test_disabled_apply_wording_is_recognized(sentence):
    assert any(claim.search(sentence) for claim in DISABLED_APPLY_CLAIMS)


@pytest.mark.parametrize(
    "sentence",
    [
        "rejects workload drift before invoking it",
        "Workload drift remains rejected until an accepted-workload receipt exists.",
        "routes TEST `plan` (`test_preview`) and `up-plan` (`test_apply`)",
    ],
)
def test_enabled_apply_wording_is_not_a_disabled_claim(sentence):
    assert not any(claim.search(sentence) for claim in DISABLED_APPLY_CLAIMS)


def test_documentation_matches_workload_apply_routing(monkeypatch):
    assert _routes_workload(monkeypatch, "plan") is True
    assert _routes_workload(monkeypatch, "drift") is False
    claims = _disabled_apply_claims()
    if _routes_workload(monkeypatch, "up-plan"):
        assert claims == [], (
            "Documentation claims workload apply is disabled while the worker "
            f"routes workload up-plan to the runner: {claims}"
        )
    else:
        assert claims, "Documentation must state that workload apply is disabled."


def test_documents_scan_the_pulumi_application_docstrings():
    scanned = {str(path) for path, _ in _documents()}
    assert "pulumi/app/workload_phase.py" in scanned
    assert "scripts/service_execution_worker.py" in scanned


def test_enabled_routing_is_stated_positively(monkeypatch):
    routed = [
        command
        for command in ("plan", "up-plan")
        if _routes_workload(monkeypatch, command)
    ]
    assert routed == ["plan", "up-plan"]
    worker_doc = " ".join((worker.__doc__ or "").split())
    bridge_doc = " ".join(
        (ROOT / "docs/poc-workload-settings-bridge.md").read_text().split()
    )
    for command in routed:
        assert f"``{command}``" in worker_doc, command
        assert f"`{command}`" in bridge_doc, command


# Claims the recovery runbook and related docs must never make while shipped
# admission rejects partial or complete first-workload checkpoints.
RECOVERY_OVERCLAIMS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"continues? from (it|state|the (recorded|partial|checkpoint))",
        r"reviewed import path",
        r"adopts it via",
        r"read the failed `?test_apply`? job summary",
        r"(failing resource|aws error)[^.]{0,80}job summary",
        r"job summary for the failing",
        r"clean failures? (are|is) recoverable",
        r"no workload apply runs until",
    )
)
RECOVERY_HISTORICAL = (
    "so the plan continues from it.",
    "The reviewed import path covers only Secrets Manager secrets.",
    "the next plan adopts it via the reviewed import path",
    "Read the failed `test_apply` job summary for the failing resource and its "
    "AWS error.",
    "so no workload apply runs until its preconditions are met and reviewed.",
)


def _recovery_overclaims():
    hits = []
    for path, text in _documents():
        flat = " ".join(text.split())
        hits.extend(
            (str(path), match.group(0))
            for claim in RECOVERY_OVERCLAIMS
            for match in claim.finditer(flat)
        )
    return hits


@pytest.mark.parametrize("sentence", RECOVERY_HISTORICAL)
def test_recovery_overclaim_wording_is_recognized(sentence):
    assert any(claim.search(sentence) for claim in RECOVERY_OVERCLAIMS)


def test_docs_make_no_unshipped_recovery_or_visibility_claims():
    assert _recovery_overclaims() == []


def test_recovery_runbook_marks_unshipped_paths_and_private_logs():
    text = " ".join((ROOT / "docs/poc-workload-recovery.md").read_text().split())
    for marker in (
        "## 2. Resume (FUTURE; not executable with shipped tooling)",
        "## 3. Abandon (FUTURE; not executable with shipped tooling)",
        "## 5. Secrets Manager recovery-window collisions (FUTURE)",
        "stays in a private temporary log",
        "stop-and-escalate",
        "issue #57",
    ):
        assert marker in text, marker
    ci_doc = " ".join((ROOT / "docs/ci-architecture.md").read_text().split())
    assert "merge gate only" in ci_doc
    assert "#57" in ci_doc
