"""Real Docker isolation proof with synthetic local state, never AWS acceptance."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IMAGE = os.environ.get("SERVICE_EXECUTION_TEST_IMAGE")

PROGRAM = r"""
import errno, json, os
from pathlib import Path
import pulumi
assert os.geteuid() == 2000 and os.getgroups() == []
assert not any(k in os.environ for k in (
    'GH_TOKEN', 'GITHUB_TOKEN', 'GITHUB_ENV', 'GITHUB_OUTPUT', 'GITHUB_PATH',
    'ACTIONS_RUNTIME_TOKEN', 'ACTIONS_ID_TOKEN_REQUEST_TOKEN'))
assert not Path('/var/run/docker.sock').exists()
for name in ('/proc/1/environ', os.environ['ROOT_CANARY']):
    try:
        with open(name, 'rb') as stream: stream.read(1)
    except PermissionError: pass
    else: raise AssertionError('root authority readable')
paths = ['/trusted/scripts/service_execution_process.py',
         '/opt/pulumi/pulumi', '/opt/service-runtime/bin/python',
         '/usr/local/bin/aws', '/usr/bin/gh']
paths += json.loads(os.environ['PROTECTED_FILES'])
for name in paths:
    path = Path(name)
    assert path.exists()
    for action in (lambda: path.write_bytes(b'tamper'), path.unlink,
                   lambda: path.chmod(0o777),
                   lambda: path.rename(path.with_name('renamed'))):
        try: action()
        except OSError as error:
            assert error.errno in (errno.EPERM, errno.EACCES, errno.EROFS)
        else: raise AssertionError('protected file mutable')
home = Path(os.environ['HOME'])
(home/'sitecustomize.py').write_text('raise AssertionError("substituted")')
for name in ('aws', 'gh', 'python', 'pulumi'):
    path = home/name
    path.write_text('#!/bin/sh\nexit 99\n')
    path.chmod(0o700)
plugins = Path(os.environ['PULUMI_HOME'])/'plugins'
assert plugins.is_symlink()
try: plugins.unlink()
except PermissionError: pass
else: raise AssertionError('plugin pointer mutable')
pulumi.export('synthetic', 'offline')
"""

CONTROLLER = r'''
import hashlib, json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, '/trusted/scripts')
import service_execution_process as p
import service_execution_transport as t
import poc_registry_runner as registry
from _pulumi_command_support import CommandContext

registry._verify_checkout(os.environ['FIXTURE_SHA'])
area = Path(tempfile.mkdtemp(prefix='native-service-'))
calls = []
port = t.ServiceTransport(area, session={
    'AWS_ACCESS_KEY_ID':'synthetic', 'AWS_SECRET_ACCESS_KEY':'synthetic',
    'AWS_SESSION_TOKEN':'synthetic'}, region='eu-central-1',
    account='891377212104', before_program=lambda: calls.append('admission'))
canary = area/'root-canary'
p.private_write(canary, b'offline-root-canary')
config = port.inputs/'config'
plan = port.inputs/'plan'
p.protected_write(config, b'synthetic-config')
p.protected_write(plan, b'synthetic-plan')
port.environment['ROOT_CANARY'] = str(canary)
port.environment['PROTECTED_FILES'] = json.dumps([str(config), str(plan)])
port.environment['PULUMI_CONFIG_PASSPHRASE'] = ''
project = port.project(Path('/fixture/project'))
context = CommandContext(root_dir=port.repo,
    env={'PULUMI_COMMIT_SHA':'a'*40}, pulumi_dir=project,
    policy_pack_dir=Path('/fixture/policy'), plan_dir=port.repo/'.artifacts/plan',
    preview_artifact_dir=port.repo/'.artifacts/preview',
    backend_url='file://'+str(port.work/'backend'), secrets_provider='passphrase')
bound = port.bind(context)
bound.prepare_policy_pack(bound)
backend = port.work/'backend'
backend.mkdir(mode=0o700)
os.chown(backend,2000,2000)
port.environment['PULUMI_BACKEND_URL'] = bound.backend_url
env = dict(port.environment)
root = '/trusted/scripts/service_execution_process.py'
before = hashlib.sha256(Path(root).read_bytes()).hexdigest()
port(['pulumi','-C',str(project),'login',bound.backend_url,
      '--non-interactive'], env=env)
# Fixture-only local stack creation precedes the protected execution boundary.
# Production never initializes shared stacks through this worker.
os.chown(project,2000,2000)
port(['pulumi','-C',str(project),'stack','init','dev',
      '--secrets-provider','passphrase','--non-interactive'], env=env)
os.chown(project,0,0)
for path in project.iterdir(): os.chown(path,0,0)
saved = port.repo/'.artifacts/offline.plan'
result = port(['pulumi','-C',str(project),'preview','--stack','dev',
              '--non-interactive','--save-plan',str(saved),'--json',
              '--policy-pack',str(bound.policy_pack_dir)], env=env)
assert json.loads(result.stdout)['steps'] and saved.is_file()
port(['pulumi','-C',str(project),'up','--stack','dev','--non-interactive',
      '--yes','--plan',str(saved),'--policy-pack',str(bound.policy_pack_dir)],
     env=env)
assert calls == ['admission','admission']
assert not p._child_pids()
assert before == hashlib.sha256(Path(root).read_bytes()).hexdigest()
for name, version in [('aws','7.23.0'),('random','4.19.2'),('tls','5.3.1')]:
    path = t.PLUGINS/f'resource-{name}-v{version}'/f'pulumi-resource-{name}'
    assert p.run([str(path),'--version'], env=env, cwd=port.work,
                 child=True).decode().strip() == version
daemon = """
import subprocess, sys, time
subprocess.Popen([sys.executable,'-I','-c','import time; time.sleep(60)'],
                 start_new_session=True, stdin=subprocess.DEVNULL,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
if sys.argv[1] == 'timeout': time.sleep(60)
raise SystemExit(1 if sys.argv[1] == 'failure' else 0)
"""
for mode in ('success','failure','timeout'):
    try:
        p.run([t.PYTHON,'-I','-c',daemon,mode], env=env, cwd=port.work,
              child=True, timeout=1)
    except ValueError:
        assert mode != 'success'
    else: assert mode == 'success'
    assert not p._child_pids()
    assert p.run([t.PYTHON,'-I','-c',
        "import sys;sys.path.insert(0,'/trusted/scripts');"
        "import service_execution_process as p;"
        "assert p.__file__=='/trusted/scripts/service_execution_process.py'"],
        env={'PATH':'/usr/bin:/bin','PYTHONPATH':str(port.work)},
        cwd=port.work) == b''
print('OFFLINE_SERVICE_ISOLATION_PASS')
'''


@pytest.mark.skipif(not IMAGE, reason="Explicit locally built worker image required")
def test_real_readonly_container_and_local_plan(tmp_path):
    """Use real UID/PID/filesystem/CLI behavior with networking disabled."""
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    shutil.copytree(
        ROOT / "scripts",
        trusted / "scripts",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for name in ("pyproject.toml", "uv.lock"):
        shutil.copyfile(ROOT / name, trusted / name)
    commands = (
        ["git", "init", "-q"],
        ["git", "add", "."],
        [
            "git",
            "-c",
            "user.name=Synthetic",
            "-c",
            "user.email=synthetic@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        [
            "git",
            "remote",
            "add",
            "origin",
            "https://github.com/VilnaCRM-Org/user-service-infrastructure.git",
        ],
    )
    for command in commands:
        subprocess.run(command, cwd=trusted, check=True, capture_output=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=trusted,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    fixture = tmp_path / "fixture"
    (fixture / "project").mkdir(parents=True)
    (fixture / "project/Pulumi.yaml").write_text(
        "name: user-service-infrastructure\nruntime: python\n"
    )
    (fixture / "project/__main__.py").write_text(PROGRAM)
    (fixture / "policy").mkdir()
    (fixture / "policy/PulumiPolicy.yaml").write_text(
        "runtime:\n  name: python\n  options:\n    virtualenv: .venv\n"
    )
    (fixture / "policy/__main__.py").write_text(
        "import os\nfrom pulumi_policy import PolicyPack,ResourceValidationPolicy\n"
        "assert os.geteuid()==2000\n"
        "PolicyPack(name='offline',policies=[ResourceValidationPolicy("
        "name='offline',description='offline',validate=lambda args,report:None)])\n"
    )
    (fixture / "controller.py").write_text(CONTROLLER)
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--user",
            "0:0",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=512m",
            "--cap-drop",
            "ALL",
            "--cap-add",
            "SETUID",
            "--cap-add",
            "SETGID",
            "--cap-add",
            "CHOWN",
            "--cap-add",
            "DAC_OVERRIDE",
            "--cap-add",
            "KILL",
            "--pids-limit",
            "128",
            "--security-opt",
            "no-new-privileges",
            "--mount",
            f"type=bind,src={trusted},dst=/trusted,readonly",
            "--mount",
            f"type=bind,src={fixture},dst=/fixture,readonly",
            "-e",
            f"FIXTURE_SHA={sha}",
            "-e",
            "GH_TOKEN=offline-root-canary",
            IMAGE,
            "/opt/service-runtime/bin/python",
            "-I",
            "/fixture/controller.py",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env={"PATH": os.defpath},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OFFLINE_SERVICE_ISOLATION_PASS"
