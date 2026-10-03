"""Workload secret declarations; descriptor validation is not AWS admission.

A hardened (``workload_step``) projection declares seeded secret identities only:
no Random or TLS generator and no ``SecretVersion`` (AD-25 transition rule). The
pre-hardening projection keeps generating values in state until S4.10 removes it.

Step 2 (S1.6, FR-05, AD-06) adds, per rotated secret, the seed
``aws.lambda.Invocation`` of the reviewed BI function with the immutable input
``{secret_arn, purpose}`` and, after it, the ``SecretRotation`` on the D-5
90-day schedule with ``rotate_immediately=False``. Rotation configuration runs
``testSecret``, which needs the ``AWSCURRENT`` version the seed writes. The
seed is idempotent: on a secret that already has ``AWSCURRENT`` it returns
``noop`` and writes nothing. ``OAUTH_PASSPHRASE`` is never rotated (D-5).

Step 2 (S1.5, FR-07, AD-08) also gives every declared secret a
``SecretPolicy(block_public_policy=True)`` that denies ``GetSecretValue``
unless the execution or app-rotation role, and the writes unless the
app-rotation role. The DocumentDB-managed secret gets a ``SecretPolicy``
rendering the document of its contract state ``documentdb_secret_policy``.

S1.8 (FR-06, AD-03) retires the PEM, passphrase and 2FA purposes from the
hardened shape: it declares only ``app_secret`` and ``oauth_encryption_key``,
and the app reaches its JWT and 2FA KMS keys through ``kms_environment``.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
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


# D-5 (decided 2026-09-30): only these purposes rotate, every 90 days.
ROTATED_PURPOSES = frozenset({"app_secret", "oauth_encryption_key"})
ROTATION_SCHEDULE_DAYS = 90
# AD-06: the seed input and output are closed. ``CREATE_ONLY`` invokes the
# function only on create or replace, and a delete makes no call (V-18).
SEED_INPUT_KEYS = frozenset({"secret_arn", "purpose"})
SEED_OUTPUT_KEYS = frozenset({"secret_arn", "version_id", "status"})
SEED_STATUSES = frozenset({"seeded", "noop"})
SEED_LIFECYCLE_SCOPE = "CREATE_ONLY"


def rotation_schedule(purpose: str, rotation: Any) -> int:
    """Return the D-5 schedule of a rotated purpose; refuse any other rotation."""
    if purpose not in ROTATED_PURPOSES:
        raise ValueError("Only APP_SECRET and OAUTH_ENCRYPTION_KEY rotate (D-5)")
    if (
        type(rotation) is not dict
        or type(rotation.get("schedule_days")) is not int
        or rotation["schedule_days"] != ROTATION_SCHEDULE_DAYS
    ):
        raise ValueError("Secret rotation must run every 90 days (D-5)")
    return ROTATION_SCHEDULE_DAYS


def seed_input(contract: dict[str, Any], secret_arn: Any, purpose: str) -> str:
    """Serialize the immutable seed input, exactly ``{secret_arn, purpose}``.

    ``validate_seed_input`` binds the purpose to a rotated declaration and the
    ARN to its declared name, account and region (FR-09).
    """
    from poc_secret_observation import validate_seed_input

    seed = {"secret_arn": secret_arn, "purpose": purpose}
    validate_seed_input(contract, seed)
    return json.dumps(seed, sort_keys=True)


def _seed_document(result: Any) -> Any:
    """Parse one seed result; anything but a JSON string parses to ``None``."""
    try:
        return json.loads(result) if type(result) is str else None
    except ValueError:
        return None


def _closed_seed(document: Any, secret_arn: str) -> bool:
    """Report whether a parsed result is exactly the AD-06 output schema."""
    return (
        isinstance(document, Mapping)
        and set(document) == SEED_OUTPUT_KEYS
        and all(type(value) is str and value for value in document.values())
        and document["status"] in SEED_STATUSES
        and document["secret_arn"] == secret_arn
    )


def seed_result(
    result: Any, *, secret_arn: str, current_version_id: str | None = None
) -> dict[str, str]:
    """Check one seed result against the closed AD-06 output schema.

    The output is exactly ``{secret_arn, version_id, status}``, for the seeded
    secret, with ``status`` ``seeded`` or ``noop``. When the secret already had
    an ``AWSCURRENT`` version (``current_version_id``), the seed must return
    ``noop`` with that version: it writes nothing.
    """
    document = _seed_document(result)
    if not _closed_seed(document, secret_arn):
        raise ValueError("Seed result differs from {secret_arn, version_id, status}")
    if current_version_id is not None and (
        document["status"] != "noop" or document["version_id"] != current_version_id
    ):
        raise ValueError("Seed on a secret with AWSCURRENT must return noop")
    return dict(document)


# S1.5 (FR-07, AD-08): the resource policies only deny. Each allow-list is a
# list of exact role ARNs; a wildcard anywhere fails.
_ROLE_ARN = re.compile(r"arn:aws:iam::[0-9]{12}:role/[A-Za-z0-9+=,.@_/-]+")
READ_ACTIONS = ("secretsmanager:GetSecretValue",)
WRITE_ACTIONS = (
    "secretsmanager:PutSecretValue",
    "secretsmanager:UpdateSecretVersionStage",
)
DOCUMENTDB_SECRET_POLICY_STATES = (
    "deny-other-readers",
    "allow-rotation",
    "tls-only",
)


def _allow_list(roles: Any) -> list[str]:
    """Return a non-empty list of exact role ARNs; refuse ``*`` and empty."""
    if (
        type(roles) is not list
        or not roles
        or not all(type(role) is str and _ROLE_ARN.fullmatch(role) for role in roles)
    ):
        raise ValueError("A secret policy allow-list must name exact role ARNs")
    return [str(role) for role in roles]


def _deny(sid: str, actions: tuple[str, ...], condition: dict[str, Any]) -> dict:
    """Build one ``Deny`` statement for every principal (AD-08)."""
    return {
        "Sid": sid,
        "Effect": "Deny",
        "Principal": "*",
        "Action": list(actions),
        "Resource": "*",
        "Condition": condition,
    }


def _document(*statements: dict[str, Any]) -> str:
    """Serialize a resource policy document deterministically."""
    return json.dumps(
        {"Version": "2012-10-17", "Statement": list(statements)}, sort_keys=True
    )


def declared_secret_policy(
    read_allow: Any, write_allow: Any, *, execution_role_arn: str
) -> str:
    """Render the FR-07 policy of one USI-declared secret.

    Reads are denied unless ``aws:PrincipalArn`` is on ``read_allow`` (the
    execution and app-rotation roles); writes are denied unless it is on
    ``write_allow``, which must not hold the execution role.
    """
    readers = _allow_list(read_allow)
    writers = _allow_list(write_allow)
    if execution_role_arn in writers:
        raise ValueError("The write-deny allow-list must not hold the execution role")
    return _document(
        _deny(
            "DenyReadUnlessReviewedReader",
            READ_ACTIONS,
            {"StringNotEquals": {"aws:PrincipalArn": readers}},
        ),
        _deny(
            "DenyWriteUnlessAppRotation",
            WRITE_ACTIONS,
            {"StringNotEquals": {"aws:PrincipalArn": writers}},
        ),
    )


def managed_secret_policy(state: Any, *, bootstrap_job_role_arn: str) -> str:
    """Render the managed-secret document of one ``documentdb_secret_policy``.

    ``deny-other-readers`` denies reads unless the bootstrap-job role;
    ``allow-rotation`` keeps that deny but exempts AWS service principals, the
    managed rotation (V-3 docs); ``tls-only`` only denies reads without TLS.
    """
    readers = {"aws:PrincipalArn": _allow_list([bootstrap_job_role_arn])}
    if state == "deny-other-readers":
        condition: dict[str, Any] = {"StringNotEquals": readers}
    elif state == "allow-rotation":
        condition = {
            "StringNotEquals": readers,
            "Bool": {"aws:PrincipalIsAWSService": "false"},
        }
    elif state == "tls-only":
        return _document(
            _deny(
                "DenyReadWithoutTls",
                READ_ACTIONS,
                {"Bool": {"aws:SecureTransport": "false"}},
            )
        )
    else:
        raise ValueError("Unknown documentdb_secret_policy state")
    return _document(_deny("DenyReadUnlessBootstrapJob", READ_ACTIONS, condition))


# A secret ARN, optionally selecting a JSON key (`arn:key::`). Any version ID or
# staging label segment is refused so ECS always resolves AWSCURRENT.
_SECRET_REFERENCE = re.compile(
    r"arn:aws:secretsmanager:[a-z0-9-]+:[0-9]{12}:secret:[A-Za-z0-9/_+=.@-]+-[A-Za-z0-9]{6}"
    r"(?::[A-Za-z0-9_.-]+::)?"
)


def require_unversioned_reference(reference: Any) -> str:
    """Accept only the secret ARN or ``arn:key::``; reject versions and stages.

    This checks the reference shape only. It does not bind the declared name,
    account or region; ``ecs_secrets()`` (``_current_references``) fullmatches
    each reference against ``secret_arn_regex(...)`` for that.
    """
    if type(reference) is not str or not _SECRET_REFERENCE.fullmatch(reference):
        raise ValueError("Secret reference must not pin a version or staging label")
    return reference


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
    def hardened(self) -> bool:
        """Report the seeded shape, which only a ``workload_step`` contract has."""
        return "workload_step" in self._contract

    @property
    def workload_step(self) -> int:
        """Return the hardened step (FR-34); a pre-hardening contract has none."""
        return self._contract["workload_step"]

    @property
    def runtime_cmk_arn(self) -> str:
        """Return the D-4 runtime CMK from reviewed central metadata (S1.9).

        Only the hardened shape carries ``central.cmk``; the pre-hardening
        projection has none and raises (AD-25).
        """
        if not self.hardened:
            raise ValueError("The runtime CMK exists only on the hardened shape")
        return self._contract["workload"]["central"]["cmk"]["runtime"]["arn"]

    @property
    def rotation_function_arns(self) -> dict[str, str]:
        """Return the reviewed BI rotation function ARNs (S5.3, AD-05)."""
        return dict(self._contract["workload"]["central"]["rotation_function_arns"])

    @property
    def kms_environment(self) -> list[dict[str, str]]:
        """Return the AD-15 KMS key environment values (S1.8, FR-06).

        The app signs JWTs with the current key and verifies with both it and
        the optional verify-only ``cmk.jwt_previous`` key (D-17; empty when no
        key change is open). 2FA uses the symmetric 2FA key. Only key ARNs
        leave the contract, never key material. ``AWS_REGION``, the fourth
        AD-15 value, is already a hardened plain value (S1.4 Redis IAM).
        """
        cmk = self._contract["workload"]["central"]["cmk"]
        previous = cmk.get("jwt_previous", {}).get("arn", "")
        return [
            {"name": "JWT_KMS_KEY_ID", "value": cmk["jwt"]["arn"]},
            {"name": "JWT_KMS_PREVIOUS_KEY_ID", "value": previous},
            {"name": "TWO_FACTOR_KMS_KEY_ID", "value": cmk["two_factor"]["arn"]},
        ]

    @property
    def documentdb_secret_policy(self) -> str:
        """Return the managed-secret policy state (FR-07, AD-08)."""
        return self._contract["documentdb_secret_policy"]

    @property
    def central(self) -> dict[str, Any]:
        """Return a detached copy of the reviewed central metadata."""
        return copy.deepcopy(self._contract["workload"]["central"])

    @property
    def scaling(self) -> dict[str, Any]:
        """Return a detached copy of the hardened ``scaling`` block (AD-10)."""
        return copy.deepcopy(self._contract["scaling"])

    @property
    def references(self) -> dict[str, dict[str, Any]]:
        """Return a detached copy of the exact declared secret identities."""
        return copy.deepcopy(
            self._contract["workload"]["secret_lifecycle"]["references"]
        )

    @property
    def mail_sender(self) -> str:
        """Return the declared sender; native admission checks identity verification."""
        return self._contract["workload"]["external"]["mail"]["sender"]

    @property
    def mailer_dsn(self) -> str:
        """Derive a credential-free SES API endpoint from the closed region."""
        return f"ses+api://default?region={self._contract['region']}"

    @property
    def database_name(self) -> str:
        """Return the validated application database selected by the workload."""
        return self._contract["workload"]["runtime"]["database_name"]

    @property
    def ca_bundle_path(self) -> str:
        """Return the declared container path without claiming the file exists."""
        return self._contract["workload"]["runtime"]["ca_bundle_path"]

    @property
    def account_id(self) -> str:
        """Return the account bound to the protected deployment context."""
        return self._contract["account_id"]

    @property
    def worker_health_command(self) -> list[str]:
        """Return a detached copy of the validated worker health command."""
        return list(self._contract["workload"]["runtime"]["worker_health_command"])

    @property
    def trusted_proxy_cidrs(self) -> list[str]:
        """Return the exact declared ALB subnet networks, without serialization."""
        return list(self._contract["workload"]["runtime"]["trusted_proxy_cidrs"])

    def validate_target(self, settings: Any) -> None:
        """Bind declarations to protected configuration and workload roles."""
        self.validate_context()
        if set(self.trusted_proxy_cidrs) != set(settings.network.app_subnet_cidrs):
            raise ValueError("Trusted proxy CIDRs must exactly match the ALB subnets")
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
    """Declare named AWS secrets; only the pre-hardening shape generates values."""

    values: dict[str, pulumi.Output[str]]
    # Detached partial instances keep the pre-hardening completeness rule.
    _hardened = False

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
        self.seed_results: dict[str, pulumi.Output[dict[str, str]]] = {}
        self.rotations: list[aws.secretsmanager.SecretRotation] = []
        self.policies: list[aws.secretsmanager.SecretPolicy] = []
        super().__init__(
            "user-service-infrastructure:secrets:Runtime", name, None, opts
        )
        self._hardened = self.descriptor.hardened
        if self._hardened:
            # Values arrive from the reviewed seed outside Pulumi state.
            self.values = {}
            for purpose in self.references:
                secret = self._declare(purpose)
                if self.descriptor.workload_step != 2:
                    continue
                self._restrict(purpose, secret)
                # S1.8 left only rotated purposes; ``rotation_schedule``
                # refuses any other rotation entry (D-5).
                self._rotate(purpose, secret)
            if self.descriptor.workload_step == 2:
                self._restrict_managed()
        else:
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

    def _declare(self, purpose: str) -> aws.secretsmanager.Secret:
        """Register one protected named secret identity without any value."""
        declaration = self.references[purpose]
        secret = aws.secretsmanager.Secret(
            f"runtime-{purpose}",
            name=declaration["name"],
            kms_key_id=declaration["kms_key_arn"],
            opts=pulumi.ResourceOptions(parent=self, protect=True),
        )
        self.secret_arns[purpose] = secret.arn
        return secret

    def _restrict(self, purpose: str, secret: aws.secretsmanager.Secret) -> None:
        """Attach the FR-07 deny-only policy to one declared secret (AD-08)."""
        central = self.descriptor.central
        self.policies.append(
            aws.secretsmanager.SecretPolicy(
                f"runtime-{purpose}-policy",
                secret_arn=secret.arn,
                block_public_policy=True,
                policy=declared_secret_policy(
                    [central["execution_role_arn"], central["app_rotation_role_arn"]],
                    [central["app_rotation_role_arn"]],
                    execution_role_arn=central["execution_role_arn"],
                ),
                opts=pulumi.ResourceOptions(parent=self),
            )
        )

    def _restrict_managed(self) -> None:
        """Attach the managed-secret policy of the contract state (AD-08).

        The ARN arrives through XP-8 after step 1. ``protect`` keeps every
        apply mode from deleting it; only the TEST abandon removes it.
        """
        central = self.descriptor.central
        self.policies.append(
            aws.secretsmanager.SecretPolicy(
                "documentdb-managed-secret-policy",
                secret_arn=central["documentdb_managed_secret_arn"],
                block_public_policy=True,
                policy=managed_secret_policy(
                    self.descriptor.documentdb_secret_policy,
                    bootstrap_job_role_arn=central["bootstrap_job_role_arn"],
                ),
                opts=pulumi.ResourceOptions(parent=self, protect=True),
            )
        )

    def _rotate(self, purpose: str, secret: aws.secretsmanager.Secret) -> None:
        """Seed one rotated secret, then enable its rotation (AD-06 step 2).

        The seed input is exactly ``{secret_arn, purpose}``; its result must
        match the closed output schema. The rotation waits for the seed,
        because rotation configuration runs ``testSecret`` (AD-06).
        """
        rotation = self.references[purpose]["rotation"]
        days = rotation_schedule(purpose, rotation)
        function_arn = self.descriptor.rotation_function_arns[rotation["function_ref"]]
        seed = aws.lambda_.Invocation(
            f"runtime-{purpose}-seed",
            function_name=function_arn,
            input=secret.arn.apply(
                lambda arn: seed_input(self.descriptor._contract, arn, purpose)
            ),
            lifecycle_scope=SEED_LIFECYCLE_SCOPE,
            opts=pulumi.ResourceOptions(parent=self),
        )
        self.seed_results[purpose] = pulumi.Output.all(seed.result, secret.arn).apply(
            lambda values: seed_result(values[0], secret_arn=values[1])
        )
        self.rotations.append(
            aws.secretsmanager.SecretRotation(
                f"runtime-{purpose}-rotation",
                secret_id=secret.id,
                rotation_lambda_arn=function_arn,
                rotation_rules={"automatically_after_days": days},
                rotate_immediately=False,
                opts=pulumi.ResourceOptions(parent=self, depends_on=[seed]),
            )
        )

    def _persist(self, purpose: str, value: pulumi.Input[str]) -> pulumi.Output[str]:
        """Persist one named secret/version without exporting its material."""
        secret = self._declare(purpose)
        version = aws.secretsmanager.SecretVersion(
            f"runtime-{purpose}-version",
            secret_id=secret.id,
            secret_string=pulumi.Output.secret(value),
            opts=pulumi.ResourceOptions(
                parent=self, protect=True, additional_secret_outputs=["secretString"]
            ),
        )
        self.version_ids[purpose] = version.version_id
        return secret.arn

    def persist_url(self, purpose: str, value: pulumi.Input[str]) -> pulumi.Output[str]:
        """Complete endpoint-dependent declarations using generated credentials."""
        if (
            purpose not in DERIVED
            or purpose in self.secret_arns
            or purpose not in self.references
        ):
            raise ValueError("Runtime derived secret purpose is invalid or duplicated")
        return self._persist(purpose, value)

    def ecs_secrets(self) -> list[dict[str, pulumi.Input[str]]]:
        """Inject secrets by ARN (AWSCURRENT); pre-hardening stays version-pinned."""
        if self._hardened:
            return self._current_references()
        if set(self.secret_arns) != set(self.references) or set(
            self.version_ids
        ) != set(self.references):
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

    def _current_references(self) -> list[dict[str, pulumi.Input[str]]]:
        """Reference each declared secret by its bare ARN, never a version ID.

        Each reference must fully match the declared name in this account and
        region. A mocked-program test over the rendered containerDefinitions
        (F6) comes when compute joins the hardened branch.
        """
        from poc_secret_observation import secret_arn_regex

        if set(self.secret_arns) != set(self.references):
            raise ValueError("Runtime secret inventory is incomplete")
        contract = self.descriptor._contract

        def declared(purpose: str):
            pattern = re.compile(
                secret_arn_regex(
                    contract["region"],
                    contract["account_id"],
                    self.references[purpose]["name"],
                    json_key=True,
                )
            )

            def check(reference: Any) -> str:
                require_unversioned_reference(reference)
                if not pattern.fullmatch(reference):
                    raise ValueError("Secret reference differs from its declaration")
                return reference

            return check

        return [
            {
                "name": ENVIRONMENT_NAMES[purpose],
                "valueFrom": self.secret_arns[purpose].apply(declared(purpose)),
            }
            for purpose in self.references
        ]

    def complete(self) -> None:
        """Export only metadata; the pre-hardening shape needs both derived secrets."""
        if not self._hardened:
            self.ecs_secrets()
        outputs: dict[str, Any] = {
            "secretArns": self.secret_arns,
            "versionIds": self.version_ids,
        }
        if self.seed_results:
            # Only a step-2 graph seeds; metadata only, never a value (NFR-01).
            outputs["seedResults"] = self.seed_results
        self.register_outputs(outputs)
