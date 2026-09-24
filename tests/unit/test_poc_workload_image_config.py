"""Exercise private config retrieval with synthetic HTTP/AWS peers only."""

import base64
import hashlib
import json
import ssl
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import poc_workload_images as module  # noqa: E402
import pytest


class Response:
    def __init__(self, raw=b"", *, status=200, headers=()):
        self.raw = raw
        self.status = status
        self.headers = list(headers)
        self.closed = False
        self.reads = []

    def getheaders(self):
        return self.headers

    def read1(self, size):
        self.reads.append(size)
        result, self.raw = self.raw[:size], self.raw[size:]
        return result

    def close(self):
        self.closed = True


def transport(responses):
    pending = iter(responses)
    calls = []

    class Connection:
        def __init__(self, host):
            self.host = host
            self.closed = False
            self.response = next(pending)
            if type(self.response) is bytes:
                self.response = Response(self.response)

        def request(self, method, path, *, headers):
            calls.append((self, method, path, headers))

        def getresponse(self):
            return self.response

        def close(self):
            self.closed = True

    return Connection, calls


def blob(architecture="amd64"):
    raw = json.dumps(
        {
            "os": "linux",
            "architecture": architecture,
            "config": {"Env": ["SYNTHETIC_PRIVATE=never-report"]},
            "history": [{"created_by": "private build information"}],
        }
    ).encode()
    return raw, descriptor(raw)


def descriptor(raw):
    return {
        "mediaType": "application/vnd.docker.container.image.v1+json",
        "size": len(raw),
        "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
    }


def inspect(raw, value=None, *, responses=None, platform="linux/amd64"):
    factory, calls = transport(responses if responses is not None else [raw])
    result = module._config(
        "user-service-test-web",
        value or descriptor(raw),
        platform,
        authorize=lambda: "SYNTHETIC_PRIVATE_TOKEN",
        connect=factory,
    )
    return result, calls


@pytest.mark.parametrize("architecture", ["amd64", "arm64"])
def test_native_config_is_bound_to_exact_size_digest_and_platform(architecture):
    raw, value = blob(architecture)
    result, calls = inspect(raw, value, platform="linux/" + architecture)
    assert result == {
        "config_digest": value["digest"],
        "config_size": len(raw),
        "platform": "linux/" + architecture,
    }
    assert "never-report" not in repr(result) and "private build" not in repr(result)
    connection, method, path, headers = calls[0]
    assert connection.host == module.REGISTRY_HOST
    assert (
        method == "GET" and path == "/v2/user-service-test-web/blobs/" + value["digest"]
    )
    assert headers == {
        "Accept-Encoding": "identity",
        "Authorization": "Basic SYNTHETIC_PRIVATE_TOKEN",
    }
    assert connection.closed and connection.response.closed
    assert max(connection.response.reads) <= 65536


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_documented_layer_bucket_redirect_never_receives_registry_auth(status):
    raw, value = blob()
    redirect = Response(
        status=status,
        headers=[
            (
                "Location",
                f"https://{module.LAYER_HOST}/bounded/config?X-Amz-Signature=synthetic",
            )
        ],
    )
    result, calls = inspect(raw, value, responses=[redirect, raw])
    assert result["config_digest"] == value["digest"]
    assert calls[1][0].host == module.LAYER_HOST
    assert calls[1][2] == "/bounded/config?X-Amz-Signature=synthetic"
    assert calls[1][3] == {"Accept-Encoding": "identity"}
    assert all(c[0].closed and c[0].response.closed for c in calls)
    assert not redirect.reads


def test_relative_same_origin_redirect_preserves_only_exact_blob_path():
    raw, value = blob()
    path = "/v2/user-service-test-web/blobs/" + value["digest"]
    _, calls = inspect(
        raw, value, responses=[Response(status=307, headers=[("Location", path)]), raw]
    )
    assert all(c[0].host == module.REGISTRY_HOST for c in calls)
    assert all(c[3]["Authorization"] == "Basic SYNTHETIC_PRIVATE_TOKEN" for c in calls)


@pytest.mark.parametrize(
    "location",
    [
        "http://example.invalid/config",
        "file:///etc/passwd",
        "https://example.invalid/config",
        "https://127.0.0.1/config",
        "https://169.254.169.254/config",
        f"https://{module.REGISTRY_HOST}.example.invalid/config",
        f"https://user:password@{module.REGISTRY_HOST}/config",
        f"https://{module.REGISTRY_HOST}:444/config",
        f"https://{module.LAYER_HOST}/config#fragment",
        f"https://{module.LAYER_HOST}/",
        f"https://{module.LAYER_HOST}/config\r\nAuthorization: leak",
        "https://prod-us-east-1-starport-layer-bucket.s3.us-east-1.amazonaws.com/config",
        "https://foreign.s3.eu-central-1.amazonaws.com/config",
        "https://s3.eu-central-1.amazonaws.com/foreign/config",
        "/v2/user-service-test-worker/blobs/sha256:foreign",
        "?arbitrary=query",
        "https://" + "x" * 16400,
    ],
)
def test_unapproved_redirect_stops_before_second_request_and_sanitizes(location):
    raw, value = blob()
    factory, calls = transport([Response(status=307, headers=[("Location", location)])])
    with pytest.raises(ValueError, match="^image-config-observation-failed$") as error:
        module._config(
            "user-service-test-web",
            value,
            "linux/amd64",
            authorize=lambda: "private-token",
            connect=factory,
        )
    assert len(calls) == 1 and calls[0][0].closed
    assert error.value.__suppress_context__ and location not in str(error.value)


def test_redirect_from_layer_bucket_cannot_restore_registry_authorization():
    raw, value = blob()
    original = (
        module.REGISTRY_ORIGIN + "/v2/user-service-test-web/blobs/" + value["digest"]
    )
    responses = [
        Response(
            status=307, headers=[("Location", f"https://{module.LAYER_HOST}/config")]
        ),
        Response(status=307, headers=[("Location", original)]),
    ]
    factory, calls = transport(responses)
    with pytest.raises(ValueError, match="return-redirect"):
        module._download_config(
            "user-service-test-web", value, "private-token", connect=factory
        )
    assert len(calls) == 2 and "Authorization" not in calls[1][3]


def test_redirect_loops_are_bounded():
    raw, value = blob()
    path = "/v2/user-service-test-web/blobs/" + value["digest"]
    factory, calls = transport(
        [Response(status=307, headers=[("Location", path)]) for _ in range(3)]
    )
    with pytest.raises(ValueError, match="redirect-limit"):
        module._download_config(
            "user-service-test-web", value, "private-token", connect=factory
        )
    assert len(calls) == 3 and all(c[0].closed for c in calls)


@pytest.mark.parametrize(
    "headers", [[], [("Location", "")], [("Location", "one"), ("location", "two")]]
)
def test_missing_or_ambiguous_redirect_is_rejected(headers):
    raw, value = blob()
    with pytest.raises(ValueError, match="observation-failed"):
        inspect(raw, value, responses=[Response(status=307, headers=headers)])


@pytest.mark.parametrize(
    "headers",
    [
        [("Content-Encoding", "gzip")],
        [("Content-Length", "999")],
        [("Content-Length", "1"), ("content-length", "1")],
        [("Docker-Content-Digest", "sha256:foreign")],
    ],
)
def test_ambiguous_or_transformed_response_is_rejected(headers):
    raw, value = blob()
    response = Response(raw, headers=headers)
    with pytest.raises(ValueError, match="observation-failed"):
        inspect(raw, value, responses=[response])
    assert response.closed and not response.reads


def test_matching_optional_headers_are_accepted():
    raw, value = blob()
    response = Response(
        raw,
        headers=[
            ("Content-Length", str(len(raw))),
            ("Docker-Content-Digest", value["digest"]),
            ("Content-Encoding", "identity"),
        ],
    )
    assert inspect(raw, value, responses=[response])[0]["config_size"] == len(raw)


@pytest.mark.parametrize(
    "fault",
    [
        "size",
        "extra",
        "truncated",
        "digest",
        "os",
        "architecture",
        "missing",
        "duplicate",
        "nonfinite",
        "array",
    ],
)
def test_wrong_bytes_or_platform_fail_without_exposing_config(fault):
    raw, value = blob()
    if fault == "size":
        value["size"] += 1
    elif fault == "extra":
        raw += b"x"
    elif fault == "truncated":
        raw = raw[:-1]
    elif fault == "digest":
        value["digest"] = "sha256:" + "d" * 64
    else:
        raw = {
            "os": b'{"os":"windows","architecture":"amd64"}',
            "architecture": b'{"os":"linux","architecture":"arm64"}',
            "missing": b'{"config":{"Env":["SYNTHETIC_PRIVATE=never-report"]}}',
            "duplicate": b'{"os":"linux","os":"linux","architecture":"amd64"}',
            "nonfinite": b'{"os":"linux","architecture":"amd64","value":NaN}',
            "array": b"[]",
        }[fault]
        value = descriptor(raw)
    with pytest.raises(ValueError, match="^image-config-observation-failed$"):
        inspect(raw, value)


@pytest.mark.parametrize("status", [206, 400, 401, 403, 404, 500])
def test_partial_and_failed_http_never_become_absence(status):
    raw, value = blob()
    response = Response(b"private service error", status=status)
    with pytest.raises(ValueError, match="observation-failed"):
        inspect(raw, value, responses=[response])
    assert response.closed and not response.reads


@pytest.mark.parametrize("fault", ["name", "size", "platform", "descriptor"])
def test_preconditions_fail_before_token_retrieval(fault):
    raw, value = blob()
    name, platform = "user-service-test-web", "linux/amd64"
    if fault == "name":
        name = "foreign"
    elif fault == "size":
        value["size"] = module.MAX_CONFIG_BYTES + 1
    elif fault == "platform":
        platform = "windows/amd64"
    else:
        value["urls"] = ["https://foreign.invalid"]
    with pytest.raises(ValueError, match="observation-failed"):
        module._config(
            name, value, platform, authorize=lambda: pytest.fail("token retrieval")
        )


def test_connection_errors_never_expose_token_or_signed_url():
    raw, value = blob()

    def failed(_host):
        raise RuntimeError("private-token https://signed.invalid/?secret=value")

    with pytest.raises(ValueError, match="^image-config-observation-failed$"):
        module._config(
            "user-service-test-web",
            value,
            "linux/amd64",
            authorize=lambda: "private-token",
            connect=failed,
        )


def test_socket_read_deadline_and_redirect_deadline_are_enforced(monkeypatch):
    raw, value = blob()
    monkeypatch.setattr(module.time, "monotonic", lambda: 100)
    with pytest.raises(ValueError, match="deadline"):
        module._config_body(Response(raw), value, 99)
    times = iter((0, 61))
    monkeypatch.setattr(module.time, "monotonic", lambda: next(times))
    with pytest.raises(ValueError, match="deadline"):
        module._download_config(
            "user-service-test-web",
            value,
            "private-token",
            connect=lambda _: pytest.fail("network"),
        )


def test_direct_tls_uses_fixed_trust_store_without_ambient_proxy_or_ca(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("HTTPS_PROXY", "http://untrusted.invalid")
    monkeypatch.setenv("SSL_CERT_FILE", "/untrusted/certs")
    keylog = tmp_path / "must-not-create-keylog"
    monkeypatch.setenv("SSLKEYLOGFILE", str(keylog))
    calls = []
    monkeypatch.setattr(
        module.http.client,
        "HTTPSConnection",
        lambda host, **kwargs: calls.append((host, kwargs)),
    )
    module._connection(module.REGISTRY_HOST)
    host, options = calls[0]
    assert host == module.REGISTRY_HOST and options["timeout"] == 15
    assert options["context"].verify_mode == ssl.CERT_REQUIRED
    assert options["context"].check_hostname
    assert options["context"].keylog_filename is None and not keylog.exists()


def authorization():
    return {
        "authorizationData": [
            {
                "proxyEndpoint": module.REGISTRY_ORIGIN,
                "authorizationToken": base64.b64encode(
                    b"AWS:synthetic-private-token"
                ).decode(),
                "expiresAt": (
                    datetime.now(timezone.utc) + timedelta(hours=1)
                ).isoformat(),
            }
        ]
    }


@pytest.mark.parametrize("numeric", [False, True])
def test_authorization_supports_native_cli_expiry_shapes(monkeypatch, numeric):
    value = authorization()
    if numeric:
        value["authorizationData"][0]["expiresAt"] = (
            datetime.now(timezone.utc).timestamp() + 3600
        )
    calls = []
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(module.os, "getpid", lambda: 1)
    monkeypatch.setattr(module, "_aws", lambda *args: calls.append(args) or value)
    assert (
        module._authorization() == value["authorizationData"][0]["authorizationToken"]
    )
    assert calls == [
        ("get-authorization-token", ["--registry-ids", module.backend.ACCOUNT])
    ]


@pytest.mark.parametrize(
    "fault",
    [
        "count",
        "endpoint",
        "expired",
        "future",
        "timezone",
        "boolean",
        "encoding",
        "prefix",
        "empty",
        "token_type",
    ],
)
def test_bad_authorization_is_rejected(monkeypatch, fault):
    value = authorization()
    row = value["authorizationData"][0]
    updates = {
        "endpoint": ("proxyEndpoint", "https://foreign.invalid"),
        "expired": ("expiresAt", 0),
        "future": ("expiresAt", 99999999999),
        "timezone": ("expiresAt", "2030-01-01T00:00:00"),
        "boolean": ("expiresAt", True),
        "encoding": ("authorizationToken", "bad\r\nheader"),
        "prefix": (
            "authorizationToken",
            base64.b64encode(b"foreign:password").decode(),
        ),
        "empty": ("authorizationToken", base64.b64encode(b"AWS:").decode()),
        "token_type": ("authorizationToken", 123),
    }
    if fault == "count":
        value["authorizationData"] = []
    else:
        key, replacement = updates[fault]
        row[key] = replacement
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(module.os, "getpid", lambda: 1)
    monkeypatch.setattr(module, "_aws", lambda *_: value)
    with pytest.raises(ValueError):
        module._authorization()


@pytest.mark.parametrize(("uid", "pid"), [(2000, 1), (0, 999)])
def test_registry_token_requires_isolated_root_worker(monkeypatch, uid, pid):
    monkeypatch.setattr(module.os, "geteuid", lambda: uid)
    monkeypatch.setattr(module.os, "getpid", lambda: pid)
    monkeypatch.setattr(module, "_aws", lambda *_: pytest.fail("AWS called"))
    with pytest.raises(ValueError, match="auth-worker"):
        module._authorization()
