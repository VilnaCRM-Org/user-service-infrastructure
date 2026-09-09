#!/usr/bin/env python3
"""Run only the authenticated TEST registry graph through the saved-plan runner.

Invoke installed main with its locked virtualenv and python -I. Artifact inputs
come from trusted same-run upload outputs. No PR Python/Makefile is executed.
Private checkpoint resources remain in this process, never in output artifacts.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402  # nosec B404
from contextlib import contextmanager  # noqa: E402

import poc_backend_observer as backend  # noqa: E402
import poc_contract  # noqa: E402
import poc_provider_runtime as providers  # noqa: E402
import poc_registry_plan as graph  # noqa: E402
import poc_source_artifact as artifact  # noqa: E402
import pulumi_command_preflight as preflight  # noqa: E402
import run_pulumi_command as runner  # noqa: E402
from poc_phase_admission import SourceAdmission  # noqa: E402
from poc_registry_phase_entrypoint import project_registry_phase  # noqa: E402
from reviewed_source_admission import verify_reviewed_source  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MAX_PLAN_BYTES = 16 * 1024 * 1024
TRUSTED_PATHS = ("scripts", "pulumi", "policy", "pyproject.toml", "uv.lock")


def _require(value):
    if not value:
        raise ValueError("Registry execution precondition failed")


def _git(*arguments):
    result = subprocess.run(  # nosec B603 B607
        ["git", "-C", str(ROOT), *arguments],
        capture_output=True,
        check=False,
        timeout=30,
    )
    _require(result.returncode == 0)
    return result.stdout


def _trusted_root():
    """Bind the executed checkout and interpreter to this main workflow revision."""
    _, sha = artifact._context(os.environ)
    return _verify_checkout(sha)


def _verify_checkout(sha, *, extra_paths=()):
    """Verify installed bytes after the caller authenticates its own run context."""
    _require(_git("rev-parse", "--show-toplevel").decode().strip() == str(ROOT))
    _require(_git("rev-parse", "HEAD").decode().strip() == sha)
    _require(
        _git("remote", "get-url", "origin").decode().strip()
        in {
            f"https://github.com/{artifact.REPOSITORY}.git",
            f"https://github.com/{artifact.REPOSITORY}",
            f"git@github.com:{artifact.REPOSITORY}.git",
        }
    )
    paths = (*TRUSTED_PATHS, *extra_paths)
    _git("diff", "--quiet", "--no-ext-diff", "HEAD", "--", *paths)
    _require(not _git("ls-files", "--others", "--exclude-standard", "--", *paths))
    _require(Path(sys.prefix).resolve() == (ROOT / ".venv").resolve())
    _require((ROOT / ".venv/bin/python").is_file())
    return sha


def _review(source):
    facts, request = source["source"], source["request"]
    preflight.revalidate_requester(request)
    return verify_reviewed_source(
        artifact.REPOSITORY,
        request["pull_request_number"],
        facts["head_sha"],
        facts["base_sha"],
        gh=preflight.gh,
    )


def _child_environment(source):
    return _runtime_environment(source["source"]["head_sha"])


def _runtime_environment(head_sha):
    """Only installed paths configure the runtime; GitHub tokens stay in parent."""
    home = providers.verify_runtime(ROOT)
    removed = {
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "GH_ENTERPRISE_TOKEN",
        "GITHUB_ENTERPRISE_TOKEN",
        "ACTIONS_RUNTIME_TOKEN",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        "ACTIONS_ID_TOKEN_REQUEST_URL",
    }
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in removed
        and not key.startswith(("PYTHON", "PULUMI_", "UV_", "POLICY_"))
    }
    env.update(
        {
            "PULUMI_BACKEND_URL": f"s3://{backend.BUCKET}",
            "PULUMI_SECRETS_PROVIDER": backend.PROVIDER,
            "PULUMI_COMMIT_SHA": head_sha,
            "PULUMI_EXPECTED_SHA": head_sha,
            "PULUMI_SKIP_UPDATE_CHECK": "true",
            "PULUMI_HOME": str(home),
            "PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION": "true",
            "PULUMI_IGNORE_AMBIENT_PLUGINS": "true",
            "PULUMI_PYTHON_CMD": str(ROOT / ".venv/bin/python"),
            "POLICY_VENV": str(ROOT / ".venv"),
            "UV_PROJECT_ENVIRONMENT": str(ROOT / ".venv"),
            "UV_FROZEN": "true",
            "UV_NO_SYNC": "true",
        }
    )
    return env


def _program(projection):
    """Generate closed data plus a fixed installed graph import, never PR code."""
    encoded = json.dumps(projection.registries, sort_keys=True)
    return (
        "import json, sys\nfrom pathlib import Path\n"
        "root = Path(__file__).resolve().parents[2]\n"
        "sys.path[:0] = [str(root / 'scripts'), str(root / 'pulumi')]\n"
        "from poc_registry_phase_entrypoint import (\n"
        "    RegistryPhaseProjection, run_registry_phase)\n"
        f"run_registry_phase(RegistryPhaseProjection(json.loads({encoded!r})))\n"
    )


@contextmanager
def _project(projection):
    """A fixed relative project path keeps existing manifest replay checks valid."""
    directory = ROOT / ".poc-registry"
    directory.mkdir(mode=0o700)  # Exclusive; never reuse an existing program.
    try:
        project = directory / "pulumi"
        project.mkdir(mode=0o700)
        (project / "Pulumi.yaml").write_text(
            f"name: {backend.PROJECT}\nruntime:\n  name: python\n"
            f"  options:\n    virtualenv: {json.dumps(str(ROOT / '.venv'))}\n"
        )
        config = _git("show", f"{os.environ['GITHUB_SHA']}:pulumi/Pulumi.test.yaml")
        (project / "Pulumi.test.yaml").write_bytes(config)
        (project / "__main__.py").write_text(_program(projection))
        yield project
    finally:
        shutil.rmtree(directory)


def ecr_read(name):
    """Describe one fixed repository; only the native missing code is absence."""
    _require(name in {row["name"] for row in graph.REGISTRIES.values()})
    result = subprocess.run(  # nosec B603 B607
        [
            "aws",
            "ecr",
            "describe-repositories",
            "--registry-id",
            backend.ACCOUNT,
            "--repository-names",
            name,
            "--region",
            backend.REGION,
            "--endpoint-url",
            f"https://api.ecr.{backend.REGION}.amazonaws.com",
            "--output",
            "json",
            "--no-cli-pager",
            "--no-paginate",
        ],
        capture_output=True,
        check=False,
        timeout=60,
        env={**os.environ, "AWS_MAX_ATTEMPTS": "1"},
    )
    _require(len(result.stdout) <= backend.MAX_METADATA and len(result.stderr) <= 65536)
    if result.returncode != 0:
        _require(
            re.match(
                rb"\s*(?:aws: \[ERROR\]: )?An error occurred "
                rb"\(RepositoryNotFoundException\) "
                rb"when calling the "
                rb"DescribeRepositories operation:",
                result.stderr,
            )
            is not None
        )
        return None
    response = backend._json(result.stdout)
    rows = response.get("repositories")
    _require(type(rows) is list and len(rows) == 1)
    return rows[0]


def _ecr_inventory(resources):
    existing = {row["inputs"]["name"] for row in resources if row["type"] == graph.ECR}
    for registry in graph.REGISTRIES.values():
        name = registry["name"]
        actual = ecr_read(name)
        if name not in existing:
            _require(actual is None)
            continue
        expected = {
            "repositoryName": name,
            "registryId": backend.ACCOUNT,
            "repositoryArn": (
                f"arn:aws:ecr:{backend.REGION}:{backend.ACCOUNT}:repository/{name}"
            ),
            "repositoryUri": (
                f"{backend.ACCOUNT}.dkr.ecr.{backend.REGION}.amazonaws.com/{name}"
            ),
            "imageTagMutability": "IMMUTABLE",
            "imageScanningConfiguration": {"scanOnPush": True},
        }
        _require(type(actual) is dict)
        _require(all(actual.get(key) == value for key, value in expected.items()))


def _capture(source, command, projection):
    capture = backend.capture_backend(source, operation=command)
    _require(capture.summary["state"]["kind"] == "observed_checkpoint")
    graph._prior(capture.resources, graph._graph(projection))
    _ecr_inventory(capture.resources)
    return capture


def _binding(context, capture):
    summary, state = capture.summary, capture.summary["state"]
    expected = {
        "accountId": backend.ACCOUNT,
        "backendUrl": f"s3://{backend.BUCKET}",
        "project": backend.PROJECT,
        "stack": "test",
        "kmsKeyArn": summary["kms_key_arn"],
        "checkpointVersionId": state["VersionId"],
        "checkpointETag": state["ETag"],
    }
    _require(type(context.provider_identity) is dict)
    _require(
        all(
            context.provider_identity.get(key) == value
            for key, value in expected.items()
        )
    )


def _read_plan(path):
    _require(
        not path.is_symlink()
        and path.is_file()
        and path.stat().st_size <= MAX_PLAN_BYTES
    )
    raw = path.read_bytes()
    _require(len(raw) <= MAX_PLAN_BYTES)
    value = json.loads(
        raw,
        object_pairs_hook=poc_contract._pairs,
        parse_constant=poc_contract._reject_nonfinite,
    )
    _require(type(value) is dict)
    return raw, value


def _gate(source, command, projection, initial):
    def validate(context, stack, plan_path, preview_path):
        _require(stack == "test")
        _review(source)
        plan_raw, plan = _read_plan(plan_path)
        preview_raw, preview = _read_plan(preview_path)
        current = _capture(source, command, projection)
        _require(current.summary["state"] == initial.summary["state"])
        _binding(context, current)
        graph.validate(
            preview,
            saved_plan=plan,
            prior_resources=current.resources,
            projection=projection,
        )
        _require(
            plan_path.read_bytes() == plan_raw
            and preview_path.read_bytes() == preview_raw
        )
        preflight.revalidate_requester(source["request"])

    return validate


def execute(command, *, artifact_id, archive_sha256, source_sha256):
    """Authenticate then execute the sole fixed registry plan/replay path."""
    _require(command in ("plan", "up-plan", "drift"))
    _trusted_root()
    source, contract = artifact.load_verified_contract(
        artifact_id=artifact_id,
        archive_sha256=archive_sha256,
        source_sha256=source_sha256,
    )
    _require(source["request"]["target_environment"] == "test")
    _require(source["source"]["base_sha"] == os.environ["GITHUB_SHA"])
    _require(command == "plan" or source["request"]["command"] == "up")
    _review(source)
    projection = project_registry_phase(SourceAdmission(**source["source"]), contract)
    operation = "up-plan" if command == "up-plan" else "plan"
    initial = _capture(source, operation, projection)
    if command == "drift":
        _require(len(initial.resources) == 7)
    with _project(projection) as project:
        context = runner.CommandContext(
            root_dir=ROOT,
            env=_child_environment(source),
            pulumi_dir=project,
            policy_pack_dir=ROOT / "policy",
            plan_dir=ROOT / ".artifacts/pulumi-plan",
            preview_artifact_dir=ROOT / ".artifacts/pulumi-preview",
            backend_url=f"s3://{backend.BUCKET}",
            secrets_provider=backend.PROVIDER,
            registry_plan_gate=_gate(source, operation, projection, initial),
        )
        status = runner._dispatch_command(operation, context, ["test"])
        if status == 0 and command == "up-plan":
            final = _capture(source, operation, projection)
            _require(len(final.resources) == 7)
        return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "up-plan", "drift"))
    for field in ("artifact-id", "archive-sha256", "source-sha256"):
        parser.add_argument(f"--{field}", required=True)
    args = parser.parse_args(argv)
    try:
        return execute(**vars(args))
    except (
        ValueError,
        OSError,
        TypeError,
        KeyError,
        AttributeError,
        RuntimeError,
        RecursionError,
        subprocess.SubprocessError,
    ):
        print("INVALID: registry execution failed", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
