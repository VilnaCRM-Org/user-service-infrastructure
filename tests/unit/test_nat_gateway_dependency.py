"""Verify NAT gateways wait for the public Internet Gateway."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import pulumi_aws as aws
import pytest
from app.network import NetworkPlane
from pulumi.runtime import mocks, settings, stack

import pulumi


class NetworkMocks(mocks.Mocks):
    """Echo declared inputs while recording the managed resource graph."""

    def new_resource(self, args: mocks.MockResourceArgs) -> tuple[str, dict]:
        """Return deterministic provider-shaped IDs without cloud access."""
        return f"{args.name}-id", dict(args.inputs)

    def call(self, args: mocks.MockCallArgs) -> dict:
        """Keep this resource-only test independent of provider invokes."""
        return args.inputs


def _settings(zones: tuple[str, ...]) -> object:
    """Build the small managed settings surface NetworkPlane reads."""
    cidrs = tuple(f"10.42.{index}.0/24" for index, _ in enumerate(zones))
    return SimpleNamespace(
        is_managed=True,
        stack_tag="unit",
        network=SimpleNamespace(
            vpc_cidr="10.42.0.0/16",
            availability_zones=zones,
            public_subnet_cidrs=cidrs,
            app_subnet_cidrs=tuple(
                f"10.42.{index + 10}.0/24" for index, _ in enumerate(zones)
            ),
            data_subnet_cidrs=tuple(
                f"10.42.{index + 20}.0/24" for index, _ in enumerate(zones)
            ),
        ),
        capacity=SimpleNamespace(container_port=8080),
        documentdb=SimpleNamespace(port=27017),
        redis=SimpleNamespace(port=6379),
    )


def _run(program) -> None:
    """Run a component program against Pulumi's in-process resource monitor."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        monitor = mocks.MockMonitor(NetworkMocks())
        mocks.set_mocks(
            NetworkMocks(),
            project="user-service-infrastructure",
            stack="unit",
            monitor=monitor,
        )
        loop.run_until_complete(stack.run_pulumi_func(program))
        loop.run_until_complete(asyncio.sleep(0))
    finally:
        settings.reset_options(project=None, stack=None)
        loop.close()
        asyncio.set_event_loop(None)


@pytest.mark.parametrize(
    "zones",
    [
        ("eu-central-1a",),
        ("eu-central-1a", "eu-central-1b"),
    ],
)
def test_public_nat_gateways_depend_on_internet_gateway(zones: tuple[str, ...]) -> None:
    """Each public NAT keeps its component parent and waits for the one IGW."""
    internet_gateways: list[aws.ec2.InternetGateway] = []
    nat_options: list[pulumi.ResourceOptions] = []
    plane: NetworkPlane | None = None
    original_gateway = aws.ec2.InternetGateway
    original_nat = aws.ec2.NatGateway

    def capture_gateway(*args, **kwargs):
        gateway = original_gateway(*args, **kwargs)
        internet_gateways.append(gateway)
        return gateway

    def capture_nat(*args, **kwargs):
        nat_options.append(kwargs["opts"])
        return original_nat(*args, **kwargs)

    def program() -> None:
        nonlocal plane
        plane = NetworkPlane(
            "network",
            settings=cast(object, _settings(zones)),
        )

    with (
        patch("app.network.aws.ec2.InternetGateway", side_effect=capture_gateway),
        patch("app.network.aws.ec2.NatGateway", side_effect=capture_nat),
    ):
        _run(program)

    assert len(internet_gateways) == 1
    assert len(nat_options) == len(zones)
    assert plane is not None
    for options in nat_options:
        assert options.parent is plane
        assert options.provider is None
        assert options.depends_on == [internet_gateways[0]]
