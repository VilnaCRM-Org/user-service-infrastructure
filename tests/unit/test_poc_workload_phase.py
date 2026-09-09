"""Executable mock registrations prove source ownership, not a native state plan."""

import asyncio
import copy
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from coverage import Coverage, CoverageData

ROOT = Path(__file__).resolve().parents[2]
TAGS = {
    "Project": "user-service-infrastructure",
    "Environment": "test",
    "Owner": "team-user-service",
    "CostCenter": "core",
    "DataClassification": "internal",
    "Criticality": "high",
    "RetentionClass": "standard",
}
REGISTRIES = {
    kind: {
        "logical_name": f"user-service-{kind}-repository",
        "name": f"user-service-test-{kind}",
    }
    for kind in ("web", "worker")
}


def _mutate(value, registries, mutation):
    if mutation == "type":
        return None
    if mutation == "registries":
        registries["web"]["name"] = "foreign"
    if mutation in (
        "environment",
        "region",
        "service_name",
        "owner",
        "cost_center",
        "stack_tag",
    ):
        return replace(value, **{mutation: "foreign"})
    changes = {
        "preview": {"deployment_mode": "preview"},
        "tags": {
            "default_tags": {
                key: val for key, val in TAGS.items() if key != "Criticality"
            }
        },
        "images": {"images": replace(value.images, web_repository_name="foreign")},
        "role": {"runtime": replace(value.runtime, task_role_arn="foreign")},
        "runtime": {"runtime": replace(value.runtime, app_env="dev")},
    }
    return replace(value, **changes.get(mutation, {}))


def _probe(root, mode, mutation, coverage_path):
    """Run both actual component compositions in independent Python runtimes."""
    sys.path[:0] = [str(root / "pulumi"), str(root / "tests/unit")]
    coverage = Coverage(
        config_file=False,
        branch=True,
        include=[
            str(root / "pulumi/app/workload_phase.py"),
            str(root / "pulumi/app/registry_phase.py"),
        ],
        data_file=str(coverage_path),
    )
    coverage.start()
    from app.environment import resolve_stack_settings
    from app.registry_phase import RegistryPhaseStack
    from app.workload_phase import WorkloadPhaseStack
    from pulumi.runtime import mocks, rpc, set_all_config, settings, stack
    from test_environment_component import SimpleMocks

    registrations, outputs = {}, {}

    class Monitor(mocks.MockMonitor):
        def RegisterResource(self, request):
            result = super().RegisterResource(request)
            registrations[request.name] = {
                "urn": result.urn,
                "id": result.id,
                "parent": request.parent,
                "provider": request.provider,
                "type": request.type,
                "custom": request.custom,
                "inputs": rpc.deserialize_properties(request.object),
            }
            return result

        def RegisterResourceOutputs(self, request):
            outputs[request.urn] = rpc.deserialize_properties(request.outputs)
            return super().RegisterResourceOutputs(request)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    recorder = SimpleMocks()
    mocks.set_mocks(
        recorder,
        project="user-service-infrastructure",
        stack="test",
        monitor=Monitor(recorder),
    )
    config = {
        "environment": "test",
        "serviceName": "user-service-infrastructure",
        "owner": "team-user-service",
        "costCenter": "core",
        "deploymentMode": "preview",
        "repoSlug": "user-service-infrastructure",
        "pulumiBackendUrl": "s3://pulumi-user-service-infrastructure-test-state",
        "pulumiSecretsProvider": "awskms://alias/pulumi-user-service-infrastructure-test-secrets?region=eu-central-1",
        "webRepositoryName": "user-service-test-web",
        "workerRepositoryName": "user-service-test-worker",
        "executionRoleArn": (
            "arn:aws:iam::891377212104:role/"
            "user-service-infrastructure-test-EcsExecution"
        ),
        "taskRoleArn": (
            "arn:aws:iam::891377212104:role/user-service-infrastructure-test-EcsTask"
        ),
        "appEnv": "prod",
    }
    aws_config = {
        "region": "eu-central-1",
        "allowedAccountIds": '["891377212104"]',
        "skipCredentialsValidation": "false",
        "skipRegionValidation": "false",
        "skipRequestingAccountId": "false",
    }
    set_all_config(
        {
            **{
                f"user-service-infrastructure:{key}": value
                for key, value in config.items()
            },
            **{f"aws:{key}": value for key, value in aws_config.items()},
        }
    )

    def program():
        if mode == "registry":
            RegistryPhaseStack(registries=copy.deepcopy(REGISTRIES))
            return
        # Pure metadata fixture avoids constructing a second EnvironmentSettings.
        metadata = SimpleNamespace(
            environment_name="test",
            service_name_value="user-service-infrastructure",
            owner="team-user-service",
            cost_center="core",
        )
        value = resolve_stack_settings(metadata)
        value = replace(
            value,
            deployment_mode="managed",
            default_tags=dict(TAGS),
            runtime=replace(
                value.runtime, access_logs_bucket_name="synthetic-test-access-logs"
            ),
        )
        registries = copy.deepcopy(REGISTRIES)
        value = _mutate(value, registries, mutation)
        WorkloadPhaseStack(settings=value, registries=registries)

    error = None
    try:
        loop.run_until_complete(stack.run_pulumi_func(program))
    except ValueError as exc:
        error = str(exc)
    loop.run_until_complete(asyncio.sleep(0))
    # Secrets in this fixture are explicitly synthetic preview values; do not
    # reuse this recorder as a live checkpoint or native ownership attestation.
    print(
        json.dumps(
            {
                "registrations": registrations,
                "outputs": outputs,
                "error": error,
                "aws_config": aws_config,
            },
            default=str,
        )
    )
    settings.reset_options(project=None, stack=None)
    loop.close()
    coverage.stop()
    coverage.save()


def graph(tmp_path, mode="workload", mutation="none"):
    coverage_path = tmp_path / f"{mode}-{mutation}.coverage"
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            __file__,
            "probe",
            str(ROOT),
            mode,
            mutation,
            str(coverage_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
        env={
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("COV_CORE_", "COVERAGE_"))
        },
    )
    assert result.returncode == 0, result.stderr
    if active := Coverage.current():
        child = CoverageData(basename=str(coverage_path))
        child.read()
        active.get_data().update(child)
    return json.loads(result.stdout)


def test_workload_extends_actual_registry_registrations_without_changing_baseline(
    tmp_path,
):
    before, after = graph(tmp_path, "registry"), graph(tmp_path)
    assert before["error"] is after["error"] is None
    baseline, workload = before["registrations"], after["registrations"]
    assert set(baseline) == {
        "user-service-infrastructure-test",
        "environment-settings",
        "user-service",
        "registries",
        "user-service-web-repository",
        "user-service-worker-repository",
    }
    assert {name: workload[name] for name in baseline} == baseline
    assert all(
        after["outputs"][urn] == value for urn, value in before["outputs"].items()
    )
    assert after["aws_config"] == before["aws_config"]
    # MockMonitor omits the implicit AWS provider. No synthetic seventh record
    # is invented; native provider identity/no-change still needs a real preview.
    assert not any(row["type"] == "pulumi:providers:aws" for row in workload.values())
    assert all(row["provider"] == "" for row in workload.values())
    owner = baseline["user-service"]["urn"]
    for name in ("network", "data", "messaging", "compute"):
        assert workload[name]["parent"] == owner
    types = {row["type"] for row in workload.values()}
    assert {
        "aws:ec2/vpc:Vpc",
        "aws:docdb/cluster:Cluster",
        "aws:elasticache/replicationGroup:ReplicationGroup",
        "aws:sqs/queue:Queue",
        "aws:ecs/taskDefinition:TaskDefinition",
        "aws:lb/loadBalancer:LoadBalancer",
        "aws:cloudwatch/logGroup:LogGroup",
        "aws:secretsmanager/secret:Secret",
    } <= types
    assert not any(kind.startswith("aws:iam/") for kind in types)
    assert (
        sum(
            kind == "aws:ecr/repository:Repository"
            for kind in (row["type"] for row in workload.values())
        )
        == 2
    )
    for name in ("user-service-web-repository", "user-service-worker-repository"):
        assert workload[name]["inputs"]["tags"] == TAGS
    from app.workload_phase import TAGGABLE_TYPES

    for row in workload.values():
        if row["type"] in TAGGABLE_TYPES:
            assert row["inputs"]["tags"] == TAGS
        elif row["type"] != "aws:ecr/repository:Repository":
            assert "tags" not in row["inputs"]


@pytest.mark.parametrize(
    "mutation",
    [
        "preview",
        "type",
        "environment",
        "region",
        "service_name",
        "owner",
        "cost_center",
        "stack_tag",
        "tags",
        "registries",
        "images",
        "role",
        "runtime",
    ],
)
def test_bad_internal_settings_fail_before_any_aws_registration(tmp_path, mutation):
    receipt = graph(tmp_path, mutation=mutation)
    assert receipt["error"] is not None
    assert not any(
        row["type"].startswith("aws:") for row in receipt["registrations"].values()
    )
    assert set(receipt["registrations"]) <= {"user-service-infrastructure-test"}


def test_workload_tags_preserve_extra_fields_and_reject_baseline_conflicts():
    from app.workload_phase import _merge_tags

    assert _merge_tags({"Name": "workload", "Owner": TAGS["Owner"]}, TAGS) == {
        **TAGS,
        "Name": "workload",
    }
    for tags in ("unsupported", {"Owner": "foreign"}):
        with pytest.raises(ValueError, match="overrides preserved baseline tags"):
            _merge_tags(tags, TAGS)


if __name__ == "__main__":
    assert sys.argv[1] == "probe"
    _probe(Path(sys.argv[2]), sys.argv[3], sys.argv[4], Path(sys.argv[5]))
