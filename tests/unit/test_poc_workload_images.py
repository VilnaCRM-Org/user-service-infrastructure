"""Reject forged native image metadata without live AWS or registry credentials."""

import base64
import copy
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import poc_workload_images as module  # noqa: E402
import pytest
from test_poc_contract import fixture


def config_bytes(architecture="amd64"):
    return json.dumps({"os": "linux", "architecture": architecture}).encode()


def manifest(media):
    config, layers = module.MEDIA[media]
    raw = config_bytes()
    return {
        "schemaVersion": 2,
        "mediaType": media,
        "config": {
            "mediaType": config,
            "size": len(raw),
            "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
        },
        "layers": [
            {
                "mediaType": sorted(layers)[0],
                "size": 456,
                "digest": "sha256:" + "d" * 64,
            }
        ],
    }


def evidence(media=None):
    document = manifest(media or next(iter(module.MEDIA)))
    raw = json.dumps(document)
    digest = "sha256:" + hashlib.sha256(raw.encode()).hexdigest()
    contract = fixture("workload")
    for kind in ("web", "worker"):
        name = module.graph.REGISTRIES[kind]["name"]
        uri = (
            f"{module.backend.ACCOUNT}.dkr.ecr.{module.backend.REGION}.amazonaws.com/"
            + name
        )
        contract["registries"][kind].update(
            name=name,
            uri=uri,
            arn=f"arn:aws:ecr:{module.backend.REGION}:{module.backend.ACCOUNT}:repository/{name}",
        )
        contract["workload"]["release"][kind]["repository_uri"] = uri
        contract["workload"]["release"][kind]["digest"] = digest
    return contract, document, raw, digest


def reader(document, raw, digest):
    calls = []

    def read(operation, name, references):
        calls.append((operation, name, references))
        if operation == "batch-get-image":
            return {
                "failures": [],
                "images": [
                    {
                        "registryId": module.backend.ACCOUNT,
                        "repositoryName": name,
                        "imageId": {"imageDigest": digest},
                        "imageManifest": raw,
                        "imageManifestMediaType": document["mediaType"],
                    }
                ],
            }
        assert operation == "batch-check-layer-availability"
        return {
            "failures": [],
            "layers": [
                {
                    "layerDigest": layer["digest"],
                    "layerAvailability": "AVAILABLE",
                    "layerSize": layer["size"],
                    "mediaType": layer["mediaType"],
                }
                for layer in document["layers"]
            ],
        }

    return read, calls


@pytest.mark.parametrize("media", module.MEDIA)
def test_observes_both_exact_images_and_returns_no_pull_claim(media):
    contract, document, raw, digest = evidence(media)
    read, calls = reader(document, raw, digest)

    def config(name, descriptor, platform):
        assert descriptor == document["config"]
        assert platform == contract["workload"]["release"]["platform"]
        return {
            "config_digest": descriptor["digest"],
            "config_size": descriptor["size"],
            "platform": platform,
        }

    result = module.inspect_images(contract, read=read, config=config)
    for kind in ("web", "worker"):
        assert result[kind] == {
            "uri": contract["registries"][kind]["uri"] + "@" + digest,
            "manifest_media_type": media,
            "config_digest": document["config"]["digest"],
            "config_size": document["config"]["size"],
            "platform": contract["workload"]["release"]["platform"],
        }
    assert [c[0] for c in calls] == [
        "batch-get-image",
        "batch-check-layer-availability",
        "batch-get-image",
        "batch-check-layer-availability",
    ]
    assert all(c[2] == [digest] for c in calls[::2])


@pytest.mark.parametrize(
    "fault",
    [
        "failures",
        "missing",
        "extra",
        "account",
        "repository",
        "digest",
        "bytes",
        "media",
        "manifest_type",
        "manifest_bound",
    ],
)
def test_rejects_missing_forged_or_transformed_native_manifest(fault):
    contract, document, raw, digest = evidence()
    read, calls = reader(document, raw, digest)

    def forged(operation, name, references):
        response = read(operation, name, references)
        image = response["images"][0]
        if fault == "failures":
            response["failures"] = [{"failureCode": "ImageNotFound"}]
        elif fault in {"missing", "extra"}:
            response["images"] = [] if fault == "missing" else [image, image]
        else:
            field, value = {
                "account": ("registryId", "000000000000"),
                "repository": ("repositoryName", "foreign"),
                "digest": ("imageId", {"imageDigest": "sha256:" + "f" * 64}),
                "bytes": ("imageManifest", raw + " "),
                "media": ("imageManifestMediaType", "unknown"),
                "manifest_type": ("imageManifest", {}),
                "manifest_bound": (
                    "imageManifest",
                    "x" * (module.MAX_MANIFEST_BYTES + 1),
                ),
            }[fault]
            image[field] = value
        return response

    with pytest.raises(ValueError):
        module.inspect_images(contract, read=forged)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "fault",
    [
        "index",
        "schema",
        "boolean_schema",
        "media",
        "config_media",
        "external_url",
        "size",
        "boolean_size",
        "digest",
        "empty_layers",
        "too_many",
        "layer_type",
        "foreign_layer",
        "repeated_layer",
        "duplicate_keys",
        "nonfinite",
    ],
)
def test_content_addressing_does_not_admit_unsupported_manifest(fault):
    _, document, _, _ = evidence()
    mutations = {
        "index": (document, "manifests", []),
        "schema": (document, "schemaVersion", 1),
        "boolean_schema": (document, "schemaVersion", True),
        "media": (document, "mediaType", "application/vnd.oci.image.index.v1+json"),
        "config_media": (document["config"], "mediaType", "foreign"),
        "external_url": (document["config"], "urls", ["https://untrusted.invalid/"]),
        "size": (document["config"], "size", -1),
        "boolean_size": (document["config"], "size", True),
        "digest": (document["config"], "digest", "tag"),
        "empty_layers": (document, "layers", []),
        "too_many": (document, "layers", document["layers"] * 101),
        "repeated_layer": (document, "layers", document["layers"] * 2),
        "layer_type": (document, "layers", "untrusted"),
        "foreign_layer": (
            document["layers"][0],
            "mediaType",
            "application/vnd.docker.image.rootfs.foreign.diff.tar.gzip",
        ),
    }
    if fault in mutations:
        target, key, value = mutations[fault]
        target[key] = value
    raw = json.dumps(document)
    if fault == "duplicate_keys":
        raw = raw.replace(
            '"schemaVersion": 2', '"schemaVersion": 2, "schemaVersion": 2'
        )
    elif fault == "nonfinite":
        raw = raw.replace(f'"size": {document["config"]["size"]}', '"size": NaN')
    digest = "sha256:" + hashlib.sha256(raw.encode()).hexdigest()
    read, _ = reader(document, raw, digest)
    with pytest.raises(ValueError):
        module._manifest(read("batch-get-image", "fixed", [digest]), "fixed", digest)


@pytest.mark.parametrize(
    "fault",
    [
        "failures",
        "empty",
        "extra",
        "foreign",
        "unavailable",
        "size",
        "bool",
        "media",
    ],
)
def test_rejects_incomplete_or_unavailable_layers(fault):
    contract, document, raw, digest = evidence()
    read, calls = reader(document, raw, digest)

    def forged(operation, name, references):
        response = read(operation, name, references)
        if operation == "batch-get-image":
            return response
        row = response["layers"][0]
        if fault == "failures":
            response["failures"] = [{"failureCode": "LayerInaccessible"}]
        elif fault in {"empty", "extra"}:
            response["layers"] = [] if fault == "empty" else [row, row]
        else:
            field, value = {
                "foreign": ("layerDigest", "sha256:" + "e" * 64),
                "unavailable": ("layerAvailability", "UNAVAILABLE"),
                "size": ("layerSize", 99),
                "bool": ("layerSize", True),
                "media": ("mediaType", "unknown"),
            }[fault]
            row[field] = value
        return response

    with pytest.raises(ValueError):
        module.inspect_images(contract, read=forged)
    assert len(calls) == 2


def test_schema_and_installed_repository_binding_precede_reads():
    contract, _, _, _ = evidence()
    for kind in ("web", "worker"):
        contract["registries"][kind]["uri"] = "foreign"
        contract["workload"]["release"][kind]["repository_uri"] = "foreign"
    for value in (fixture("registry"), contract):
        with pytest.raises(ValueError):
            module.inspect_images(value, read=lambda *_: pytest.fail("native read"))


def test_default_adapter_has_fixed_cli_endpoint_and_closed_session(monkeypatch):
    from test_poc_workload_image_config import transport

    contract, document, raw, digest = evidence()
    read, calls = reader(document, raw, digest)
    native_calls = []
    for key in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "HOME",
    ):
        monkeypatch.setenv(key, "synthetic")
    monkeypatch.setenv("GH_TOKEN", "must-not-pass")
    monkeypatch.setenv("AWS_ENDPOINT_URL", "https://must-not-pass.invalid")
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(module.os, "getpid", lambda: 1)
    connections, _ = transport([config_bytes(), config_bytes()])
    monkeypatch.setattr(module, "_connection", connections)
    token = base64.b64encode(b"AWS:synthetic-private-token").decode()

    def run(command, **kwargs):
        native_calls.append((command, kwargs))
        if command[2] == "get-authorization-token":
            return json.dumps(
                {
                    "authorizationData": [
                        {
                            "proxyEndpoint": module.REGISTRY_ORIGIN,
                            "authorizationToken": token,
                            "expiresAt": (
                                datetime.now(timezone.utc) + timedelta(hours=1)
                            ).isoformat(),
                        }
                    ]
                }
            ).encode()
        field = "--image-ids" if command[2] == "batch-get-image" else "--layer-digests"
        refs = json.loads(command[command.index(field) + 1])
        if field == "--image-ids":
            refs = [r["imageDigest"] for r in refs]
        return json.dumps(
            read(command[2], command[command.index("--repository-name") + 1], refs)
        ).encode()

    monkeypatch.setattr(module, "run", run)
    module.inspect_images(contract)
    assert len(calls) == 4 and len(native_calls) == 6
    for command, options in native_calls:
        assert command[:2] == ["/usr/local/bin/aws", "ecr"]
        assert (
            command[command.index("--endpoint-url") + 1]
            == "https://api.ecr.eu-central-1.amazonaws.com"
        )
        flag = (
            "--registry-ids"
            if command[2] == "get-authorization-token"
            else "--registry-id"
        )
        assert command[command.index(flag) + 1] == module.backend.ACCOUNT
        assert token not in repr(command) and token not in repr(options)
        assert options["cwd"] == Path("/trusted") and options["timeout"] == 120
        assert set(options["env"]) == {
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "PATH",
            "HOME",
            "AWS_CONFIG_FILE",
            "AWS_SHARED_CREDENTIALS_FILE",
            "AWS_EC2_METADATA_DISABLED",
            "AWS_MAX_ATTEMPTS",
        }


def test_native_failures_remain_failures_without_absence_fallback(monkeypatch):
    contract, _, _, _ = evidence()
    for key in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "HOME",
    ):
        monkeypatch.setenv(key, "synthetic")

    def denied(*_args, **_kwargs):
        raise ValueError("private-process-failed")

    monkeypatch.setattr(module, "run", denied)
    with pytest.raises(ValueError, match="private-process-failed"):
        module.inspect_images(contract)
    monkeypatch.setattr(
        module, "run", lambda *_a, **_k: b" " * (module.backend.MAX_METADATA + 1)
    )
    with pytest.raises(ValueError, match="image-response-bound"):
        module.inspect_images(contract)
    with pytest.raises(ValueError, match="image-operation"):
        module._native("get-authorization-token", "user-service-test-web", [])
    with pytest.raises(ValueError, match="image-repo"):
        module._native("batch-get-image", "foreign", [])


def test_layer_duplicate_cannot_hide_a_missing_digest():
    document = manifest(next(iter(module.MEDIA)))
    second = copy.deepcopy(document["layers"][0])
    second["digest"] = "sha256:" + "e" * 64
    expected = [*document["layers"], second]
    row = {"layerDigest": document["layers"][0]["digest"]}
    with pytest.raises(ValueError, match="image-layer-set"):
        module._layers({"failures": [], "layers": [row, row]}, expected)
