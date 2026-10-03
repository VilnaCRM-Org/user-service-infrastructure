"""Installed service worker: authenticate in root, execute Pulumi as UID 2000.

The workflow supplies immutable mounts and its existing credentials. For a
workload-phase contract this entry point routes TEST ``plan`` and ``up-plan`` to
the protected saved-plan runner; workload drift stays rejected.

On failure the worker prints sanitized operator diagnostics (FR-20): from the
private Pulumi engine event logs it keeps only the failing URN, resource type,
operation and the AWS error code and message, redacts secret-like values and
truncates with a marker. The same lines go to a bounded file in ``/public``
so the host can append them to the job summary. ``private.log`` itself never
leaves the worker.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse  # noqa: E402
import contextlib  # noqa: E402
import tempfile  # noqa: E402

import poc_registry_runner as registry  # noqa: E402
import poc_workload_runner as workload  # noqa: E402
from service_execution_process import require  # noqa: E402
from service_execution_transport import ServiceTransport, copy_tree  # noqa: E402

JOBS = {
    "test_preview": ("test", "plan"),
    "test_apply": ("test", "up-plan"),
    "test_post_apply_drift": ("test", "drift"),
}
ACCOUNTS = {"test": "891377212104"}
SESSION_KEYS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")
# FR-20 operator diagnostics: closed field allow-list and fixed bounds.
EVENT_LOG_GLOB = "events-*.jsonl"
EVENT_LINE_BYTES = 1024 * 1024
PUBLIC = Path("/public")
DIAGNOSTICS_FILE = "operator-diagnostics.txt"
DIAGNOSTICS_FILE_BYTES = 64 * 1024
DIAGNOSTIC_ENTRIES = 10
DIAGNOSTIC_FIELD_CHARS = 300
TRUNCATED = "[truncated]"
REDACTED = "[redacted]"
OPERATIONS = frozenset(
    {
        "create",
        "update",
        "delete",
        "replace",
        "create-replacement",
        "delete-replaced",
        "read",
        "read-replacement",
        "refresh",
        "import",
        "import-replacement",
        "discard",
        "discard-replaced",
        "remove-pending-replace",
        "same",
    }
)
URN = re.compile(r"urn:pulumi:[A-Za-z0-9._-]+::[A-Za-z0-9._-]+::[A-Za-z0-9:/$._-]+")
RESOURCE_TYPE = re.compile(r"[A-Za-z0-9-]+:[A-Za-z0-9/._-]*:[A-Za-z0-9._-]+")
AWS_ERROR = re.compile(
    r"(?:api error |RequestID: [^,\s]*, )([A-Za-z][A-Za-z0-9.]{0,63}): ([^\n]*)"
)
COLOR_TAG = re.compile(r"<\{%[^%]*%\}>")
_SENSITIVE_KEY_PATTERN = (
    r"[A-Za-z0-9_.-]*?(?:password|passwd|secret|token|api[_-]?key|private[_-]?key"
    r"|access[_-]?key|credentials?)[A-Za-z0-9_.-]*"
)
# (pattern, replacement) pairs, applied in order after the session values.
SECRET_LIKE = (
    (
        re.compile(r"-----BEGIN [A-Z ]+-----.*?(?:-----END [A-Z ]+-----|$)", re.S),
        REDACTED,
    ),
    (re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*"), REDACTED),
    (re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), REDACTED),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"), REDACTED),
    # URL userinfo: scheme://user:password@host keeps only the scheme and host.
    (re.compile(r"\b([A-Za-z][A-Za-z0-9+.-]*://)[^/\s@]*@"), r"\g<1>[redacted]@"),
    # Authorization headers lose the scheme and the credential.
    (
        re.compile(
            r"(?i)(\bauthorization[\"']?\s*[=:]\s*[\"']?)"
            r"(?:[A-Za-z0-9-]+\s+)?[^\s,;\"']+"
        ),
        r"\g<1>[redacted]",
    ),
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]+"), r"\g<1>[redacted]"),
    # Secret-named keys, also inside identifiers and quoted JSON values.
    (
        re.compile(
            r"(?i)(" + _SENSITIVE_KEY_PATTERN + r"[\"']?\s*(?:=|:(?=[\s\"']))\s*[\"']?)"
            r"(?:(?<=\")[^\"]*|(?<=')[^']*|[^\s,;\"'}&]+)"
        ),
        r"\g<1>[redacted]",
    ),
    (re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"), REDACTED),
    (re.compile(r"(?i)\b[0-9a-f]{32,}\b"), REDACTED),
)
# Free-text AWS error messages: after the rules above, every token of 20 or more
# characters (split on whitespace and quoting or assignment delimiters) is
# redacted unless it is a whole ARN, a Pulumi URN, a digit-free PascalCase word
# or IAM action (InvalidParameterException, secretsmanager:GetSecretValue), or a
# lower-case name, host or URL path.
LONG_TOKEN = re.compile(r"[^\s\"',;()\[\]{}<>=`]{20,}")
_ARN = re.compile(r"arn:aws[a-z-]*:[a-z0-9-]+:[a-z0-9-]*:[0-9]{0,12}:\S+")
_KEPT_TOKEN = re.compile(
    r"urn:pulumi:\S*|(?:[a-z0-9-]+:)?(?:[A-Z][a-z]+)+|[a-z0-9./:@-]+"
)
# Inside an ARN path a hyphen-free run of 20 or more characters that mixes upper
# and lower case, or holds + or =, is key material, not a resource name.
_ARN_RUN = re.compile(r"[A-Za-z0-9+=_]{20,}")
# C0/C1 controls, line and paragraph separators and bidi controls: each would
# split or disguise a line in the job log (workflow commands) or the summary.
CONTROL_CHARS = re.compile("[\x00-\x1f\x7f-\x9f\u2028\u2029\u202a-\u202e\u2066-\u2069]")
# The legacy "##[command]" syntax is also neutralised in every field.
LEGACY_COMMAND = "##["


def _arn_run(match):
    run = match[0]
    mixed = run != run.lower() and run != run.upper()
    return REDACTED if mixed or "+" in run or "=" in run else run


def _long_token(match):
    token = match[0]
    if _ARN.fullmatch(token):
        return _ARN_RUN.sub(_arn_run, token)
    return token if _KEPT_TOKEN.fullmatch(token) else REDACTED


def admit(job):
    """Reuse original native requester/reviewer or scheduled-main authority."""
    require(job in JOBS, "worker-job")
    run_id, sha = registry.artifact._context(os.environ)
    registry.artifact._producer(registry.preflight.gh, run_id, sha)
    registry._verify_checkout(sha)
    require(os.environ.get("EXPECTED_BASE_SHA") == sha, "request-base")
    request = registry.preflight.read_request()
    registry.preflight.revalidate_requester(request)
    registry.verify_reviewed_source(
        registry.artifact.REPOSITORY,
        request["pull_request_number"],
        request["head_sha"],
        os.environ["EXPECTED_BASE_SHA"],
        gh=registry.preflight.gh,
    )
    account, command = JOBS[job]
    require(request["target_environment"] == account, "request-account")
    require(command == "plan" or request["command"] == "up", "request-command")
    return request["head_sha"]


def _coordinates(account):
    expected = {
        "AWS_ACCOUNT_ID": ACCOUNTS[account],
        "AWS_REGION": "eu-central-1",
        "PULUMI_BACKEND_URL": f"s3://pulumi-user-service-infrastructure-{account}-state",
        "PULUMI_SECRETS_PROVIDER": (
            f"awskms://alias/pulumi-user-service-infrastructure-{account}-secrets"
            "?region=eu-central-1"
        ),
    }
    require(
        all(os.environ.get(key) == value for key, value in expected.items()),
        "worker-coordinates",
    )
    return expected


def _replay_inputs(port, account):
    require(account == "test", "worker-account")
    source = Path("/trusted") / ".artifacts"
    destination = port.repo / ".artifacts"
    destination.mkdir(mode=0o700, exist_ok=True)
    for name in ("pulumi-plan", "pulumi-preview"):
        copy_tree(source / name, destination / name)


def _test(port, command, head):
    os.write(2, b"Trusted worker stage: source contract\n")
    references = {
        "artifact_id": os.environ["POC_SOURCE_ARTIFACT_ID"],
        "archive_sha256": os.environ["POC_SOURCE_ARCHIVE_SHA256"],
        "source_sha256": os.environ["POC_SOURCE_SHA256"],
    }
    source, contract = registry.artifact.load_verified_contract(**references)
    require(
        source["source"]["head_sha"] == head
        and source["source"]["base_sha"] == os.environ["GITHUB_SHA"]
        and source["request"]["target_environment"] == "test",
        "workload-source-binding",
    )
    os.write(2, b"Trusted worker stage: source review\n")
    registry._review(source)
    if contract["phase"] == "workload":
        require(command in ("plan", "up-plan"), "workload-drift-not-enabled")
        os.write(2, b"Trusted worker stage: workload saved-plan execution\n")
        return workload.execute(command, **references, transport=port)
    os.write(2, b"Trusted worker stage: registry execution\n")
    return registry.execute(command, **references, transport=port)


def execute(job, area):
    require(job in JOBS and os.environ.get("GITHUB_JOB") == job, "worker-job")
    account, command = JOBS[job]
    os.write(2, b"Trusted worker stage: request admission\n")
    head = admit(job)
    os.write(2, b"Trusted worker stage: account coordinates\n")
    coordinates = _coordinates(account)
    os.write(2, b"Trusted worker stage: isolated transport\n")
    port = ServiceTransport(
        area,
        session={key: os.environ.get(key, "") for key in SESSION_KEYS},
        region=coordinates["AWS_REGION"],
        account=coordinates["AWS_ACCOUNT_ID"],
        before_program=lambda: require(
            admit(job) == head, "worker-pre-execution-admission"
        ),
    )
    if command == "up-plan":
        os.write(2, b"Trusted worker stage: saved plan inputs\n")
        _replay_inputs(port, account)
    result = _test(port, command, head)
    require(result == 0, "worker-execution")
    require(admit(job) == head, "worker-final-admission")
    if command == "plan":
        output = Path("/public")
        for name in ("pulumi-plan", "pulumi-preview"):
            copy_tree(port.repo / ".artifacts" / name, output / name)


def redact(text):
    """Remove the worker's session values and every secret-like pattern."""
    for key in SESSION_KEYS:
        value = os.environ.get(key, "")
        if len(value) >= 8:
            text = text.replace(value, REDACTED)
    for pattern, replacement in SECRET_LIKE:
        text = pattern.sub(replacement, text)
    return text


def redact_message(text):
    """Redact a free-text AWS error message: the rules, then every long token."""
    return LONG_TOKEN.sub(_long_token, redact(text))


def _field(text, scrub=redact):
    """Flatten controls, redact and neutralise ``##[`` before truncating.

    Each field is one line for every reader, carries no workflow command, and a
    cut can never expose part of a secret.
    """
    text = scrub(CONTROL_CHARS.sub(" ", text)).replace(LEGACY_COMMAND, "# #[")
    if len(text) > DIAGNOSTIC_FIELD_CHARS:
        return text[:DIAGNOSTIC_FIELD_CHARS] + TRUNCATED
    return text


def _lines(handle):
    """Yield each line up to the cap; an over-long line is skipped as cut."""
    while line := handle.readline(EVENT_LINE_BYTES + 1):
        if len(line) <= EVENT_LINE_BYTES:
            yield line, False
            continue
        while line and not line.endswith(b"\n"):
            line = handle.readline(EVENT_LINE_BYTES)
        yield b"", True


def _read_events(path, cuts):
    """Stream one child-written event log without following links.

    Each line is capped, so memory stays bounded while a failure late in a long
    log is still found. A cut line is recorded in ``cuts`` and skipped.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        return
    with os.fdopen(descriptor, "rb") as handle:
        for line, cut in _lines(handle):
            if cut:
                cuts.append(path)
            with contextlib.suppress(ValueError):
                event = json.loads(line.decode(errors="replace"))
                if type(event) is dict:
                    yield event


def _metadata(event):
    """Return resource-step metadata from a pre or failed-operation event."""
    for kind in ("resOpFailedEvent", "resourcePreEvent"):
        body = event.get(kind)
        if type(body) is dict and type(body.get("metadata")) is dict:
            return body["metadata"]
    return None


def _step(metadata):
    """Keep only the allow-listed step fields, so memory stays small."""
    return {"type": metadata.get("type"), "op": metadata.get("op")}


def _failures(events):
    """Collect allow-listed fields for every URN with an error or failed step."""
    steps, failures = {}, {}
    for event in events:
        metadata = _metadata(event)
        if metadata is not None and type(metadata.get("urn")) is str:
            steps[metadata["urn"]] = _step(metadata)
            if "resOpFailedEvent" in event:
                failures.setdefault(metadata["urn"], None)
        body = event.get("diagnosticEvent")
        if (
            type(body) is dict
            and body.get("severity") == "error"
            and type(body.get("urn")) is str
            and type(body.get("message")) is str
        ):
            failures[body["urn"]] = AWS_ERROR.search(COLOR_TAG.sub("", body["message"]))
    return [(urn, steps.get(urn, {}), error) for urn, error in failures.items()]


def _entry(urn, metadata, error):
    """Render one failure from the allow-listed fields only."""
    kind = metadata.get("type")
    operation = metadata.get("op")
    lines = [
        "- urn: " + (_field(urn) if URN.fullmatch(urn) else REDACTED),
        "  type: "
        + (
            _field(kind)
            if type(kind) is str and RESOURCE_TYPE.fullmatch(kind)
            else "unknown"
        ),
        "  operation: "
        + (
            operation
            if type(operation) is str and operation in OPERATIONS
            else "unknown"
        ),
    ]
    if error is not None:
        lines.append("  aws_error_code: " + _field(error.group(1)))
        message = _field(error.group(2).strip(), redact_message)
        lines.append("  aws_error_message: " + message)
    return lines


def diagnostics(area):
    """Build the sanitized FR-20 operator summary from the private event logs."""
    outputs = area / "outputs"
    paths = sorted(outputs.glob(EVENT_LOG_GLOB)) if outputs.is_dir() else []
    failures, cuts = [], []
    for path in paths:
        failures.extend(_failures(_read_events(path, cuts)))
    truncated = bool(cuts)
    if not failures and not truncated:
        return []
    lines = ["Operator diagnostics (allow-listed fields only):"]
    for failure in failures[:DIAGNOSTIC_ENTRIES]:
        lines.extend(_entry(*failure))
    if len(failures) > DIAGNOSTIC_ENTRIES or truncated:
        lines.append(TRUNCATED)
    return lines


def _publish(lines):
    """Hand the sanitized lines to the host for the job summary, bounded.

    The file is created fresh in ``/public`` without following links; the host
    validates every line again before it reaches ``$GITHUB_STEP_SUMMARY``.
    """
    data = "".join(line + "\n" for line in lines).encode()[:DIAGNOSTICS_FILE_BYTES]
    descriptor = os.open(
        PUBLIC / DIAGNOSTICS_FILE,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o644,
    )
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)


def _report(area):
    """Print and publish the sanitized summary; never let it mask the failure.

    The printed block sits between ``::stop-commands::`` and its fresh random
    end marker, so the runner processes no workflow command inside it.
    """
    with contextlib.suppress(Exception):
        lines = diagnostics(area)
        if lines:
            marker = secrets.token_hex(16)
            print(f"::stop-commands::{marker}", file=sys.stderr)
            for line in lines:
                print(line, file=sys.stderr)
            print(f"::{marker}::", file=sys.stderr)
            _publish(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", choices=tuple(JOBS))
    arguments = parser.parse_args(argv)
    try:
        require(os.geteuid() == 0 and os.getpid() == 1, "worker-root-pid")
        # The launcher supplies a clean fixed PATH; private logs never reach Actions.
        require(
            os.environ.get("PATH") == "/opt/pulumi:/usr/local/bin:/usr/bin:/bin",
            "worker-path",
        )
        with tempfile.TemporaryDirectory(prefix="service-worker-") as name:
            area = Path(name)
            home = area / "root-home"
            home.mkdir(mode=0o700)
            os.environ["HOME"] = str(home)
            try:
                with (area / "private.log").open("w") as log:
                    (area / "private.log").chmod(0o600)
                    with (
                        contextlib.redirect_stdout(log),
                        contextlib.redirect_stderr(log),
                    ):
                        execute(arguments.job, area)
            except Exception:
                _report(area)
                raise
        print("Service execution completed with trusted checks.")
        return 0
    except Exception:
        print("Service execution failed its trusted prerequisites.", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
