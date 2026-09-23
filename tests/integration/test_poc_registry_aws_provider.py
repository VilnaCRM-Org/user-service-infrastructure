"""Pinned AWS provider and native engine over synthetic loopback AWS APIs only."""

import copy
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import poc_mail_prerequisite as mail  # noqa: E402
import poc_registry_plan as plan  # noqa: E402

PROVIDER_HOME = Path.home() / ".pulumi"


class SyntheticAws(BaseHTTPRequestHandler):
    """Only the fixed fixture's SES, ECR and Route53 operations are available."""

    ready = False

    def log_message(self, *_args):
        pass

    def respond(self, body, content_type="application/json"):
        payload = (
            json.dumps(body) if content_type == "application/json" else body
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def dns(self):
        namespace = ' xmlns="https://route53.amazonaws.com/doc/2013-04-01/"'
        if self.command == "POST":
            self.rfile.read(int(self.headers["Content-Length"]))
            body = f"<ChangeResourceRecordSetsResponse{namespace}/>"
        elif "rrset" in self.path:
            name = parse_qs(urlsplit(self.path).query)["name"][0].rstrip(".")
            token = name.split(".")[0]
            body = (
                f"<ListResourceRecordSetsResponse{namespace}><ResourceRecordSets>"
                f"<ResourceRecordSet><Name>{name}.</Name>"
                "<Type>CNAME</Type><TTL>300</TTL><ResourceRecords><ResourceRecord>"
                f"<Value>{token}.dkim.amazonses.com</Value>"
                "</ResourceRecord></ResourceRecords></ResourceRecordSet>"
                "</ResourceRecordSets><IsTruncated>false</IsTruncated>"
                "<MaxItems>100</MaxItems></ListResourceRecordSetsResponse>"
            )
        else:
            body = (
                f"<GetHostedZoneResponse{namespace}><HostedZone>"
                f"<Id>/hostedzone/{mail.ZONE}</Id><Name>vilnacrmtest.com.</Name>"
                "<CallerReference>synthetic</CallerReference><Config>"
                "<PrivateZone>false</PrivateZone></Config>"
                "</HostedZone></GetHostedZoneResponse>"
            )
        self.respond(body, "text/xml")

    def do_POST(self):
        if self.path.startswith("/2013-04-01/"):
            self.dns()
            return
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        if b"Action=GetCallerIdentity" in raw:
            self.respond(
                '<GetCallerIdentityResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/">'
                "<GetCallerIdentityResult><Account>" + plan.ACCOUNT + "</Account>"
                "<Arn>arn:aws:iam::" + plan.ACCOUNT + ":user/synthetic</Arn>"
                "<UserId>synthetic</UserId></GetCallerIdentityResult></GetCallerIdentityResponse>",
                "text/xml",
            )
            return
        target = self.headers.get("X-Amz-Target", "")
        if target.startswith("AmazonEC2ContainerRegistry"):
            request = json.loads(raw)
            name = (
                request.get("repositoryName") or request.get("repositoryNames", [""])[0]
            )
            name = name or request["resourceArn"].rsplit("/", 1)[-1]
            repository = {
                "repositoryArn": (
                    f"arn:aws:ecr:{plan.REGION}:{plan.ACCOUNT}:repository/{name}"
                ),
                "registryId": plan.ACCOUNT,
                "repositoryName": name,
                "repositoryUri": (
                    f"{plan.ACCOUNT}.dkr.ecr.{plan.REGION}.amazonaws.com/{name}"
                ),
                "imageTagMutability": "IMMUTABLE",
                "imageScanningConfiguration": {"scanOnPush": True},
                "encryptionConfiguration": {"encryptionType": "AES256"},
            }
            self.respond(
                {
                    "CreateRepository": {"repository": repository},
                    "DescribeRepositories": {"repositories": [repository]},
                    "ListTagsForResource": {"tags": self.tags()},
                }[target.split(".")[-1]]
            )
            return
        assert self.path == "/v2/email/identities"
        self.respond(
            {
                "IdentityType": "DOMAIN",
                "VerifiedForSendingStatus": False,
                "DkimAttributes": {"Tokens": [value * 32 for value in "abc"]},
            }
        )

    @staticmethod
    def tags():
        return [
            {"Key": key, "Value": value} for key, value in plan.DEFAULT_TAGS.items()
        ]

    def do_GET(self):
        if self.path.startswith("/2013-04-01/"):
            self.dns()
            return
        assert self.path.startswith(("/v2/email/identities/", "/v2/email/tags?"))
        self.respond(
            {
                "IdentityType": "DOMAIN",
                "VerifiedForSendingStatus": self.ready,
                "VerificationStatus": "SUCCESS" if self.ready else "PENDING",
                "Tags": self.tags(),
                "DkimAttributes": {
                    "SigningEnabled": True,
                    "SigningAttributesOrigin": "AWS_SES",
                    "CurrentSigningKeyLength": "RSA_2048_BIT",
                    "NextSigningKeyLength": "RSA_2048_BIT",
                    "Status": "SUCCESS" if self.ready else "PENDING",
                    "Tokens": [value * 32 for value in "abc"],
                },
            }
        )


def test_pinned_provider_checkpoint_metadata(tmp_path, ensure_pulumi_cli):
    homes = [PROVIDER_HOME]
    if os.environ.get("PULUMI_HOME"):
        homes.insert(0, Path(os.environ["PULUMI_HOME"]))
    plugin = next(
        (
            home / "plugins/resource-aws-v7.23.0/pulumi-resource-aws"
            for home in homes
            if (home / "plugins/resource-aws-v7.23.0/pulumi-resource-aws").is_file()
        ),
        None,
    )
    if plugin is None:
        pytest.skip(
            "Pinned AWS 7.23.0 provider must be installed; no network acquisition"
        )
    SyntheticAws.ready = False
    server = ThreadingHTTPServer(("127.0.0.1", 0), SyntheticAws)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    provider = subprocess.Popen(
        [str(plugin)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env={
            "PATH": os.environ["PATH"],
            "HOME": str(tmp_path),
            "AWS_EC2_METADATA_DISABLED": "true",
            "AWS_MAX_ATTEMPTS": "1",
        },
    )
    try:
        port = int(provider.stdout.readline())
        rows, native = _checkpoint(tmp_path, server.server_port, port)
        for row in rows:
            if row["type"] == plan.ECR:
                plan._ecr_values(row, row["inputs"], row["outputs"], new=False)
                assert row["outputs"].keys() >= plan.ECR_PROVIDER_OUTPUTS.keys()
            elif row["type"] in (mail.SES, mail.DNS):
                if row["type"] == mail.SES:
                    private = row["outputs"]["dkimSigningAttributes"][
                        "domainSigningPrivateKey"
                    ]
                    assert set(private) == {mail.SIGNATURE, "ciphertext"}
                    assert row["outputs"].keys() >= mail.SES_PROVIDER_OUTPUTS.keys()
                else:
                    assert row["outputs"].keys() >= mail.DNS_PROVIDER_OUTPUTS.keys()
                mail.validate_row(row, new=False, tags=plan.DEFAULT_TAGS)
        assert {row["type"] for row in rows} >= {plan.ECR, mail.SES, mail.DNS}
        _validate_native(native)
    finally:
        provider.terminate()
        provider.wait(timeout=10)
        server.shutdown()
        server.server_close()


def _checkpoint(root, endpoint_port, provider_port):
    (root / "backend").mkdir()
    (root / "Pulumi.yaml").write_text(
        "name: user-service-infrastructure\nruntime:\n  name: python\n"
        f"  options:\n    virtualenv: {json.dumps(sys.prefix)}\n"
    )
    program = (
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT / 'pulumi')!r})\n"
        "from app.registry_phase import RegistryPhaseStack\n"
        f"RegistryPhaseStack(registries={plan.REGISTRIES!r})\n"
    )
    (root / "__main__.py").write_text(program)
    endpoint = f"http://127.0.0.1:{endpoint_port}"
    config = {
        "aws:region": plan.REGION,
        "aws:accessKey": "synthetic",
        "aws:secretKey": "synthetic",
        "aws:skipCredentialsValidation": True,
        "aws:skipRegionValidation": True,
        "aws:skipMetadataApiCheck": True,
        "aws:skipRequestingAccountId": False,
        "aws:endpoints": [
            {key: endpoint for key in ("sesv2", "ecr", "route53", "sts")}
        ],
    }
    config.update(
        {
            "user-service-infrastructure:" + key: value
            for key, value in {
                "environment": "test",
                "serviceName": plan.PROJECT,
                "owner": "team-user-service",
                "costCenter": "core",
                "repoSlug": plan.PROJECT,
                "pulumiBackendUrl": plan.ROOT_OUTPUTS["pulumiBackendUrl"],
                "pulumiSecretsProvider": plan.ROOT_OUTPUTS["pulumiSecretsProvider"],
            }.items()
        }
    )
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(root),
        "PULUMI_HOME": str(root / "home"),
        "PULUMI_BACKEND_URL": (root / "backend").as_uri(),
        "PULUMI_DEBUG_PROVIDERS": f"aws:{provider_port}",
        "PULUMI_CONFIG_PASSPHRASE": "synthetic-local-test-only",
        "PULUMI_SKIP_UPDATE_CHECK": "true",
        "PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION": "true",
        "PULUMI_PYTHON_CMD": sys.executable,
    }

    def cli(*arguments):
        result = subprocess.run(
            ["pulumi", "-C", str(root), *arguments],
            env=env,
            capture_output=True,
            timeout=90,
            check=False,
        )
        assert result.returncode == 0, "Synthetic native provider fixture failed"
        return result.stdout

    cli("stack", "init", "test", "--non-interactive")
    (root / "Pulumi.test.yaml").write_text(yaml.safe_dump({"config": config}))
    baseline_program = (
        "import sys\n" + f"sys.path.insert(0, {str(ROOT / 'pulumi')!r})\n"
        "from app.registry_phase import preserve_baseline\npreserve_baseline()\n"
    )
    (root / "__main__.py").write_text(baseline_program)
    cli("up", "--yes", "--skip-preview", "--non-interactive")
    baseline = json.loads(cli("stack", "export"))["deployment"]["resources"]
    (root / "__main__.py").write_text(program)
    initial_preview = json.loads(
        cli(
            "preview",
            "--json",
            "--refresh",
            "--show-sames",
            "--save-plan",
            str(root / "initial.plan"),
            "--non-interactive",
        )
    )
    initial_saved = json.loads((root / "initial.plan").read_text())
    _validate_native((baseline, initial_preview, initial_saved))
    cli("up", "--yes", "--skip-preview", "--non-interactive")
    rows = json.loads(cli("stack", "export"))["deployment"]["resources"]
    SyntheticAws.ready = True
    preview = json.loads(
        cli(
            "preview",
            "--json",
            "--refresh",
            "--show-sames",
            "--save-plan",
            str(root / "repeat.plan"),
            "--non-interactive",
        )
    )
    saved = json.loads((root / "repeat.plan").read_text())
    same_identity = next(
        step
        for step in preview["steps"]
        if step["op"] == "same" and step["oldState"]["type"] == mail.SES
    )
    assert same_identity["oldState"]["outputs"]["verifiedForSendingStatus"] is True
    assert (
        next(row for row in rows if row["type"] == mail.SES)["outputs"][
            "verifiedForSendingStatus"
        ]
        is False
    )
    after = json.loads(cli("stack", "export"))["deployment"]["resources"]
    assert rows == after
    return rows, (rows, preview, saved)


def _validate_native(native):
    rows, preview, saved = copy.deepcopy(native)
    provider = next((row for row in rows if row["type"] == plan.PROVIDER), None)
    # The fixture alone uses synthetic credentials and loopback endpoints.
    # Normalize only its provider configuration to the independently tested
    # production guard. Every application resource/event/goal remains native.
    provider_inputs = {
        "version": "7.23.0",
        "region": plan.REGION,
        "allowedAccountIds": json.dumps([plan.ACCOUNT]),
        "__internal": {},
        "skipCredentialsValidation": "false",
        "skipRegionValidation": "false",
        "skipRequestingAccountId": "false",
    }
    provider_goal = saved["resourcePlans"][plan.PROVIDER_URN]["goal"]
    if provider:
        provider["inputs"] = provider_inputs
        provider["outputs"] = {
            key: value for key, value in provider_inputs.items() if key != "__internal"
        }
        provider_goal["inputDiff"] = {}
    else:
        provider_goal["inputDiff"] = {"adds": provider_inputs}
    provider_goal["outputDiff"] = {}
    projection = plan.RegistryPhaseProjection(registries=plan.REGISTRIES)
    plan.validate(
        preview,
        saved_plan=saved,
        prior_resources=rows,
        projection=projection,
        require_refresh=True,
    )
