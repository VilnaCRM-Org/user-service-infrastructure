"""Observe immutable TEST ECR manifests and layers under the admitted CI caller.

Config blobs are checked privately against their digest, size and platform.
Root registry authorization never enters argv, logs, artifacts or a foreign host.
These CI-caller reads do not establish ECS pull authority or permit a workload.
"""

from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import re
import ssl
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import poc_backend_observer as backend
import poc_contract as contracts
import poc_registry_plan as graph
from service_execution_process import require, run
from service_execution_transport import AWS

MEDIA = {
    "application/vnd.docker.distribution.manifest.v2+json": (
        "application/vnd.docker.container.image.v1+json",
        {"application/vnd.docker.image.rootfs.diff.tar.gzip"},
    ),
    "application/vnd.oci.image.manifest.v1+json": (
        "application/vnd.oci.image.config.v1+json",
        {
            "application/vnd.oci.image.layer.v1.tar+gzip",
            "application/vnd.oci.image.layer.v1.tar+zstd",
        },
    ),
}
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_CONFIG_BYTES = 1024 * 1024
REGISTRY_HOST = f"{backend.ACCOUNT}.dkr.ecr.{backend.REGION}.amazonaws.com"
REGISTRY_ORIGIN = "https://" + REGISTRY_HOST
LAYER_HOST = (
    f"prod-{backend.REGION}-starport-layer-bucket.s3.{backend.REGION}.amazonaws.com"
)


def _native(operation, name, references):
    """Read only two ECR APIs, with fixed coordinates and the root AWS session."""
    require(name in {row["name"] for row in graph.REGISTRIES.values()}, "image-repo")
    require(
        operation in {"batch-get-image", "batch-check-layer-availability"},
        "image-operation",
    )
    parameter = "image-ids" if operation == "batch-get-image" else "layer-digests"
    request = (
        [{"imageDigest": value} for value in references]
        if operation == "batch-get-image"
        else references
    )
    return _aws(
        operation,
        [
            "--registry-id",
            backend.ACCOUNT,
            "--repository-name",
            name,
            "--" + parameter,
            json.dumps(request),
        ],
    )


def _aws(operation, arguments):
    """Capture fixed-endpoint AWS output privately with no ambient credentials."""
    require(
        operation
        in {
            "batch-get-image",
            "batch-check-layer-availability",
            "get-authorization-token",
        },
        "image-operation",
    )
    environment = {
        key: os.environ[key]
        for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")
    }
    environment.update(
        PATH="/usr/local/bin:/usr/bin:/bin",
        HOME=os.environ["HOME"],
        AWS_CONFIG_FILE="/dev/null",
        AWS_SHARED_CREDENTIALS_FILE="/dev/null",
        AWS_EC2_METADATA_DISABLED="true",
        AWS_MAX_ATTEMPTS="1",
    )
    raw = run(
        [
            AWS,
            "ecr",
            operation,
            *arguments,
            "--region",
            backend.REGION,
            "--endpoint-url",
            f"https://api.ecr.{backend.REGION}.amazonaws.com",
            "--output",
            "json",
            "--no-cli-pager",
            "--no-paginate",
        ],
        env=environment,
        cwd=Path("/trusted"),
        timeout=120,
    )
    require(len(raw) <= backend.MAX_METADATA, "image-response-bound")
    return backend._json(raw)


def _authorization():
    """Read a fresh ECR token only within the isolated trusted root worker."""
    require(os.geteuid() == 0 and os.getpid() == 1, "image-auth-worker")
    response = _aws("get-authorization-token", ["--registry-ids", backend.ACCOUNT])
    rows = response.get("authorizationData")
    require(type(rows) is list and len(rows) == 1, "image-auth-response")
    value = rows[0]
    require(value["proxyEndpoint"] == REGISTRY_ORIGIN, "image-auth-registry")
    expires = value["expiresAt"]
    if type(expires) is str:
        parsed = datetime.fromisoformat(expires)
        require(parsed.tzinfo is not None, "image-auth-timezone")
        expires = parsed.timestamp()
    require(type(expires) in (int, float), "image-auth-expiry")
    remaining = expires - datetime.now(timezone.utc).timestamp()
    require(60 < remaining <= 12 * 3600 + 60, "image-auth-expired")
    token = value["authorizationToken"]
    require(type(token) is str, "image-auth-token")
    decoded = base64.b64decode(token, validate=True)
    require(decoded.startswith(b"AWS:") and len(decoded) > 4, "image-auth-token")
    return token


def _connection(host):
    """Use direct verified TLS, ignoring proxy, netrc and ambient CA overrides."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile="/etc/ssl/certs/ca-certificates.crt")
    return http.client.HTTPSConnection(host, timeout=15, context=context)


def _blob_target(url, original_path):
    require(
        type(url) is str and len(url) <= 16384 and re.fullmatch(r"[\x21-\x7e]+", url),
        "image-config-url",
    )
    target = urlsplit(url)
    require(
        target.scheme == "https"
        and not target.fragment
        and target.netloc in {REGISTRY_HOST, LAYER_HOST},
        "image-config-origin",
    )
    if target.netloc == REGISTRY_HOST:
        require(target.path == original_path and not target.query, "image-config-path")
    else:
        require(target.path.startswith("/") and target.path != "/", "image-config-path")
    return target


def _header(response, name):
    """Reject ambiguous framing and redirect fields without reflecting values."""
    values = [value for key, value in response.getheaders() if key.lower() == name]
    require(len(values) <= 1, "image-config-header")
    return values[0] if values else None


def _config_body(response, descriptor, deadline):
    require(response.status == 200, "image-config-status")
    require(
        _header(response, "content-encoding") in (None, "identity"),
        "image-config-encoding",
    )
    size = descriptor["size"]
    length = _header(response, "content-length")
    require(length in (None, str(size)), "image-config-length")
    digest = _header(response, "docker-content-digest")
    require(digest in (None, descriptor["digest"]), "image-config-header-digest")
    raw = bytearray()
    while True:
        require(time.monotonic() < deadline, "image-config-deadline")
        chunk = response.read1(min(65536, size + 1 - len(raw)))
        if not chunk:
            break
        raw.extend(chunk)
        require(len(raw) <= size, "image-config-size")
    require(len(raw) == size, "image-config-size")
    require(
        "sha256:" + hashlib.sha256(raw).hexdigest() == descriptor["digest"],
        "image-config-digest",
    )
    return bytes(raw)


def _download_config(name, descriptor, token, *, connect=None):
    """Follow at most two HTTPS redirects to only the fixed ECR layer bucket."""
    path = f"/v2/{name}/blobs/{descriptor['digest']}"
    current = REGISTRY_ORIGIN + path
    deadline = time.monotonic() + 60
    connection = connect or _connection
    left_registry = False
    for _ in range(3):
        require(time.monotonic() < deadline, "image-config-deadline")
        target = _blob_target(current, path)
        headers = {"Accept-Encoding": "identity"}
        if target.netloc == REGISTRY_HOST:
            require(not left_registry, "image-config-return-redirect")
            headers["Authorization"] = "Basic " + token
        else:
            left_registry = True
        request_path = target.path + ("?" + target.query if target.query else "")
        with closing(connection(target.netloc)) as transport:
            transport.request("GET", request_path, headers=headers)
            with closing(transport.getresponse()) as response:
                if response.status in {301, 302, 303, 307, 308}:
                    location = _header(response, "location")
                    require(type(location) is str and location, "image-config-redirect")
                    current = urljoin(current, location)
                else:
                    return _config_body(response, descriptor, deadline)
    raise ValueError("image-config-redirect-limit")


def _config(name, descriptor, platform, *, authorize=None, connect=None):
    """Return only verified platform metadata; never expose config bodies/errors."""
    try:
        require(
            name in {row["name"] for row in graph.REGISTRIES.values()}, "image-repo"
        )
        _descriptor(descriptor, {value[0] for value in MEDIA.values()})
        require(descriptor["size"] <= MAX_CONFIG_BYTES, "image-config-bound")
        require(platform in {"linux/amd64", "linux/arm64"}, "image-config-platform")
        token = (authorize or _authorization)()
        raw = _download_config(name, descriptor, token, connect=connect)
        document = backend._json(raw)
        system, architecture = platform.split("/")
        require(
            document.get("os") == system
            and document.get("architecture") == architecture,
            "image-config-platform",
        )
        return {
            "config_digest": descriptor["digest"],
            "config_size": descriptor["size"],
            "platform": platform,
        }
    except Exception:
        raise ValueError("image-config-observation-failed") from None


def _descriptor(value, media):
    require(
        type(value) is dict and set(value) == {"mediaType", "size", "digest"},
        "image-descriptor",
    )
    require(value["mediaType"] in media, "image-descriptor-media")
    require(type(value["size"]) is int and value["size"] > 0, "image-blob-size")
    digest = value["digest"]
    require(
        type(digest) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", digest),
        "image-blob-digest",
    )


def _manifest(response, name, digest):
    require(response.get("failures") == [], "image-read-failures")
    rows = response.get("images")
    require(type(rows) is list and len(rows) == 1, "image-response-count")
    image = rows[0]
    require(
        image["registryId"] == backend.ACCOUNT
        and image["repositoryName"] == name
        and image["imageId"]["imageDigest"] == digest,
        "image-native-identity",
    )
    document = _document(image, digest)
    config_media, layer_media = MEDIA[document["mediaType"]]
    _descriptor(document["config"], {config_media})
    layers = document["layers"]
    require(type(layers) is list and 0 < len(layers) <= 100, "image-layer-count")
    for layer in layers:
        _descriptor(layer, layer_media)
    require(len({row["digest"] for row in layers}) == len(layers), "image-layer-repeat")
    return document


def _document(image, digest):
    """Decode original content-addressed single-image bytes with closed fields."""
    raw = image["imageManifest"]
    require(type(raw) is str, "image-manifest-type")
    encoded = raw.encode()
    require(len(encoded) <= MAX_MANIFEST_BYTES, "image-manifest-bound")
    require("sha256:" + hashlib.sha256(encoded).hexdigest() == digest, "image-bytes")
    document = backend._json(encoded)
    require(
        set(document) == {"schemaVersion", "mediaType", "config", "layers"}
        and type(document["schemaVersion"]) is int
        and document["schemaVersion"] == 2,
        "image-manifest-shape",
    )
    media = document["mediaType"]
    require(
        type(media) is str
        and media in MEDIA
        and image["imageManifestMediaType"] == media,
        "image-manifest-media",
    )
    return document


def _layers(response, expected):
    require(response.get("failures") == [], "image-layer-failures")
    rows = response.get("layers")
    require(type(rows) is list and len(rows) == len(expected), "image-layer-response")
    wanted = {item["digest"]: item for item in expected}
    require({row["layerDigest"] for row in rows} == set(wanted), "image-layer-set")
    for row in rows:
        descriptor = wanted[row["layerDigest"]]
        require(
            row["layerAvailability"] == "AVAILABLE"
            and type(row["layerSize"]) is int
            and row["layerSize"] == descriptor["size"]
            and row["mediaType"] == descriptor["mediaType"],
            "image-layer-unavailable",
        )


def inspect_images(contract, *, read=None, config=None):
    """Check both exact digests and return only closed nonsecret image references."""
    contracts._validate_document(contract)
    require(contract["phase"] == "workload", "image-workload-required")
    native = read or _native
    result = {}
    for kind in ("web", "worker"):
        registry = graph.REGISTRIES[kind]
        desired = contract["workload"]["release"][kind]
        uri = (
            f"{backend.ACCOUNT}.dkr.ecr.{backend.REGION}.amazonaws.com/"
            + registry["name"]
        )
        require(desired["repository_uri"] == uri, "image-registry-binding")
        name, digest = registry["name"], desired["digest"]
        document = _manifest(native("batch-get-image", name, [digest]), name, digest)
        layers = document["layers"]
        _layers(
            native(
                "batch-check-layer-availability", name, [r["digest"] for r in layers]
            ),
            layers,
        )
        observed_config = (config or _config)(
            name, document["config"], contract["workload"]["release"]["platform"]
        )
        result[kind] = {
            "uri": desired["repository_uri"] + "@" + digest,
            "manifest_media_type": document["mediaType"],
            **observed_config,
        }
    return result
