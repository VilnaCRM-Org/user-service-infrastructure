"""Run the actual registry graph in an isolated offline Pulumi runtime."""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

from coverage import Coverage


def main():
    """Return graph and coverage evidence without sharing the pytest event loop."""
    root = Path(sys.argv[1])
    sys.path[:0] = [str(root / "scripts"), str(root / "pulumi")]

    coverage = Coverage(
        config_file=False,
        branch=True,
        include=[
            str(root / "scripts/poc_registry_phase_entrypoint.py"),
            str(root / "pulumi/app/registry_phase.py"),
        ],
        data_file=sys.argv[3],
    )
    coverage.start()
    import poc_phase_admission as admission
    import poc_registry_phase_entrypoint as entrypoint
    from pulumi.runtime import mocks, settings, stack

    class Recorder(mocks.Mocks):
        def __init__(self):
            self.rows = []
            self.parents = {}
            self.urns = {}

        def new_resource(self, args):
            self.rows.append(args)
            values = dict(args.inputs)
            if args.typ == "aws:ecr/repository:Repository":
                values.update({"arn": args.name, "repositoryUrl": args.name})
            return args.name, values

        def call(self, args):
            raise AssertionError(args.token)

    document = json.loads(Path(sys.argv[2]).read_text())
    for kind, logical, name in (
        ("web", "user-service-web-repository", "user-service-test-web"),
        ("worker", "user-service-worker-repository", "user-service-test-worker"),
    ):
        value = document["registries"][kind]
        value.update(
            {
                "logical_name": logical,
                "name": name,
                "arn": f"arn:aws:ecr:eu-central-1:891377212104:repository/{name}",
                "uri": f"891377212104.dkr.ecr.eu-central-1.amazonaws.com/{name}",
            }
        )
    digest = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    source = admission.SourceAdmission(
        digest,
        "a" * 40,
        "b" * 40,
        admission.CONTRACT_PATH,
        "c" * 40,
        "d" * 64,
        "e" * 64,
    )
    projection = entrypoint.project_registry_phase(source, document)
    recorder, loop = Recorder(), asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    class Monitor(mocks.MockMonitor):
        def RegisterResource(self, request):
            recorder.parents[request.name] = request.parent
            result = super().RegisterResource(request)
            recorder.urns[request.name] = result.urn
            return result

    monitor = Monitor(recorder)
    mocks.set_mocks(
        recorder, project="user-service-infrastructure", stack="test", monitor=monitor
    )

    from pulumi.runtime import set_all_config

    set_all_config(
        {
            "user-service-infrastructure:environment": "test",
            "user-service-infrastructure:serviceName": "user-service-infrastructure",
            "user-service-infrastructure:owner": "team-user-service",
            "user-service-infrastructure:costCenter": "core",
            "user-service-infrastructure:repoSlug": "user-service-infrastructure",
            "user-service-infrastructure:pulumiBackendUrl": (
                "s3://pulumi-user-service-infrastructure-test-state"
            ),
            "user-service-infrastructure:pulumiSecretsProvider": (
                "awskms://alias/pulumi-user-service-infrastructure-test-secrets?region=eu-central-1"
            ),
        }
    )

    def program():
        entrypoint.run_registry_phase(projection)

    loop.run_until_complete(stack.run_pulumi_func(program))
    loop.run_until_complete(asyncio.sleep(0))
    sys.path.insert(0, str(root))
    from types import SimpleNamespace

    import pulumi
    from policy.pack import require_default_tags

    failures = []
    for row in recorder.rows:
        if row.custom:
            require_default_tags(
                SimpleNamespace(resource_type=row.typ, props=row.inputs),
                failures.append,
            )
    root_outputs = loop.run_until_complete(
        pulumi.Output.from_input(settings.get_root_resource().outputs).future()
    )
    print(
        json.dumps(
            {
                "resources": [
                    {
                        "type": row.typ,
                        "name": row.name,
                        "custom": row.custom,
                        "inputs": row.inputs,
                    }
                    for row in recorder.rows
                ],
                "policy_failures": failures,
                "root_outputs": root_outputs,
                "parents": recorder.parents,
                "urns": recorder.urns,
            },
            sort_keys=True,
        )
    )
    settings.reset_options(project=None, stack=None)
    loop.close()
    coverage.stop()
    coverage.save()

    coverage.json_report(outfile=sys.argv[3] + ".json")


if __name__ == "__main__":
    main()
