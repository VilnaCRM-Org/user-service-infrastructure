"""Closed generated child bytes and isolated Pulumi mocks, without AWS."""

import ast
import json
import runpy
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import poc_workload_phase_entrypoint as module  # noqa: E402
from test_poc_registry_phase_entrypoint import source
from test_poc_workload_phase import graph
from test_poc_workload_phase_entrypoint import fixture


def projection():
    contract, images = fixture()
    return module.project_workload_phase(source(contract), contract, images)


def encoded(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


def test_child_wire_round_trip_is_closed_canonical_and_detached():
    original = projection()
    raw = module.encode_workload_projection(original)
    decoded = module.decode_workload_projection(raw)
    assert decoded == original
    assert module.encode_workload_projection(decoded) == raw
    assert set(json.loads(raw)) == {"schema_version", "source", "contract", "images"}
    assert json.loads(raw)["schema_version"] == "poc-workload-child-v1"
    original.images["web"]["uri"] = "foreign"
    assert decoded.images["web"]["uri"] != "foreign"


@pytest.mark.parametrize(
    "raw", [None, "{}", b"", b" " * (module.MAX_PROJECTION_BYTES + 1)]
)
def test_unbounded_or_untyped_child_bytes_reject(raw):
    with pytest.raises(ValueError, match="projection-bound"):
        module.decode_workload_projection(raw)


@pytest.mark.parametrize(
    "raw", [b"not-json", b"\xff", b'{"a":1,"a":2}', b'{"a":NaN}', b"[" * 2000]
)
def test_invalid_ambiguous_or_recursive_json_rejects(raw):
    with pytest.raises(ValueError, match="projection-json"):
        module.decode_workload_projection(raw)


@pytest.mark.parametrize(
    "fault",
    [
        "list",
        "field",
        "version",
        "source-list",
        "source-field",
        "path",
        "hash-type",
        "hash-value",
        "contract",
        "image",
        "noncanonical",
    ],
)
def test_closed_projection_or_source_substitution_rejects(fault):
    raw = module.encode_workload_projection(projection())
    document = json.loads(raw)
    changes = {
        "field": (document, "phase", "workload"),
        "version": (document, "schema_version", "foreign"),
        "source-list": (document, "source", []),
        "source-field": (document["source"], "authorized", True),
        "path": (document["source"], "path", "foreign.json"),
        "hash-type": (document["source"], "head_sha", True),
        "hash-value": (document["source"], "head_sha", "g" * 40),
        "contract": (
            document["contract"]["workload"]["runtime"],
            "health_path",
            "/changed",
        ),
        "image": (document["images"]["web"], "uri", "foreign"),
    }
    if fault in changes:
        target, key, value = changes[fault]
        target[key] = value
    if fault == "list":
        document = []
    with pytest.raises(ValueError):
        module.decode_workload_projection(
            encoded(document) + (b"\n" if fault == "noncanonical" else b"")
        )


def test_all_source_coordinates_revalidate_before_encoding():
    original = projection()
    for key in (
        "contract_sha256",
        "head_sha",
        "base_sha",
        "blob_sha",
        "schema_sha256",
        "validator_sha256",
    ):
        changed = replace(original, source=replace(original.source, **{key: "foreign"}))
        with pytest.raises(ValueError, match="source-identity"):
            module.encode_workload_projection(changed)


def test_encoder_bound_and_wire_do_not_authorize_phase(monkeypatch):
    original = projection()
    monkeypatch.setattr(module, "MAX_PROJECTION_BYTES", 1)
    with pytest.raises(ValueError, match="projection-bound"):
        module.encode_workload_projection(original)


def test_generated_source_contains_only_literal_payload_and_fixed_imports(monkeypatch):
    contract, images = fixture()
    contract["workload"]["external"]["responder"]["channel_reference"] = (
        "'); raise AssertionError('payload was executed'); #"
    )
    value = module.project_workload_phase(source(contract), contract, images)
    program = module.workload_program_source(value)
    tree = ast.parse(program)
    call = tree.body[-1].value
    assert isinstance(call, ast.Call) and call.func.id == "run_workload_program"
    assert len(call.args) == 1 and type(call.args[0].value) is bytes
    assert call.args[0].value == module.encode_workload_projection(value)
    assert tree.body[-2].module == "poc_workload_phase_entrypoint"
    assert "['/trusted/scripts', '/trusted/pulumi']" in program
    calls = []
    monkeypatch.setattr(
        module,
        "run_workload_phase",
        lambda projection: calls.append(projection) or "graph",
    )
    assert module.run_workload_program(call.args[0].value) == "graph"
    assert calls == [value]
    with pytest.raises(ValueError):
        module.run_workload_program(b'{"phase":"workload"}')
    assert calls == [value]


def test_generated_child_matches_existing_bridge_and_registry_baseline(tmp_path):
    bridge = graph(tmp_path, "bridge")
    child = graph(tmp_path, "generated-child")
    # Pulumi collects dependencies concurrently; ordering is not graph identity.
    for receipt in (bridge, child):
        for row in receipt["registrations"].values():
            row["dependencies"].sort()
    assert child == bridge
    assert child["error"] is None
    assert (
        len(
            [
                row
                for row in child["registrations"].values()
                if row["type"] == "aws:ecs/taskDefinition:TaskDefinition"
            ]
        )
        == 2
    )
    assert not any(
        row["type"].startswith("aws:iam/") for row in child["registrations"].values()
    )


@pytest.mark.parametrize(
    "mutation,error",
    [
        ("config", "workload-config-binding"),
        ("cli", "workload-isolated-child-required"),
    ],
)
def test_generated_child_rejects_config_substitution_and_cli_selection_before_aws(
    tmp_path, mutation, error
):
    child = graph(tmp_path, "generated-child", mutation)
    assert child["error"] == error
    assert not any(
        row["type"].startswith("aws:") for row in child["registrations"].values()
    )


def test_plain_python_launcher_cannot_execute_generated_child(tmp_path):
    program = tmp_path / "__main__.py"
    program.write_text(module.workload_program_source(projection()))
    result = subprocess.run(
        [sys.executable, str(program)],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode != 0
    assert "workload-isolated-child-required" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert result.stdout == ""


def test_direct_module_cli_cannot_select_workload():
    result = subprocess.run(
        [sys.executable, module.__file__, "--phase", "workload"],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode != 0
    assert result.stderr.strip() == "workload-internal-entrypoint-required"
    assert result.stdout == ""
    with pytest.raises(SystemExit, match="workload-internal-entrypoint-required"):
        runpy.run_path(module.__file__, run_name="__main__")


def test_future_wrapper_preserves_native_pulumi_argv_and_pins_isolation(monkeypatch):
    import os

    script = module.workload_python_wrapper_source()
    assert script.startswith("#!/opt/service-runtime/bin/python -I\n")
    args = [
        "/trusted/workload-python",
        "-u",
        "/usr/local/bin/pulumi-language-python-exec",
        "--monitor",
        "127.0.0.1:1234",
        "--project",
        "user-service-infrastructure",
        "--stack",
        "test",
        "/protected/pulumi",
    ]
    monkeypatch.setattr(sys, "argv", args)
    observed = []
    monkeypatch.setattr(
        os, "execv", lambda executable, argv: observed.append((executable, argv))
    )
    exec(compile(script, "/trusted/workload-python", "exec"), {"__name__": "__main__"})
    assert observed == [
        (
            "/opt/service-runtime/bin/python",
            ["/opt/service-runtime/bin/python", "-I", *args[1:]],
        )
    ]
