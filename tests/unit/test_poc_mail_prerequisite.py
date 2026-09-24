"""Fail closed on SES/DNS ownership, pending verification and credential injection."""

import copy
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
mail = importlib.import_module("poc_mail_prerequisite")
graph = importlib.import_module("test_poc_registry_plan")


def native_identity():
    return {
        "IdentityType": "DOMAIN",
        "VerifiedForSendingStatus": True,
        "DkimAttributes": {
            "SigningAttributesOrigin": "AWS_SES",
            "SigningEnabled": True,
            "CurrentSigningKeyLength": "RSA_2048_BIT",
            "Status": "SUCCESS",
            "Tokens": [letter * 32 for letter in "abc"],
        },
        "Tags": [
            {"Key": key, "Value": value}
            for key, value in graph.plan.DEFAULT_TAGS.items()
        ],
    }


def native(service, operation, arguments):
    if service == "sesv2":
        assert arguments == {"email-identity": mail.DOMAIN}
        return native_identity()
    if operation == "get-hosted-zone":
        assert arguments == {"id": mail.ZONE}
        return {
            "HostedZone": {
                "Id": f"/hostedzone/{mail.ZONE}",
                "Name": "vilnacrmtest.com.",
                "Config": {"PrivateZone": False},
            }
        }
    assert arguments["hosted-zone-id"] == mail.ZONE
    name = arguments["start-record-name"]
    return {
        "ResourceRecordSets": [
            {
                "Name": name,
                "Type": "CNAME",
                "TTL": 300,
                "ResourceRecords": [
                    {"Value": name.split(".")[0] + ".dkim.amazonses.com"}
                ],
            }
        ]
    }


def test_owned_identity_and_public_dns_match_native_checkpoint(monkeypatch):
    monkeypatch.setattr(mail, "read", native)
    mail.inspect_inventory(list(graph.states().values()), graph.plan.DEFAULT_TAGS)
    assert mail.inspect_identity(ready=True) == native_identity()


@pytest.mark.parametrize(
    "fault",
    [
        "absent",
        "pending",
        "unverified",
        "integer",
        "disabled",
        "byodkim",
        "weak",
        "email",
        "tokens",
    ],
)
def test_workload_requires_native_verified_domain_and_easy_dkim(monkeypatch, fault):
    value = native_identity()
    if fault == "absent":
        value = None
    elif fault in ("pending", "disabled", "byodkim", "weak", "tokens"):
        key, replacement = {
            "pending": ("Status", "PENDING"),
            "disabled": ("SigningEnabled", False),
            "byodkim": ("SigningAttributesOrigin", "EXTERNAL"),
            "weak": ("CurrentSigningKeyLength", "RSA_1024_BIT"),
            "tokens": ("Tokens", ["a" * 32] * 3),
        }[fault]
        value["DkimAttributes"][key] = replacement
    elif fault == "email":
        value["IdentityType"] = "EMAIL_ADDRESS"
    else:
        value["VerifiedForSendingStatus"] = 1 if fault == "integer" else False
    monkeypatch.setattr(mail, "read", lambda *_: value)
    with pytest.raises(ValueError):
        mail.inspect_identity(ready=True)


def test_pending_identity_permits_prerequisite_receipt_only(monkeypatch):
    value = native_identity()
    value["VerifiedForSendingStatus"] = False
    value["DkimAttributes"]["Status"] = "PENDING"
    monkeypatch.setattr(mail, "read", lambda *_: value)
    assert mail.inspect_identity() == value
    with pytest.raises(ValueError, match="not-verified"):
        mail.inspect_identity(ready=True)
    monkeypatch.setattr(mail, "read", lambda *_: None)
    assert mail.inspect_identity() is None


@pytest.mark.parametrize(
    "fault", ["private", "zone", "tags", "token", "missing", "target", "type", "ttl"]
)
def test_native_inventory_rejects_foreign_or_changed_prerequisites(monkeypatch, fault):
    paths = {
        "private": ("get-hosted-zone", ("HostedZone", "Config", "PrivateZone"), True),
        "zone": ("get-hosted-zone", ("HostedZone", "Name"), "foreign.example."),
        "tags": ("get-email-identity", ("Tags",), []),
        "token": ("get-email-identity", ("DkimAttributes", "Tokens", 0), "d" * 32),
        "target": (
            "list-resource-record-sets",
            ("ResourceRecordSets", 0, "ResourceRecords", 0, "Value"),
            "foreign.example",
        ),
        "type": ("list-resource-record-sets", ("ResourceRecordSets", 0, "Type"), "TXT"),
        "ttl": ("list-resource-record-sets", ("ResourceRecordSets", 0, "TTL"), 60),
    }

    def read(service, operation, arguments):
        value = native(service, operation, arguments)
        if fault == "missing":
            return None if service == "sesv2" else value
        expected, path, replacement = paths[fault]
        if expected == operation:
            target = value
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = replacement
        return value

    monkeypatch.setattr(mail, "read", read)
    with pytest.raises(ValueError):
        mail.inspect_inventory(list(graph.states().values()), graph.plan.DEFAULT_TAGS)


def test_initial_phase_never_adopts_an_existing_unowned_identity(monkeypatch):
    monkeypatch.setattr(mail, "read", native)
    with pytest.raises(ValueError):
        mail.inspect_inventory([], graph.plan.DEFAULT_TAGS)
    monkeypatch.setattr(
        mail, "read", lambda s, o, a: None if s == "sesv2" else native(s, o, a)
    )
    mail.inspect_inventory([], graph.plan.DEFAULT_TAGS)


@pytest.mark.parametrize(
    "fault",
    [
        "domain",
        "zone",
        "record",
        "credential",
        "token",
        "dependency",
        "extra",
        "missing",
    ],
)
def test_exact_saved_graph_rejects_unreviewed_mail_authority(fault):
    data = graph.case("repeat")
    rows = data["prior_resources"]
    identity = next(row for row in rows if row["type"] == mail.SES)
    record = next(row for row in rows if row["type"] == mail.DNS)
    if fault == "domain":
        identity["inputs"]["emailIdentity"] = "vilnacrmtest.com"
    elif fault == "zone":
        record["inputs"]["zoneId"] = "ZOTHER"
    elif fault == "record":
        record["inputs"]["records"] = ["foreign.example"]
    elif fault == "credential":
        identity["inputs"]["dkimSigningAttributes"]["domainSigningPrivateKey"] = (
            "synthetic-not-a-key"
        )
    elif fault == "token":
        identity["outputs"]["dkimSigningAttributes"]["tokens"][0] = "d" * 32
    elif fault == "dependency":
        record["dependencies"] = []
    elif fault == "extra":
        rows.append(copy.deepcopy(record))
    else:
        rows.remove(record)
    with pytest.raises(ValueError):
        graph.validate(data)


def test_cli_reads_fixed_endpoints_without_credentials_or_pagination_conflict(
    monkeypatch,
):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=b"{}", stderr=b"")

    monkeypatch.setattr(mail.subprocess, "run", run)
    mail.read("sesv2", "get-email-identity", {"email-identity": mail.DOMAIN})
    mail.read(
        "route53",
        "list-resource-record-sets",
        {
            "hosted-zone-id": mail.ZONE,
            "start-record-name": "a" * 32 + "._domainkey." + mail.DOMAIN,
        },
    )
    assert calls[0][calls[0].index("--endpoint-url") + 1] == (
        "https://email.eu-central-1.amazonaws.com"
    )
    assert calls[1][calls[1].index("--endpoint-url") + 1] == (
        "https://route53.amazonaws.com"
    )
    assert "--max-items" not in calls[1]
    request = json.loads(calls[1][calls[1].index("--cli-input-json") + 1])
    assert request["MaxItems"] == "1"
    assert all(
        not any(
            "secret" in argument.lower() or "token" in argument.lower()
            for argument in command
        )
        for command in calls
    )
    with pytest.raises(ValueError):
        mail.read("sesv2", "create-email-identity", {})


@pytest.mark.parametrize(
    "error", [b"AccessDenied", b"arbitrary-private-body", b"NotFoundException"]
)
def test_denial_and_unstructured_errors_are_not_absence(monkeypatch, error):
    monkeypatch.setattr(
        mail.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(returncode=1, stdout=b"", stderr=error),
    )
    with pytest.raises(ValueError, match="^mail-prerequisite-binding$"):
        mail.read("sesv2", "get-email-identity", {"email-identity": mail.DOMAIN})


def test_only_native_ses_notfound_means_absence(monkeypatch):
    error = (
        b"An error occurred (NotFoundException) when calling "
        b"the GetEmailIdentity operation: absent"
    )
    monkeypatch.setattr(
        mail.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(returncode=1, stdout=b"", stderr=error),
    )
    assert (
        mail.read("sesv2", "get-email-identity", {"email-identity": mail.DOMAIN})
        is None
    )
    with pytest.raises(ValueError):
        mail.read("route53", "get-hosted-zone", {"id": mail.ZONE})


def test_prerequisite_resources_are_not_registered_for_another_stack(monkeypatch):
    from app import mail_identity

    monkeypatch.setattr(mail_identity.pulumi, "get_stack", lambda: "prod")
    monkeypatch.setattr(
        mail_identity.aws.sesv2,
        "EmailIdentity",
        lambda *_a, **_k: pytest.fail("registered a resource"),
    )
    with pytest.raises(ValueError, match="TEST"):
        mail_identity.create_mail_identity(parent=None, tags={})


def test_graph_owns_only_provider_derived_dkim_cnames(tmp_path):
    from test_poc_registry_phase_entrypoint import graph_receipt

    result = graph_receipt(tmp_path)
    identities = [row for row in result["resources"] if row["type"] == mail.SES]
    records = [row for row in result["resources"] if row["type"] == mail.DNS]
    assert len(identities) == 1 and len(records) == 3
    assert identities[0]["inputs"] == mail.identity_inputs(graph.plan.DEFAULT_TAGS)
    for row in records:
        index = int(row["name"].rsplit("-", 1)[-1])
        assert row["inputs"] == mail.record_inputs("abc"[index] * 32)
        assert result["parents"][row["name"]] == result["urns"]["user-service"]


def test_pending_ses_blocks_real_workload_admission_before_final_gate(monkeypatch):
    import poc_workload_admission as admission

    monkeypatch.setattr(admission, "inspect_registry", lambda *_: "anchor")
    monkeypatch.setattr(admission, "inspect_release", lambda *_: None)
    monkeypatch.setattr(admission.images, "inspect_images", lambda *_: None)
    monkeypatch.setattr(admission.capabilities, "inspect_capabilities", lambda *_: None)
    observed = native_identity()
    observed["DkimAttributes"]["Status"] = "PENDING"
    monkeypatch.setattr(mail, "read", lambda *_: observed)
    with pytest.raises(ValueError, match="workload-ses-identity-not-verified"):
        admission.inspect_workload({}, {}, None, "plan")
    observed["DkimAttributes"]["Status"] = "SUCCESS"
    with pytest.raises(ValueError, match="native-image-capability-and-plan"):
        admission.inspect_workload({}, {}, None, "plan")


@pytest.mark.parametrize(
    "domain", ["vilnacrmtest.com", "sub.user.vilnacrmtest.com", "other.example"]
)
def test_sender_domain_is_exact_not_parent_or_subdomain(domain):
    import poc_contract
    from test_poc_contract import fixture

    contract = fixture("workload")
    contract["workload"]["external"]["mail"]["sender"] = "sender@" + domain
    with pytest.raises(ValueError, match="TEST owned domain"):
        poc_contract._validate_document(contract)


@pytest.mark.parametrize(
    "attribute", ["domain", "identity_arn", "hosted_zone_id", "owner", "dkim"]
)
def test_registry_identity_binding_cannot_be_overridden(attribute):
    import poc_contract
    from test_poc_contract import fixture

    contract = fixture("registry")
    contract["mail_identity"][attribute] = "foreign"
    with pytest.raises(ValueError, match="schema"):
        poc_contract._validate_document(contract)


def test_legacy_ecr_only_or_partial_prerequisite_checkpoint_is_not_admitted():
    rows = list(graph.states().values())
    for prior in (
        [row for row in rows if row["type"] not in (mail.SES, mail.DNS)],
        rows[:-1],
    ):
        with pytest.raises(ValueError):
            graph.plan._prior(prior, graph.plan._graph(graph.projection()))


@pytest.mark.parametrize("new", [False, True])
def test_computed_ses_status_is_metadata_not_readiness_authority(new):
    row = next(row for row in graph.states().values() if row["type"] == mail.SES)
    if new:
        row.pop("id")
    row["outputs"].update(verificationStatus="PENDING", verifiedForSendingStatus=False)
    row["outputs"]["dkimSigningAttributes"]["status"] = "PENDING"
    mail.validate_row(row, new=new, tags=graph.plan.DEFAULT_TAGS)
    row["outputs"]["dkimSigningAttributes"]["status"] = mail.UNKNOWN
    if new:
        mail.validate_row(row, new=True, tags=graph.plan.DEFAULT_TAGS)
        row["outputs"]["dkimSigningAttributes"] = mail.UNKNOWN
        mail.validate_row(row, new=True, tags=graph.plan.DEFAULT_TAGS)
    else:
        with pytest.raises(ValueError):
            mail.validate_row(row, new=False, tags=graph.plan.DEFAULT_TAGS)


@pytest.mark.parametrize("value", [None, [], ["a" * 32] * 3, ["bad"] * 3])
def test_program_rejects_malformed_provider_tokens_before_dns(value):
    from app.mail_identity import _tokens

    with pytest.raises(ValueError, match="Easy DKIM tokens"):
        _tokens(SimpleNamespace(tokens=value))


def test_only_unused_provider_output_may_retain_an_opaque_envelope():
    data = graph.case("repeat")
    identity = next(row for row in data["prior_resources"] if row["type"] == mail.SES)
    identity["outputs"]["dkimSigningAttributes"]["domainSigningPrivateKey"] = {
        mail.SIGNATURE: mail.ENVELOPE_SENTINEL,
        "ciphertext": "synthetic-opaque-envelope",
    }
    for step in data["preview"]["steps"]:
        if step["newState"]["type"] == mail.SES:
            for key in ("oldState", "newState"):
                step[key]["outputs"]["dkimSigningAttributes"][
                    "domainSigningPrivateKey"
                ] = "[secret]"
    graph.validate(data)
    identity["inputs"]["dkimSigningAttributes"]["domainSigningPrivateKey"] = {
        mail.SIGNATURE: mail.ENVELOPE_SENTINEL,
        "ciphertext": "synthetic-opaque-envelope",
    }
    with pytest.raises(ValueError):
        graph.validate(data)


@pytest.mark.parametrize(
    "value",
    [
        "synthetic-key-material",
        "[secret]",
        {mail.SIGNATURE: mail.ENVELOPE_SENTINEL, "value": "synthetic-key-material"},
        {mail.SIGNATURE: mail.ENVELOPE_SENTINEL, "ciphertext": ""},
        {mail.SIGNATURE: "foreign", "ciphertext": "opaque"},
        {mail.SIGNATURE: mail.ENVELOPE_SENTINEL, "ciphertext": "opaque", "extra": True},
    ],
)
def test_unused_output_rejects_plaintext_and_malformed_envelopes(value):
    with pytest.raises(ValueError):
        mail._unused_private_output(value, preview=False)


def test_provider_empty_field_and_preview_normalization_are_narrow():
    empty = {mail.SIGNATURE: mail.ENVELOPE_SENTINEL, "value": ""}
    mail._unused_private_output(empty, preview=False)
    mail._unused_private_output("[secret]", preview=True)
    assert mail.redacted_outputs({}) == {}
    values = {"dkimSigningAttributes": {"domainSigningPrivateKey": empty}}
    assert mail.redacted_outputs(values) == {
        "dkimSigningAttributes": {"domainSigningPrivateKey": "[secret]"}
    }


@pytest.mark.parametrize("kind", [mail.SES, mail.DNS])
def test_pinned_provider_check_metadata_preserves_exact_semantics(kind):
    row = next(row for row in graph.states().values() if row["type"] == kind)
    row["inputs"]["__defaults"] = []
    if kind == mail.SES:
        row["inputs"].update(region="eu-central-1", tagsAll=graph.plan.DEFAULT_TAGS)
        row["inputs"]["dkimSigningAttributes"]["__defaults"] = []
    mail.validate_row(row, new=False, tags=graph.plan.DEFAULT_TAGS)
    row["inputs"]["unexpected"] = "not-provider-metadata"
    with pytest.raises(ValueError):
        mail.validate_row(row, new=False, tags=graph.plan.DEFAULT_TAGS)


@pytest.mark.parametrize(
    "key,value",
    [("__defaults", ["emailIdentity"]), ("region", "us-east-1"), ("tagsAll", {})],
)
def test_pinned_provider_metadata_cannot_override_ses_binding(key, value):
    row = next(row for row in graph.states().values() if row["type"] == mail.SES)
    row["inputs"][key] = value
    with pytest.raises(ValueError):
        mail.validate_row(row, new=False, tags=graph.plan.DEFAULT_TAGS)


def test_ecr_native_check_metadata_remains_exact():
    row = next(row for row in graph.states().values() if row["type"] == graph.plan.ECR)
    original = copy.deepcopy(row["inputs"])
    native_inputs = {
        **original,
        "__defaults": [],
        "region": "eu-central-1",
        "tagsAll": graph.plan.DEFAULT_TAGS,
        "imageScanningConfiguration": {"scanOnPush": True, "__defaults": []},
    }
    graph.plan._ecr_values(row, native_inputs, row["outputs"], new=False)
    assert original == row["inputs"]
    for key, value in (
        ("region", "us-east-1"),
        ("tagsAll", {}),
        ("__defaults", ["name"]),
        ("extra", True),
        (
            "imageScanningConfiguration",
            {"scanOnPush": True, "__defaults": ["scanOnPush"]},
        ),
    ):
        with pytest.raises(ValueError):
            graph.plan._ecr_values(
                row, {**native_inputs, key: value}, row["outputs"], new=False
            )


@pytest.mark.parametrize("kind", [mail.SES, mail.DNS, graph.plan.ECR])
def test_native_checkpoint_output_defaults_are_exact(kind):
    row = next(row for row in graph.states().values() if row["type"] == kind)
    metadata = {
        mail.SES: mail.SES_PROVIDER_OUTPUTS,
        mail.DNS: mail.DNS_PROVIDER_OUTPUTS,
        graph.plan.ECR: graph.plan.ECR_PROVIDER_OUTPUTS,
    }[kind]
    row["outputs"].update(copy.deepcopy(metadata))
    row["outputs"]["id"] = row["id"]

    def validate(candidate):
        if kind == graph.plan.ECR:
            graph.plan._ecr_values(
                candidate, candidate["inputs"], candidate["outputs"], new=False
            )
        else:
            mail.validate_row(candidate, new=False, tags=graph.plan.DEFAULT_TAGS)

    validate(row)
    for key in (*metadata, "__unknown_provider_field"):
        candidate = copy.deepcopy(row)
        candidate["outputs"][key] = {"foreign": "not-observed"}
        with pytest.raises(ValueError):
            validate(candidate)
    candidate = copy.deepcopy(row)
    candidate["outputs"]["__pulumi_raw_state_delta"]["obj"]["unexpected"] = True
    with pytest.raises(ValueError):
        validate(candidate)


def test_metadata_baseline_has_no_orphan_dns_records():
    rows = list(graph.states().values())
    mail.validate_bindings(
        [row for row in rows if row["type"] not in (mail.SES, mail.DNS)]
    )
    with pytest.raises(ValueError):
        mail.validate_bindings([row for row in rows if row["type"] != mail.SES])
