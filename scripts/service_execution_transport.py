"""Execute Pulumi children with protected inputs inside the trusted service worker.

Source admission, artifact authentication and the existing provider/plan checks
remain the caller's responsibility. No child receives GitHub authority.
"""

from __future__ import annotations

import os
import subprocess  # nosec B404
from dataclasses import replace
from pathlib import Path

import yaml
from service_execution_process import private_read, protected_write, require, run

PYTHON = "/opt/service-runtime/bin/python"
PULUMI = "/opt/pulumi/pulumi"
AWS = "/usr/local/bin/aws"
PLUGINS = Path("/opt/service-plugins/plugins")
MAX_FILES = 4096
MAX_TREE_BYTES = 32 * 1024 * 1024


def copy_tree(source, destination):
    """Copy bounded regular public source, preserving no symlinks or write bits."""
    require(source.is_dir() and not source.is_symlink(), "source-directory")
    destination.mkdir(mode=0o755)
    destination.chmod(0o755)
    size = 0
    for count, path in enumerate(source.rglob("*"), 1):
        require(count <= MAX_FILES and not path.is_symlink(), "source-tree-bound")
        target = destination / path.relative_to(source)
        if path.is_dir():
            target.mkdir(mode=0o755)
            target.chmod(0o755)
        else:
            raw = private_read(path)
            size += len(raw)
            require(size <= MAX_TREE_BYTES, "source-tree-bound")
            target.write_bytes(raw)
            target.chmod(0o644)


def project_document(raw):
    """Reject alternate entrypoints, tools, packages and runtime setup hooks."""
    from _pulumi_stack_config import _StackConfigLoader

    document = yaml.load(raw, Loader=_StackConfigLoader)  # nosec B506
    require(type(document) is dict, "project-document")
    require(
        document.keys() <= {"name", "description", "runtime"}
        and document.get("name") == "user-service-infrastructure",
        "project-shape",
    )
    require(
        document.get("runtime")
        in (
            "python",
            {"name": "python"},
            {"name": "python", "options": {"virtualenv": ".venv"}},
        ),
        "project-runtime",
    )
    document["runtime"] = {
        "name": "python",
        "options": {"virtualenv": str(Path(PYTHON).parents[1])},
    }
    return yaml.safe_dump(document).encode()


class ServiceTransport:
    """Root-owned transport; every Pulumi process runs as the isolated UID."""

    def __init__(self, area, *, session, region, account, before_program):
        require(os.geteuid() == 0 and os.getpid() == 1, "worker-root-pid")
        require(
            all(os.statvfs(p).f_flag & os.ST_RDONLY for p in ("/", "/trusted")),
            "worker-readonly",
        )
        require(
            area.is_absolute() and area.is_dir() and area.stat().st_uid == 0,
            "worker-private-area",
        )
        require(
            set(session)
            == {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"}
            and all(type(value) is str and value for value in session.values()),
            "worker-session",
        )
        self.area = area
        self.before_program = before_program
        area.chmod(0o711)
        self.repo = area / "repo"
        self.repo.mkdir(mode=0o755)
        self.repo.chmod(0o755)
        (self.repo / ".artifacts").mkdir(mode=0o700)
        self.work = area / "child"
        self.work.mkdir(mode=0o700)
        os.chown(self.work, 2000, 2000)
        self.inputs = area / "inputs"
        self.inputs.mkdir(mode=0o750)
        self.inputs.chmod(0o750)
        os.chown(self.inputs, 0, 2000)
        self.outputs = area / "outputs"
        self.outputs.mkdir(mode=0o770)
        self.outputs.chmod(0o770)
        os.chown(self.outputs, 0, 2000)
        home = area / "pulumi-home"
        home.mkdir(mode=0o755)
        home.chmod(0o755)
        (home / "plugins").symlink_to(PLUGINS, target_is_directory=True)
        workspace = home / "workspaces"
        workspace.mkdir(mode=0o700)
        os.chown(workspace, 2000, 2000)
        self.environment = {
            **session,
            "AWS_REGION": region,
            "AWS_DEFAULT_REGION": region,
            "AWS_ACCOUNT_ID": account,
            "AWS_EC2_METADATA_DISABLED": "true",
            "AWS_MAX_ATTEMPTS": "1",
            "PATH": "/opt/pulumi:/usr/local/bin:/usr/bin:/bin",
            "USER": "service-program",
            "HOME": str(self.work),
            "PULUMI_HOME": str(home),
            "PULUMI_CREDENTIALS_PATH": str(self.work / "credentials"),
            "PULUMI_SKIP_UPDATE_CHECK": "true",
            "PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION": "true",
            "PULUMI_IGNORE_AMBIENT_PLUGINS": "true",
            "PULUMI_PYTHON_CMD": PYTHON,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        }
        self.sequence = 0

    def project(self, source):
        """Materialize reviewed code as root-owned files with a fixed runtime."""
        destination = self.repo / "pulumi"
        copy_tree(source, destination)
        (destination / "Pulumi.yaml").write_bytes(
            project_document(private_read(destination / "Pulumi.yaml"))
        )
        return destination

    def bind(self, context):
        """Use the same legacy paths/schema while replacing process ownership."""
        policy = self.repo / "policy"
        copy_tree(context.policy_pack_dir, policy)
        document = yaml.safe_load(private_read(policy / "PulumiPolicy.yaml"))
        require(
            type(document) is dict
            and document.keys() <= {"runtime", "version", "description"}
            and document.get("runtime")
            == {"name": "python", "options": {"virtualenv": ".venv"}},
            "policy-runtime",
        )
        (policy / ".venv").symlink_to(Path(PYTHON).parents[1], target_is_directory=True)
        return replace(
            context,
            root_dir=self.repo,
            runner=self,
            policy_pack_dir=policy,
            env={
                **self.environment,
                "PULUMI_BACKEND_URL": context.backend_url,
                "PULUMI_SECRETS_PROVIDER": context.secrets_provider,
                "PULUMI_COMMIT_SHA": context.env["PULUMI_COMMIT_SHA"],
            },
            prepare_policy_pack=self.prepare_policy,
            summarize_preview=self.summarize,
        )

    def prepare_policy(self, context):
        """Preparation never imports policy code as root or installs dependencies."""
        require(
            context.policy_pack_dir == self.repo / "policy"
            and (context.policy_pack_dir / ".venv").resolve()
            == Path(PYTHON).parents[1].resolve(),
            "policy-prepared",
        )

    @staticmethod
    def summarize(preview, summary):
        from pulumi_ci_guardrails import summarize_preview

        with summary.open("a") as handle:
            handle.write(summarize_preview(preview))

    def _inputs(self, command):
        """Copy config and replay plan into a directory the child cannot replace."""
        for flag in ("--config-file", "--plan"):
            if flag in command:
                index = command.index(flag) + 1
                target = self.inputs / f"{self.sequence}-{flag[2:]}"
                protected_write(target, private_read(Path(command[index])))
                command[index] = str(target)

    def __call__(self, command, *, env, check=True, capture_output=False, stdout=None):
        """Adapt the existing CommandContext protocol without ambient execution."""
        del check, capture_output
        require(command[0] in {"pulumi", "aws"}, "worker-executable")
        self.sequence += 1
        argv = list(command)
        argv[0] = PULUMI if command[0] == "pulumi" else AWS
        self._inputs(argv)
        saved = None
        if "--save-plan" in argv:
            index = argv.index("--save-plan") + 1
            saved = Path(argv[index])
            argv[index] = str(self.outputs / f"{self.sequence}.plan")
        # Even login/select/export use UID 2000: no Pulumi discovery runs as root.
        child = command[0] == "pulumi"
        if child and command[3:4] in (["preview"], ["up"]):
            self.before_program()
        environment = {
            **self.environment,
            **{
                key: env[key]
                for key in (
                    "PULUMI_BACKEND_URL",
                    "PULUMI_SECRETS_PROVIDER",
                    "PULUMI_COMMIT_SHA",
                )
                if key in env
            },
        }
        raw = run(argv, env=environment, cwd=self.work, child=child)
        if saved is not None:
            saved.write_bytes(private_read(Path(argv[argv.index("--save-plan") + 1])))
            saved.chmod(0o600)
        result = subprocess.CompletedProcess(command, 0, raw.decode(), "")
        if stdout is not None:
            stdout.write(result.stdout)
        return result
