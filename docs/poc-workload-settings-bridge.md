# Internal TEST workload settings bridge

`scripts/poc_workload_phase_entrypoint.py` connects the existing typed contract and
closed native image/config projection to the existing generated-secret settings
resolver and `WorkloadPhaseStack`. It does not enable workload execution. The
worker's capability/plan stop and fallback execution stop remain unchanged.

The internal caller supplies exact `SourceAdmission` facts, their matching full
workload contract and the web/worker projection from `inspect_images`. The bridge
revalidates shape, canonical source digest, fixed registry logical/physical names,
exact central TEST execution/task role names and AMD64 platform. Each image must
have exactly URI, manifest media type, config digest/size and platform; URI and
platform must equal the reviewed release. Native authenticity is the caller's
responsibility. Constructing a dataclass or passing schema-valid data grants no
deployment authority.

`workload_configuration` returns only public application config fields: immutable
digest-qualified images, fixed repositories/roles, production application mode,
declared HTTPS domain/certificate and SES sender, fixed SQS endpoint and health
path. It does not return secret material, arbitrary URLs, provider configuration,
metadata tags, a backend or a secrets-provider replacement. The trusted
materializer must merge this map into its authenticated baseline using protected
files and retain the existing canonical provider/checkpoint preparation. This
unit introduces no config/CLI phase switch, file writer or local state backend.

## Closed child program

`encode_workload_projection` and `decode_workload_projection` define a bounded,
canonical JSON wire format with exactly `schema_version`, `source`, `contract`
and `images`. They reject duplicate keys, nonfinite numbers, malformed source
hashes, alternate contract paths, extra fields, noncanonical bytes and changed
contract/image bindings. Decoding reuses the same full projection validation;
serialization does not authenticate evidence or grant phase authority.

`workload_program_source` embeds those bytes as a Python bytes literal and imports
only the fixed installed bridge from `/trusted/scripts` and `/trusted/pulumi`.
Contract text cannot become executable code. The generated program requires
Python isolated mode and no application arguments before importing that bridge.
`run_workload_program` decodes its embedded bytes and calls the existing workload
composition/settings path. There is no contract filename, environment variable,
config phase selector or public CLI that selects this graph. Direct execution of
the bridge module rejects.

The current registry runner uses a plain Python `PULUMI_PYTHON_CMD`; it **cannot
run this generated child**. `workload_python_wrapper_source` supplies source for
a future root-owned executable with a fixed `/opt/service-runtime/bin/python -I`
shebang. That wrapper uses `os.execv` to execute the same fixed interpreter with
`-I`, preserving native Pulumi arguments without shell expansion. The trusted
materializer must install/protect this wrapper, select it as `PULUMI_PYTHON_CMD`,
protect the generated program/config, and bind all resulting bytes to the saved
plan. No caller, PR config or environment override may select its interpreter.
These helpers generate source only; no wrapper or project is installed here.

The wrapper test verifies the fixed interpreter/flag/argv contract. Separate
isolated Python subprocesses execute the generated program with Pulumi mocks and
verify the unchanged registry baseline, complete existing workload graph and
exact image/secret references. Plain Python, extra program arguments and changed
release config reject before AWS resource registration. These are source/mocked
runtime checks, not a native Pulumi language-host or provider acceptance run.

`resolve_workload_inputs` runs in the isolated Pulumi child after that preparation.
It requires current protected config to equal every generated field, checks the
descriptor's project/stack/account/region, and reuses
`resolve_stack_settings(..., generated_secrets=True)`. It creates no second
EnvironmentSettings component and never invokes the legacy manual-secret loader.
`run_workload_phase` passes those settings, the existing registry projection and
`RuntimeSecretsDescriptor` to the existing composition. The inherited registry
parent, names, metadata and AWS provider links remain unchanged.

The secret lifecycle remains the existing one: pinned Random/TLS providers create
protected material in encrypted Pulumi provider state and named Secrets Manager
versions persist it under declared KMS keys. This bridge does not generate or
read plaintext itself, accept caller-supplied secret values, rotate material or
claim that generation occurs inside the Secrets Manager service. The complete
declaration remains attached to the descriptor.

## Exact remaining composition and integration work

- Generated settings no longer require an external `accessLogsBucketName`.
  `ComputePlane` creates service-owned ALB log storage and waits for its delivery
  policy/protections before enabling logging. The legacy manual-settings path
  retains its existing external bucket requirement. See
  [log and health composition](poc-workload-log-health.md) for the exact source
  graph and remaining native delivery/capability acceptance.
- The companion database composition unit propagates contract
  `runtime.database_name` and `runtime.ca_bundle_path` into the generated MongoDB
  URL, retaining TLS/retryWrites=false and explicit admin authentication. Its
  source evidence is separate; actual DocumentDB connectivity remains required.
- `ComputePlane` now maps the declared `runtime.worker_health_command` to an ECS
  `CMD` health check. The command must exist in the admitted image; actual worker
  health remains a native acceptance check.
- The exact next integration blocker is protected root materialization: install
  the fixed isolated interpreter wrapper, merge the generated public settings
  into admitted config, and protect/hash the generated child program before the
  first workload preview. The worker currently has no dispatcher for this path.
  Full authenticated capability acceptance, native saved-plan graph/replay bindings,
  phase-aware result/drift and actual workload health/release/rollback remain
  unconnected. Do not remove either existing execution stop based on this unit.

Focused tests use synthetic facts and isolated Pulumi mock registrations. They
verify exact images, generated-secret references, no IAM registration, unchanged
registry graph/provider metadata and rejection of altered source/image/config
bindings. Those tests are source evidence only, not native IAM, ECR, secret
generation or workload acceptance.
