"""Fixed TEST SES/DNS ownership and native readiness checks; never read secrets."""

import json
import os
import re

# Fixed metadata operations; no shell execution.
import subprocess  # nosec B404

import poc_backend_observer as backend
from service_execution_process import require

DOMAIN = "user.vilnacrmtest.com"
ZONE = "Z04999481RZ4UQK2NANVH"
ARN = f"arn:aws:ses:{backend.REGION}:{backend.ACCOUNT}:identity/{DOMAIN}"
SES = "aws:sesv2/emailIdentity:EmailIdentity"
DNS = "aws:route53/record:Record"
UNKNOWN = "04da6b54-80e4-46f7-96ec-b56ff0331ba9"
SIGNATURE = "4dabf18193072939515e22adb298388d"
ENVELOPE_SENTINEL = "1b47061264138c4ac30d75fd1eb44270"
IDENTITY_NAME = "user-service-mail-identity"
DECLARATION = {
    "owner": "service",
    "domain": DOMAIN,
    "identity_arn": ARN,
    "hosted_zone_id": ZONE,
    "hosted_zone_name": "vilnacrmtest.com",
    "dkim": "easy-rsa-2048",
}


# AWS 7.23.0 native-engine checkpoint metadata, verified against loopback APIs.
# Exact constants deliberately reject unknown bridge shapes or routing settings.
SES_PROVIDER_OUTPUTS = {
    "__pulumi_raw_state_delta": {
        "obj": {
            "ps": {
                "dkimSigningAttributes": {
                    "plu": {"i": {"obj": {"ps": {"tokens": {"arr": {}}}}}}
                },
                "tags": {"map": {}},
                "tagsAll": {"map": {}},
            }
        }
    },
}
DNS_PROVIDER_OUTPUTS = {
    "__meta": (
        '{"e2bfb730-ecaa-11e6-8f88-34363bc7c4c0":{"create":1800000000000,'
        '"delete":1800000000000,"update":1800000000000},"schema_version":"2"}'
    ),
    "__pulumi_raw_state_delta": {
        "obj": {
            "ps": {
                "aliases": {"arr": {}},
                "cidrRoutingPolicy": {"plu": {"i": {}}},
                "failoverRoutingPolicies": {"arr": {}},
                "geolocationRoutingPolicies": {"arr": {}},
                "geoproximityRoutingPolicy": {"plu": {"i": {}}},
                "latencyRoutingPolicies": {"arr": {}},
                "records": {"arr": {}},
                "weightedRoutingPolicies": {"arr": {}},
            },
            "renamed": {
                "aliases": "alias",
                "failoverRoutingPolicies": "failover_routing_policy",
                "geolocationRoutingPolicies": "geolocation_routing_policy",
                "latencyRoutingPolicies": "latency_routing_policy",
                "weightedRoutingPolicies": "weighted_routing_policy",
            },
        }
    },
    "aliases": [],
    "cidrRoutingPolicy": None,
    "failoverRoutingPolicies": [],
    "geolocationRoutingPolicies": [],
    "geoproximityRoutingPolicy": None,
    "healthCheckId": "",
    "latencyRoutingPolicies": [],
    "multivalueAnswerRoutingPolicy": False,
    "setIdentifier": "",
    "weightedRoutingPolicies": [],
}


def check(condition):
    """Emit fixed public diagnostics without echoing cloud response bodies."""
    require(condition, "mail-prerequisite-binding")


def tokens(values):
    """Accept exactly three distinct Easy DKIM public tokens."""
    check(type(values) is list and len(values) == 3)
    check(
        all(
            type(value) is str and re.fullmatch(r"[a-z0-9]{32}", value)
            for value in values
        )
    )
    check(len(set(values)) == 3)
    return sorted(values)


def identity_inputs(tags):
    """Return the complete permitted SES resource inputs."""
    return {
        "emailIdentity": DOMAIN,
        "dkimSigningAttributes": {"nextSigningKeyLength": "RSA_2048_BIT"},
        "tags": tags,
    }


def record_inputs(token):
    """Bind a CNAME's name and value to one SES-generated public token."""
    return {
        "zoneId": ZONE,
        "name": UNKNOWN if token is None else f"{token}._domainkey.{DOMAIN}",
        "type": "CNAME",
        "ttl": 300,
        "records": UNKNOWN if token is None else [f"{token}.dkim.amazonses.com"],
        "allowOverwrite": False,
    }


def checked_inputs(kind, inputs, tags):
    """Strip only exact defaults observed from the pinned SES/DNS provider Check."""
    result = dict(inputs)
    if "__defaults" in result:
        check(result.pop("__defaults") == [])
    if kind == SES:
        for key, expected in (("region", backend.REGION), ("tagsAll", tags)):
            if key in result:
                check(result.pop(key) == expected)
        attributes = dict(result["dkimSigningAttributes"])
        if "__defaults" in attributes:
            check(attributes.pop("__defaults") == [])
        result["dkimSigningAttributes"] = attributes
    return result


def _unused_private_output(value, *, preview):
    """Accept only empty plaintext or the provider's unused opaque secret field.

    Encrypted checkpoint metadata cannot prove emptiness. BYODKIM inputs remain
    forbidden, and the native identity must independently use AWS_SES Easy DKIM.
    No contents of this unused output enter DNS inputs or public receipts.
    """
    if value in (None, "") or (preview and value == "[secret]"):
        return
    check(type(value) is dict and value.get(SIGNATURE) == ENVELOPE_SENTINEL)
    if set(value) == {SIGNATURE, "value"}:
        check(value["value"] == "")
        return
    check(set(value) == {SIGNATURE, "ciphertext"})
    check(type(value["ciphertext"]) is str and bool(value["ciphertext"]))


def redacted_outputs(outputs):
    """Normalize only the validated unused SES output for preview comparison."""
    result = dict(outputs)
    attributes = dict(result.get("dkimSigningAttributes", {}))
    private = attributes.get("domainSigningPrivateKey")
    if type(private) is dict:
        attributes["domainSigningPrivateKey"] = "[secret]"
    if "dkimSigningAttributes" in result:
        result["dkimSigningAttributes"] = attributes
    return result


def _dkim(attributes, *, new, preview):
    check(type(attributes) is dict)
    allowed = {
        "nextSigningKeyLength",
        "currentSigningKeyLength",
        "signingAttributesOrigin",
        "status",
        "tokens",
        "lastKeyGenerationTimestamp",
        "domainSigningPrivateKey",
        "domainSigningSelector",
    }
    check(attributes.keys() <= allowed)
    _unused_private_output(attributes.get("domainSigningPrivateKey"), preview=preview)
    check(not attributes.get("domainSigningSelector"))
    for key, value in {
        "nextSigningKeyLength": "RSA_2048_BIT",
        "currentSigningKeyLength": "RSA_2048_BIT",
        "signingAttributesOrigin": "AWS_SES",
    }.items():
        check(
            attributes.get(key, value) in (value, UNKNOWN)
            if new
            else attributes.get(key, value) == value
        )
    if not new:
        tokens(attributes.get("tokens"))
    if "status" in attributes:
        check(
            attributes["status"]
            in (
                "PENDING",
                "SUCCESS",
                "FAILED",
                "TEMPORARY_FAILURE",
                "NOT_STARTED",
                *((UNKNOWN,) if new else ()),
            )
        )


def validate_row(row, *, new, tags, preview=False):
    """Validate exact SES/DNS wire inputs; graph-level token bindings follow."""
    inputs = checked_inputs(row["type"], row.get("inputs", {}), tags)
    outputs = row.get("outputs", {})
    if row["type"] == DNS:
        check(set(inputs) == set(record_inputs(None)))
        token = None if inputs["name"] == UNKNOWN else inputs["name"].split(".")[0]
        check(token is None or re.fullmatch(r"[a-z0-9]{32}", token))
        check(inputs == record_inputs(token))
        expected_id = f"{ZONE}_{inputs['name']}_CNAME"
        expected = {
            **inputs,
            **DNS_PROVIDER_OUTPUTS,
            "fqdn": inputs["name"],
            "id": expected_id,
        }
        check(outputs.keys() <= expected.keys())
        check(
            all(
                value == expected[key] or (new and value == UNKNOWN)
                for key, value in outputs.items()
            )
        )
        check(
            row.get("id", "") in ("", UNKNOWN) if new else row.get("id") == expected_id
        )
        return
    check(inputs == identity_inputs(tags))
    expected = {
        **inputs,
        **SES_PROVIDER_OUTPUTS,
        "id": DOMAIN,
        "arn": ARN,
        "identityType": "DOMAIN",
        "region": backend.REGION,
        "tagsAll": tags,
        "configurationSetName": "",
    }
    check(
        outputs.keys()
        <= expected.keys() | {"verificationStatus", "verifiedForSendingStatus"}
    )
    for key, value in outputs.items():
        if new and value == UNKNOWN:
            continue
        if key == "dkimSigningAttributes":
            _dkim(value, new=new, preview=preview)
        elif key == "verificationStatus":
            check(
                value
                in ("PENDING", "SUCCESS", "FAILED", "TEMPORARY_FAILURE", "NOT_STARTED")
            )
        elif key == "verifiedForSendingStatus":
            check(type(value) is bool)
        else:
            check(value == expected[key])
    check(row.get("id", "") in ("", UNKNOWN) if new else row.get("id") == DOMAIN)
    if not new:
        check(outputs.get("arn") == ARN)
        _dkim(outputs.get("dkimSigningAttributes"), new=False, preview=preview)


def validate_bindings(rows):
    """Reject arbitrary known DNS records and require the exact identity tokens."""
    identities = [row for row in rows if row["type"] == SES]
    records = [row for row in rows if row["type"] == DNS]
    if not identities:
        check(not records)
        return
    check(len(identities) == 1 and len(records) == 3)
    identity = identities[0]
    values = (
        tokens(identity["outputs"]["dkimSigningAttributes"]["tokens"])
        if identity.get("id")
        else [None] * 3
    )
    for record in records:
        index = int(record["urn"].rsplit("-", 1)[-1])
        check(checked_inputs(DNS, record["inputs"], {}) == record_inputs(values[index]))
        check(identity["urn"] in record.get("dependencies", []))
        check(
            all(
                identity["urn"] in record.get("propertyDependencies", {}).get(key, [])
                for key in ("name", "records")
            )
        )


def read(service, operation, arguments):
    """Read bounded native metadata through fixed service endpoints and operations."""
    check(
        (service, operation)
        in {
            ("sesv2", "get-email-identity"),
            ("route53", "get-hosted-zone"),
            ("route53", "list-resource-record-sets"),
        }
    )
    endpoint = (
        f"https://email.{backend.REGION}.amazonaws.com"
        if service == "sesv2"
        else "https://route53.amazonaws.com"
    )
    command = [
        "aws",
        service,
        operation,
        "--region",
        backend.REGION,
        "--endpoint-url",
        endpoint,
        "--output",
        "json",
        "--no-cli-pager",
        "--no-paginate",
    ]
    if operation == "list-resource-record-sets":
        command.extend(
            [
                "--cli-input-json",
                json.dumps(
                    {
                        "HostedZoneId": arguments["hosted-zone-id"],
                        "StartRecordName": arguments["start-record-name"],
                        "StartRecordType": "CNAME",
                        "MaxItems": "1",
                    }
                ),
            ]
        )
    else:
        for key, value in arguments.items():
            command.extend(["--" + key, str(value)])
    # Arguments are fixed operations and public metadata.
    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
        timeout=60,
        env={**os.environ, "AWS_MAX_ATTEMPTS": "1"},
    )  # nosec B603
    check(len(result.stdout) <= backend.MAX_METADATA and len(result.stderr) <= 65536)
    if result.returncode:
        check(
            service == "sesv2"
            and re.match(
                rb"\s*(?:aws: \[ERROR\]: )?An error occurred "
                rb"\(NotFoundException\) when calling the GetEmailIdentity operation:",
                result.stderr,
            )
        )
        return None
    return backend._json(result.stdout)


def inspect_identity(*, ready=False):
    """Observe the fixed domain; pending is allowed only for prerequisite completion."""
    observed = read("sesv2", "get-email-identity", {"email-identity": DOMAIN})
    if observed is None:
        check(not ready)
        return None
    check(observed.get("IdentityType") == "DOMAIN")
    attributes = observed.get("DkimAttributes", {})
    check(attributes.get("SigningAttributesOrigin") == "AWS_SES")
    check(attributes.get("SigningEnabled") is True)
    check(attributes.get("CurrentSigningKeyLength") == "RSA_2048_BIT")
    tokens(attributes.get("Tokens"))
    if ready:
        require(
            observed.get("VerifiedForSendingStatus") is True
            and attributes.get("Status") == "SUCCESS",
            "workload-ses-identity-not-verified",
        )
    return observed


def inspect_inventory(resources, tags):
    """Compare native ownership and CNAME values to the complete private checkpoint."""
    zone = read("route53", "get-hosted-zone", {"id": ZONE})["HostedZone"]
    check(
        zone.get("Id") == f"/hostedzone/{ZONE}"
        and zone.get("Name") == "vilnacrmtest.com."
        and zone.get("Config", {}).get("PrivateZone") is False
    )
    identity = inspect_identity()
    existing = [row for row in resources if row["type"] == SES]
    if not existing:
        check(identity is None)
        return
    check(identity is not None)
    native_tokens = tokens(identity["DkimAttributes"]["Tokens"])
    check(
        native_tokens
        == tokens(existing[0]["outputs"]["dkimSigningAttributes"]["tokens"])
    )
    check(identity.get("Tags") is not None)
    check(
        sorted(identity["Tags"], key=lambda tag: tag["Key"])
        == [{"Key": key, "Value": value} for key, value in sorted(tags.items())]
    )
    for token in native_tokens:
        name = f"{token}._domainkey.{DOMAIN}."
        response = read(
            "route53",
            "list-resource-record-sets",
            {
                "hosted-zone-id": ZONE,
                "start-record-name": name,
                "start-record-type": "CNAME",
                "max-items": "1",
            },
        )
        check(
            response.get("ResourceRecordSets")
            == [
                {
                    "Name": name,
                    "Type": "CNAME",
                    "TTL": 300,
                    "ResourceRecords": [{"Value": f"{token}.dkim.amazonses.com"}],
                }
            ]
        )
