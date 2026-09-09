"""Offline resource-graph checks for the proposed registry owner."""

import asyncio
import functools
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import NoReturn

from app.registry import RegistryInputs, RegistryPlane
from coverage import Coverage, CoverageData
from pulumi.runtime import mocks, settings, stack

import pulumi


def registry_inputs() -> RegistryInputs:
    """Return synthetic physical names and the existing compute child names."""
    return {
        "web": {
            "logical_name": "user-service-web-repository",
            "name": "synthetic-poc-web",
        },
        "worker": {
            "logical_name": "user-service-worker-repository",
            "name": "synthetic-poc-worker",
        },
    }


class RegistryMocks(mocks.Mocks):
    """Record every resource and reject unexpected provider invokes."""

    def __init__(self) -> None:
        """Start an empty registration inventory."""
        self.resources: list[mocks.MockResourceArgs] = []
        self.urns: list[str] = []

    def new_resource(self, args: mocks.MockResourceArgs) -> tuple[str, dict]:
        """Emit distinguishable provider values, never echo declared ARN/URI."""
        self.resources.append(args)
        outputs = dict(args.inputs)
        if args.typ == "aws:ecr/repository:Repository":
            outputs["arn"] = f"observed-arn:{args.name}"
            outputs["repositoryUrl"] = f"observed-uri:{args.name}"
        return f"{args.name}-id", outputs

    def call(self, args: mocks.MockCallArgs) -> NoReturn:
        """Forbid metadata discovery or any other invoke in this component."""
        raise AssertionError(f"Unexpected invoke: {args.token}")


def run_program(program: Callable[[], None]) -> RegistryMocks:
    """Resolve all registrations/outputs with no CLI, credentials or network."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    recorder = RegistryMocks()

    async def invoke() -> None:
        settings.reset_options(project=None, stack=None)
        monitor = mocks.MockMonitor(recorder)
        mocks.set_mocks(
            recorder,
            project="user-service-infrastructure",
            stack="test",
            monitor=monitor,
        )
        await stack.run_pulumi_func(program)
        await asyncio.sleep(0)
        recorder.urns = sorted(monitor.resources)

    try:
        loop.run_until_complete(invoke())
    finally:
        settings.reset_options(project=None, stack=None)
        loop.close()
        asyncio.set_event_loop(None)
    return recorder


def isolated(test):
    """Keep each Pulumi mock runtime separate from pytest's active root future."""

    @functools.wraps(test)
    def invoke():
        if os.environ.get("POC_REGISTRY_COMPONENT_CHILD") == "1":
            return test()
        root = Path(__file__).resolve().parents[2]
        with TemporaryDirectory(prefix="registry-component-test-") as directory:
            data = Path(directory) / "coverage"
            code = (
                "import runpy, sys\nfrom coverage import Coverage\n"
                f"sys.path.insert(0, {str(root / 'pulumi')!r})\n"
                "coverage = Coverage(config_file=False, branch=True, "
                f"data_file={str(data)!r}, "
                f"include=[{str(root / 'pulumi/app/registry.py')!r}])\n"
                "coverage.start()\n"
                f"runpy.run_path({__file__!r})[{test.__name__!r}]()\n"
                "coverage.stop(); coverage.save()\n"
            )
            result = subprocess.run(
                [sys.executable, "-I", "-c", code],
                capture_output=True,
                text=True,
                timeout=30,
                env={
                    **{
                        key: value
                        for key, value in os.environ.items()
                        if not key.startswith(("COV_CORE_", "COVERAGE_"))
                    },
                    "POC_REGISTRY_COMPONENT_CHILD": "1",
                },
            )
            assert result.returncode == 0, result.stderr
            active = Coverage.current()
            if active is not None:
                child = CoverageData(basename=str(data))
                child.read()
                active.get_data().update(child)

    return invoke


@isolated
def test_registry_graph_is_only_two_repos() -> None:
    """No IAM, secret, network, data or compute resources accompany registries."""

    def program() -> None:
        RegistryPlane("registries", registries=registry_inputs())

    recorder = run_program(program)
    custom = [resource for resource in recorder.resources if resource.custom]
    assert len(custom) == 2
    assert {resource.typ for resource in custom} == {"aws:ecr/repository:Repository"}
    assert {resource.name for resource in custom} == {
        "user-service-web-repository",
        "user-service-worker-repository",
    }
    assert {resource.inputs["name"] for resource in custom} == {
        "synthetic-poc-web",
        "synthetic-poc-worker",
    }
    for resource in custom:
        assert resource.inputs["imageTagMutability"] == "IMMUTABLE"
        assert resource.inputs["forceDelete"] is False
        assert resource.inputs["imageScanningConfiguration"] == {"scanOnPush": True}


@isolated
def test_registry_outputs_are_provider_values() -> None:
    """A declaration cannot masquerade as the actual registered resource output."""
    observed: list[str] = []

    def program() -> None:
        plane = RegistryPlane("registries", registries=registry_inputs())
        for output in (
            plane.outputs.web.arn,
            plane.outputs.web.uri,
            plane.outputs.worker.arn,
            plane.outputs.worker.uri,
        ):
            pulumi.Output.apply(output, observed.append)

    run_program(program)
    assert sorted(observed) == sorted(
        [
            "observed-arn:user-service-web-repository",
            "observed-uri:user-service-web-repository",
            "observed-arn:user-service-worker-repository",
            "observed-uri:user-service-worker-repository",
        ]
    )


@isolated
def test_consumer_keeps_registry_owner() -> None:
    """Adding an output-only consumer does not create or reparent repositories."""
    identities: list[list[str]] = []
    counts = []
    for with_consumer in (False, True):

        def program() -> None:
            owner = pulumi.ComponentResource(
                "user-service-infrastructure:stack:UserService", "user-service"
            )
            plane = RegistryPlane(
                "registries",
                registries=registry_inputs(),
                opts=pulumi.ResourceOptions(parent=owner),
            )
            if with_consumer:
                consumer = pulumi.ComponentResource(
                    "synthetic:consumer:References",
                    "consumer",
                    None,
                    pulumi.ResourceOptions(parent=owner),
                )
                consumer.register_outputs({"webImageRepository": plane.outputs.web.uri})

        recorder = run_program(program)
        counts.append(len([row for row in recorder.resources if row.custom]))
        identities.append([urn for urn in recorder.urns if "$aws:ecr/" in urn])
    assert counts == [2, 2]
    assert identities[0] == identities[1]
    assert len(identities[0]) == 2
    assert all(
        ":registry:Plane$aws:ecr/repository:Repository::" in urn
        for urn in identities[0]
    )
    assert all(":compute:Plane$" not in urn for urn in identities[0])
