"""State-managed workload secrets; descriptor validation is not AWS admission."""

from __future__ import annotations

import copy
from typing import Any

import pulumi_aws as aws
import pulumi_random as random
import pulumi_tls as tls

import pulumi

RANDOM_VERSION = "4.19.2"
TLS_VERSION = "5.3.1"
DERIVED = frozenset({"document_db_url", "redis_url"})
ENVIRONMENT_NAMES = {
    "document_db_url": "MONGODB_URL",
    "redis_url": "REDIS_URL",
    # Environment variable identifiers, not secret material.
    "app_secret": "APP_SECRET",  # nosec B105
    "oauth_encryption_key": "OAUTH_ENCRYPTION_KEY",
    "oauth_passphrase": "OAUTH_PASSPHRASE",  # nosec B105
    "two_factor_encryption_key": "TWO_FACTOR_ENCRYPTION_KEY",
    "oauth_private_key": "OAUTH_PRIVATE_KEY_PEM",
    "oauth_public_key": "OAUTH_PUBLIC_KEY_PEM",
}


class RuntimeSecretsDescriptor:
    """Copy a complete locally validated declaration, without claiming approval."""

    def __init__(self, contract: dict[str, Any]) -> None:
        self._contract = copy.deepcopy(contract)
        self.validate()

    def validate(self) -> None:
        """Revalidate at each resource entry, including callers of this constructor."""
        from poc_contract import _validate_document

        _validate_document(self._contract)
        if self._contract["phase"] != "workload":
            raise ValueError("Runtime secrets require a workload declaration")

    def validate_context(self) -> None:
        """Reject a descriptor targeting another protected Pulumi project or account."""
        self.validate()
        expected = self._contract
        if (
            pulumi.get_project() != expected["backend"]["project"]
            or pulumi.get_stack() != expected["backend"]["stack"]
            or pulumi.Config("aws").require("region") != expected["region"]
            or pulumi.Config("aws").get_object("allowedAccountIds")
            != [expected["account_id"]]
        ):
            raise ValueError("Runtime secrets differ from protected deployment context")

    @property
    def references(self) -> dict[str, dict[str, str]]:
        """Return a detached copy of the exact ten declared secret identities."""
        return copy.deepcopy(
            self._contract["workload"]["secret_lifecycle"]["references"]
        )

    @property
    def mail_sender(self) -> str:
        """Return the declared sender; identity verification remains external."""
        return self._contract["workload"]["external"]["mail"]["sender"]

    @property
    def mailer_dsn(self) -> str:
        """Derive a credential-free SES API endpoint from the closed region."""
        return f"ses+api://default?region={self._contract['region']}"

    def validate_target(self, settings: Any) -> None:
        """Bind declarations to protected configuration and workload roles."""
        self.validate_context()
        central = self._contract["workload"]["central"]
        actual = (
            settings.environment,
            settings.region,
            settings.runtime.execution_role_arn,
            settings.runtime.task_role_arn,
            settings.runtime.mail_sender,
            settings.images.web_repository_name,
            settings.images.worker_repository_name,
            pulumi.Config("aws").get_object("allowedAccountIds"),
        )
        expected = (
            self._contract["environment"],
            self._contract["region"],
            central["execution_role_arn"],
            central["task_role_arn"],
            self.mail_sender,
            self._contract["registries"]["web"]["name"],
            self._contract["registries"]["worker"]["name"],
            [self._contract["account_id"]],
        )
        if actual != expected:
            raise ValueError("Runtime secret declaration differs from workload target")


class RuntimeSecrets(pulumi.ComponentResource):
    """Generate once in provider state, then persist exact named AWS versions."""

    def __init__(
        self,
        name: str,
        *,
        descriptor: RuntimeSecretsDescriptor,
        opts: pulumi.ResourceOptions | None = None,
    ) -> None:
        if type(descriptor) is not RuntimeSecretsDescriptor:
            raise ValueError("Runtime secrets require a validated descriptor")
        descriptor.validate_context()
        self.descriptor = RuntimeSecretsDescriptor(descriptor._contract)
        self.references = self.descriptor.references
        self.secret_arns: dict[str, pulumi.Output[str]] = {}
        self.version_ids: dict[str, pulumi.Output[str]] = {}
        super().__init__(
            "user-service-infrastructure:secrets:Runtime", name, None, opts
        )
        self.values = self._generate()
        for purpose, value in self.values.items():
            self._persist(purpose, value)

    def _generator_options(
        self, version: str, outputs: list[str]
    ) -> pulumi.ResourceOptions:
        """Pin providers and mark material secret in the existing encrypted state."""
        return pulumi.ResourceOptions(
            parent=self,
            version=version,
            protect=True,
            additional_secret_outputs=outputs,
        )

    def _generate(self) -> dict[str, pulumi.Output[str]]:
        """Keep identities and generation parameters independent of releases."""
        values = {}
        for purpose in ("document_db_password", "redis_auth_token"):
            password = random.RandomPassword(
                f"runtime-{purpose}-material",
                length=48,
                special=False,
                min_lower=1,
                min_upper=1,
                min_numeric=1,
                opts=self._generator_options(RANDOM_VERSION, ["result", "bcryptHash"]),
            )
            values[purpose] = password.result
        for purpose in (
            "app_secret",
            "oauth_encryption_key",
            "oauth_passphrase",
            "two_factor_encryption_key",
        ):
            material = random.RandomBytes(
                f"runtime-{purpose}-material",
                length=32,
                opts=self._generator_options(RANDOM_VERSION, ["base64", "hex"]),
            )
            values[purpose] = (
                material.base64
                if purpose == "two_factor_encryption_key"
                else material.hex
            )
        key = tls.PrivateKey(
            "runtime-oauth-key",
            algorithm="RSA",
            rsa_bits=4096,
            opts=self._generator_options(
                TLS_VERSION,
                [
                    "privateKeyPem",
                    "privateKeyPemPkcs8",
                    "privateKeyOpenssh",
                ],
            ),
        )
        values["oauth_private_key"] = key.private_key_pem
        values["oauth_public_key"] = pulumi.Output.secret(key.public_key_pem)
        return values

    def _persist(self, purpose: str, value: pulumi.Input[str]) -> pulumi.Output[str]:
        """Persist one named secret/version without exporting its material."""
        declaration = self.references[purpose]
        secret = aws.secretsmanager.Secret(
            f"runtime-{purpose}",
            name=declaration["name"],
            kms_key_id=declaration["kms_key_arn"],
            opts=pulumi.ResourceOptions(parent=self, protect=True),
        )
        version = aws.secretsmanager.SecretVersion(
            f"runtime-{purpose}-version",
            secret_id=secret.id,
            secret_string=pulumi.Output.secret(value),
            opts=pulumi.ResourceOptions(
                parent=self, protect=True, additional_secret_outputs=["secretString"]
            ),
        )
        self.secret_arns[purpose] = secret.arn
        self.version_ids[purpose] = version.version_id
        return secret.arn

    def persist_url(self, purpose: str, value: pulumi.Input[str]) -> pulumi.Output[str]:
        """Complete endpoint-dependent declarations using generated credentials."""
        if purpose not in DERIVED or purpose in self.secret_arns:
            raise ValueError("Runtime derived secret purpose is invalid or duplicated")
        return self._persist(purpose, value)

    def ecs_secrets(self) -> list[dict[str, pulumi.Input[str]]]:
        """Inject eight version-pinned values through nine environment names."""
        if set(self.secret_arns) != set(self.references):
            raise ValueError("Runtime secret inventory is incomplete")
        return [
            {
                "name": name,
                "valueFrom": pulumi.Output.concat(
                    self.secret_arns[purpose], ":::", self.version_ids[purpose]
                ),
            }
            for purpose, name in (
                *ENVIRONMENT_NAMES.items(),
                ("redis_url", "REDIS_LOCKOUT_URL"),
            )
        ]

    def complete(self) -> None:
        """Export only metadata after both derived secrets have been registered."""
        self.ecs_secrets()
        self.register_outputs(
            {"secretArns": self.secret_arns, "versionIds": self.version_ids}
        )
