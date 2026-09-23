"""Pinned refresh events do not authorize semantic drift or readiness."""

import copy

import pytest
import test_poc_registry_plan as fixtures

plan = fixtures.plan
mail = plan.mail


def refreshed_case():
    data = fixtures.case("repeat")
    data["require_refresh"] = True
    rows = {row["urn"]: row for row in data["prior_resources"]}
    refresh, final = [], []
    for urn, row in rows.items():
        row["outputs"] = copy.deepcopy(row["outputs"])
        kind = row["type"]
        if kind == plan.PROVIDER:
            continue
        if kind in (plan.ECR, mail.SES, mail.DNS):
            row["inputs"]["__defaults"] = []
            row["outputs"]["id"] = row["id"]
            metadata = {
                plan.ECR: plan.ECR_PROVIDER_OUTPUTS,
                mail.SES: mail.SES_PROVIDER_OUTPUTS,
                mail.DNS: mail.DNS_PROVIDER_OUTPUTS,
            }[kind]
            row["outputs"].update(copy.deepcopy(metadata))
            diff = {"adds": {"__defaults": []}}
            if kind != mail.DNS:
                nested = (
                    "dkimSigningAttributes"
                    if kind == mail.SES
                    else "imageScanningConfiguration"
                )
                row["inputs"].update(
                    region=plan.REGION, tagsAll=copy.deepcopy(plan.DEFAULT_TAGS)
                )
                row["inputs"][nested]["__defaults"] = []
                diff["updates"] = {nested: copy.deepcopy(row["inputs"][nested])}
            data["saved_plan"]["resourcePlans"][urn]["goal"]["inputDiff"] = diff
        if kind == mail.SES:
            row["outputs"].update(
                verificationStatus="PENDING", verifiedForSendingStatus=False
            )
            row["outputs"]["dkimSigningAttributes"].update(
                status="PENDING",
                currentSigningKeyLength="RSA_2048_BIT",
                signingAttributesOrigin="AWS_SES",
                lastKeyGenerationTimestamp="",
                domainSigningPrivateKey={
                    mail.SIGNATURE: mail.ENVELOPE_SENTINEL,
                    "ciphertext": "synthetic-opaque-envelope",
                },
            )
        before = copy.deepcopy(row)
        if kind == mail.SES:
            before["outputs"] = mail.redacted_outputs(before["outputs"])
        refresh.append(
            {
                "urn": urn,
                "op": "refresh",
                "provider": row.get("provider", ""),
                "oldState": copy.deepcopy(before),
                "newState": copy.deepcopy(before),
            }
        )
        old = copy.deepcopy(before)
        if kind in (plan.ECR, mail.SES, mail.DNS):
            old["inputs"].pop("__defaults")
            if kind != mail.DNS:
                old["inputs"][nested].pop("__defaults")
        if kind == mail.SES:
            old["outputs"].update(
                verificationStatus="SUCCESS", verifiedForSendingStatus=True
            )
            old["outputs"]["dkimSigningAttributes"]["status"] = "SUCCESS"
        new = copy.deepcopy(before)
        new.pop("outputs")
        new.pop("id", None)
        final.append(
            {
                "urn": urn,
                "op": "same",
                "provider": row.get("provider", ""),
                "oldState": old,
                "newState": new,
            }
        )
    data["preview"]["steps"] = refresh + final
    return data


def ses_step(data, operation="same"):
    return next(
        step
        for step in data["preview"]["steps"]
        if step["op"] == operation and step["newState"]["type"] == mail.SES
    )


def test_native_refresh_metadata_and_verified_telemetry_preserve_checkpoint():
    data = refreshed_case()
    original = copy.deepcopy(data)
    plan.validate(**data)
    assert data == original
    # Even SUCCESS in this untrusted plan is never native readiness evidence.
    assert not next(row for row in data["prior_resources"] if row["type"] == mail.SES)[
        "outputs"
    ]["verifiedForSendingStatus"]


def test_explicit_same_outputs_remain_bound_and_minimal_metadata_is_exact():
    data = refreshed_case()
    for step in data["preview"]["steps"]:
        if step["op"] == "same":
            step["newState"]["outputs"] = copy.deepcopy(step["oldState"]["outputs"])
    plan.validate(**data)
    assert plan._ecr_checked_inputs({}) == {}
    assert plan._verification_telemetry({}) == {}
    row = next(row for row in fixtures.states().values() if row["type"] == mail.DNS)
    goal = {"type": mail.DNS, "inputDiff": {"adds": {"__defaults": []}}}
    assert plan._recheck_inputs(goal, row) == {**row["inputs"], "__defaults": []}


@pytest.mark.parametrize(
    "mutation",
    [
        "no-refresh",
        "missing-refresh",
        "duplicate-refresh",
        "late-refresh",
        "missing-final",
        "duplicate-final",
        "refresh-diff",
        "new-output-list",
        "plaintext-key",
        "secret-extra-field",
        "status-presence",
        "status-type",
        "token-drift",
        "timestamp-drift",
        "origin-drift",
        "arn-drift",
        "raw-metadata",
        "input-key-injection",
        "input-default-value",
        "output-diff",
        "final-update",
        "new-id",
        "new-parent",
        "new-provider",
        "new-protect",
        "new-partial-output",
        "new-complete-output-drift",
    ],
)
def test_refresh_protocol_rejects_substantive_or_ambiguous_mutations(mutation):
    data = refreshed_case()
    steps = data["preview"]["steps"]
    same = ses_step(data)
    attrs = same["oldState"]["outputs"]["dkimSigningAttributes"]
    goal = data["saved_plan"]["resourcePlans"][same["urn"]]["goal"]

    def change(target, key, value):
        target[key] = value

    mutations = {
        "no-refresh": lambda: steps.__setitem__(
            slice(None), [step for step in steps if step["op"] != "refresh"]
        ),
        "missing-refresh": lambda: steps.remove(ses_step(data, "refresh")),
        "duplicate-refresh": lambda: steps.insert(0, copy.deepcopy(steps[0])),
        "late-refresh": lambda: steps.append(steps.pop(0)),
        "missing-final": lambda: steps.remove(same),
        "duplicate-final": lambda: steps.append(copy.deepcopy(same)),
        "refresh-diff": lambda: change(
            steps[0], "detailedDiff", {"inputs": {"kind": "update"}}
        ),
        "new-output-list": lambda: change(same["newState"], "outputs", []),
        "plaintext-key": lambda: change(
            attrs, "domainSigningPrivateKey", "synthetic-key-material"
        ),
        "secret-extra-field": lambda: change(
            attrs,
            "domainSigningPrivateKey",
            {
                mail.SIGNATURE: mail.ENVELOPE_SENTINEL,
                "ciphertext": "opaque",
                "extra": True,
            },
        ),
        "status-presence": lambda: attrs.pop("status"),
        "status-type": lambda: change(
            same["oldState"]["outputs"], "verifiedForSendingStatus", "true"
        ),
        "token-drift": lambda: attrs["tokens"].__setitem__(0, "d" * 32),
        "timestamp-drift": lambda: change(
            attrs, "lastKeyGenerationTimestamp", "different"
        ),
        "origin-drift": lambda: change(attrs, "signingAttributesOrigin", "EXTERNAL"),
        "arn-drift": lambda: change(
            same["oldState"]["outputs"], "arn", mail.ARN + "-foreign"
        ),
        "raw-metadata": lambda: change(
            same["oldState"]["outputs"]["__pulumi_raw_state_delta"], "unexpected", True
        ),
        "input-key-injection": lambda: change(
            goal["inputDiff"]["updates"]["dkimSigningAttributes"],
            "domainSigningSelector",
            "foreign",
        ),
        "input-default-value": lambda: change(
            goal["inputDiff"]["adds"], "__defaults", ["emailIdentity"]
        ),
        "output-diff": lambda: change(
            goal, "outputDiff", {"updates": {"verifiedForSendingStatus": True}}
        ),
        "final-update": lambda: change(same, "op", "update"),
        "new-id": lambda: change(same["newState"], "id", "foreign"),
        "new-parent": lambda: change(same["newState"], "parent", plan.ROOT),
        "new-provider": lambda: change(same["newState"], "provider", "foreign"),
        "new-protect": lambda: change(same["newState"], "protect", True),
        "new-partial-output": lambda: change(
            same["newState"], "outputs", {"arn": mail.ARN}
        ),
        "new-complete-output-drift": lambda: change(
            same["newState"],
            "outputs",
            {
                **copy.deepcopy(same["oldState"]["outputs"]),
                "tags": {"Owner": "foreign"},
            },
        ),
    }
    mutations[mutation]()
    with pytest.raises(ValueError):
        plan.validate(**data)
