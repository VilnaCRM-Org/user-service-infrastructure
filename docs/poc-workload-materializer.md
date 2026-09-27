# Protected TEST workload input materializer

`scripts/poc_workload_materializer.py` adds a root-only materialization primitive.
It does not run Pulumi, select a phase, authenticate AWS evidence or authorize an
apply. The worker and runner do not call it yet; their unconditional workload
stops remain unchanged.

`materialize_workload(area, projection, baseline_config)` accepts the existing
already-authenticated `WorkloadPhaseProjection` and protected canonical JSON
baseline bytes. The caller must authenticate the source, native prerequisites,
current checkpoint and baseline encryption identity before invoking it. A typed
projection or successful serialization is not evidence of those checks.

The baseline is bounded to 1 MiB and contains exactly `config`, `secretsprovider`
and `encryptedkey`. It retains the existing encrypted data key without fetching,
decrypting or replacing it. The secrets provider and explicit environment,
service name, repository slug and backend metadata must match TEST. Duplicate
keys, nonfinite values, alternate encryption fields and noncanonical bytes reject.
The existing provider-pin and closed workload-overlay helpers normalize the
fixed AWS target and reject conflicting committed workload settings. Other
protected baseline settings remain unchanged. No raw configuration enters the
return value or diagnostics.

## Protected filesystem boundary

The caller must be UID 0/PID 1 in the existing worker's read-only root and
`/trusted` mounts. Directory traversal uses `openat`-style directory descriptors,
`O_DIRECTORY` and `O_NOFOLLOW`; each ancestor must be root-owned and protected
against group/other writes. A root-owned sticky temporary ancestor is permitted,
but the destination area itself must not be writable by group/other users.

The helper exclusively reserves `area/workload` with mode `0700`; an existing
file, directory or symlink always rejects. Only four fixed files are created:

| File | Final ownership/mode | Content |
| --- | --- | --- |
| `Pulumi.yaml` | `0:2000`, `0440` | Fixed project and Python runtime |
| `Pulumi.test.yaml` | `0:2000`, `0440` | Canonical merged protected config |
| `__main__.py` | `0:2000`, `0440` | Existing fixed generated workload child |
| `python` | `0:2000`, `0550` | Fixed isolated interpreter wrapper |

Every file is bounded to 1 MiB, created exclusively, flushed and fsynced, then
read back as a single-link regular file with exact bytes, ownership and mode.
Only after all four checks does one directory permission change publish the
complete set to group 2000 (`0750`). Children cannot traverse partially written
inputs. Failures revoke directory access and remove only the newly reserved
fixed files/directory. Preexisting areas or files are never replaced. The parent
worker owns normal lifetime cleanup after use.

The immutable result contains the directory, fixed filename/SHA-256 pairs,
projection SHA-256 and original baseline SHA-256. `python_command` points to the
fixed wrapper. These are byte bindings for a future same-run saved-plan manifest;
they are not deployment receipts.

## Native interpreter contract

A credential-free smoke test runs the actual Pulumi **3.223.0** CLI and Python
language host in a bubblewrap namespace with networking disabled, fixed
`/opt/service-runtime` interpreter mount, the exact generated wrapper and a local
backend. It previews only a no-resource Python program. With project runtime
`{"name":"python"}`, `PULUMI_PYTHON_CMD` selects the wrapper and the program observes
`sys.flags.isolated == 1`, one program argument and prefix `/opt/service-runtime`.

The negative case adds `runtime.options.virtualenv`. Pulumi then bypasses
`PULUMI_PYTHON_CMD`, observes isolated mode `0` and fails the child guard. Therefore
the materializer deliberately omits the virtualenv option: the fixed wrapper
itself selects `/opt/service-runtime/bin/python -I`. The future dispatcher must
preserve this project shape and set `PULUMI_PYTHON_CMD` from the returned fixed
path. In particular, it cannot reuse the existing transport's project runtime
rewrite unchanged.

The native smoke skips when Pulumi, bubblewrap or user namespaces are unavailable.
It establishes the launcher behavior, not an AWS/provider workload, native
root:2000 filesystem ownership, or production worker installation. Unit tests
use actual local files with simulated root ownership metadata to exercise the
materializer's positive and rejection paths.

## Remaining gate

The next gate is a trusted root dispatcher that authenticates the baseline and
complete native capabilities, calls this helper, selects its wrapper without
rewriting the project runtime, and binds all returned digests to the same-run
source/checkpoint and exact saved plan. Protected replay, workload input/graph
validation, native result/drift observation and workload acceptance remain
required. This module does not weaken or remove any current stop.
