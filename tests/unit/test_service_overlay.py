"""The overlay preserves dev metadata and closes trusted service runtime references."""

from __future__ import annotations

import re
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("environment", ["dev", "test", "prod"])
def test_program_preserves_existing_component_and_requires_shared_config(
    monkeypatch, environment
):
    exports = {}
    created = []
    values = {
        "environment": environment,
        "repoSlug": "user-service-infrastructure",
        "pulumiBackendUrl": "s3://review-fixture",
        "pulumiSecretsProvider": "awskms://review-fixture",
        "awsAccountId": "891377212104" if environment != "prod" else "933245420672",
    }
    settings = SimpleNamespace(
        environment=environment,
        service_name="user-service-infrastructure",
        stack_tag="service-test",
        default_tags={},
    )

    def component(name):
        created.append(name)
        return settings

    class Config:
        def get(self, name):
            return values.get(name)

        def require(self, name):
            return values[name]

    monkeypatch.setitem(
        sys.modules, "app", SimpleNamespace(EnvironmentSettings=component)
    )
    monkeypatch.setitem(
        sys.modules,
        "pulumi",
        SimpleNamespace(
            Config=Config,
            get_stack=lambda: environment,
            export=lambda key, value: exports.__setitem__(key, value),
        ),
    )

    def caller():
        assert environment != "dev", "Development metadata must not call AWS"
        return SimpleNamespace(account_id=values["awsAccountId"])

    monkeypatch.setitem(
        sys.modules, "pulumi_aws", SimpleNamespace(get_caller_identity=caller)
    )
    runpy.run_path(str(ROOT / "pulumi/__main__.py"))
    assert created == ["environment-settings"]
    assert {"environment", "serviceName", "stackTag", "defaultTags"} <= exports.keys()
    if environment == "dev":
        assert len(exports) == 4
    else:
        assert {
            key: exports[key]
            for key in ("repoSlug", "pulumiBackendUrl", "pulumiSecretsProvider")
        } == {
            key: values[key]
            for key in ("repoSlug", "pulumiBackendUrl", "pulumiSecretsProvider")
        }


@pytest.mark.parametrize(
    "environment,expected,actual",
    [
        ("test", "891377212104", "933245420672"),
        ("prod", "933245420672", "891377212104"),
    ],
)
def test_shared_program_rejects_wrong_caller_before_component_or_exports(
    monkeypatch, environment, expected, actual
):
    values = {"environment": environment, "awsAccountId": expected}

    class Config:
        def get(self, name):
            return values.get(name)

        def require(self, name):
            return values[name]

    monkeypatch.setitem(
        sys.modules,
        "app",
        SimpleNamespace(
            EnvironmentSettings=lambda _name: pytest.fail(
                "Wrong account created component"
            )
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "pulumi",
        SimpleNamespace(
            Config=Config,
            get_stack=lambda: environment,
            export=lambda *_args: pytest.fail("Wrong account exported outputs"),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "pulumi_aws",
        SimpleNamespace(get_caller_identity=lambda: SimpleNamespace(account_id=actual)),
    )
    with pytest.raises(ValueError, match="configured awsAccountId"):
        runpy.run_path(str(ROOT / "pulumi/__main__.py"))


@pytest.mark.parametrize(
    "stack,environment",
    [
        ("test", "dev"),
        ("prod", "dev"),
        ("test", "prod"),
        ("prod", "test"),
        ("dev", "test"),
        ("dev", "prod"),
        ("test", None),
    ],
)
def test_selected_shared_stack_cannot_skip_guard_via_environment(
    monkeypatch, stack, environment
):
    class Config:
        def get(self, _name):
            return environment

    def rejected(*_args):
        pytest.fail("Mismatched stack/environment reached runtime or AWS")

    monkeypatch.setitem(
        sys.modules, "app", SimpleNamespace(EnvironmentSettings=rejected)
    )
    monkeypatch.setitem(
        sys.modules,
        "pulumi",
        SimpleNamespace(Config=Config, get_stack=lambda: stack, export=rejected),
    )
    monkeypatch.setitem(
        sys.modules, "pulumi_aws", SimpleNamespace(get_caller_identity=rejected)
    )
    with pytest.raises(ValueError, match="selected shared stack"):
        runpy.run_path(str(ROOT / "pulumi/__main__.py"))


def test_new_workflows_resolve_local_helpers_and_use_pinned_actions():
    makefile = (ROOT / "Makefile").read_text()
    for name in (
        "self-deploy",
        "initialize-stack",
        "pulumi-pr-commands",
        "governance-promotion",
    ):
        document = yaml.safe_load((ROOT / f".github/workflows/{name}.yml").read_text())
        for job in document["jobs"].values():
            for step in job.get("steps", []):
                uses = step.get("uses", "")
                if uses.startswith("./"):
                    relative = uses.removeprefix("./").removeprefix(".trusted/")
                    assert (ROOT / relative / "action.yml").is_file()
                elif uses:
                    assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", uses)
                run = step.get("run", "")
                for helper in re.findall(r"(?:\./)?scripts/[a-z_]+\.py", run):
                    assert (ROOT / helper).is_file()
                for target in re.findall(r"^make ([a-z-]+)$", run, re.M):
                    assert re.search(rf"^{target}:", makefile, re.M)
    loader = (ROOT / ".github/actions/load-aws-ci-env/action.yml").read_text()
    assert "python3 -I" in loader
    assert "CI_CONFIG_ACTION_PATH" in loader


def test_compose_forwards_fixed_identity_and_shared_backend_pins():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    actual = set(compose["services"]["pulumi"]["environment"])
    assert {
        "AWS_ACCOUNT_ID",
        "AWS_SESSION_TOKEN",
        "PULUMI_BACKEND_URL",
        "PULUMI_SECRETS_PROVIDER",
        "PULUMI_EXPECTED_SHA",
        "PULUMI_COMMIT_SHA",
        "PULUMI_PREVIEW_STACKS",
        "INIT_ACCOUNT_ID",
        "INIT_ENVIRONMENT",
        "GITHUB_REF",
        "GITHUB_REPOSITORY",
    } <= actual
    assert "PULUMI_CONFIG_PASSPHRASE" not in actual
    assert "PULUMI_ACCESS_TOKEN" not in actual
    assert not any(
        volume["target"].endswith("/.aws")
        for volume in compose["services"]["pulumi"]["volumes"]
    )
