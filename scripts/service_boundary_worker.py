"""Credential-free isolation smoke; deployment commands remain unavailable."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from service_execution_process import require, run  # noqa: E402

DISABLED = "PR deployment is disabled during controller installation."
PROGRAM = "import os; assert os.geteuid() == 2000; print('ISOLATED_CHILD_PASS')"


def smoke():
    """Run only a fixed installed probe, without credentials, mounts or PR input."""
    require(os.geteuid() == 0 and os.getpid() == 1, "private-root-pid-required")
    require(bool(os.statvfs("/").f_flag & os.ST_RDONLY), "readonly-root-required")
    require(
        not any(
            key.startswith(("AWS_", "GH_", "GITHUB_", "ACTIONS_")) for key in os.environ
        ),
        "credential-free-runtime-required",
    )
    result = run(
        [sys.executable, "-I", "-c", PROGRAM],
        env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"},
        cwd=Path("/tmp"),  # nosec B108 - private container tmpfs
        child=True,
        timeout=10,
    )
    require(result == b"ISOLATED_CHILD_PASS\n", "fixed-probe-required")


def main(argv=None):
    """Reject every deployment command without evaluating its arguments."""
    if (sys.argv[1:] if argv is None else argv) != ["smoke"]:
        print(DISABLED, file=sys.stderr)
        return 1
    try:
        smoke()
    except Exception:
        print("Isolated boundary smoke failed.", file=sys.stderr)
        return 1
    print("ISOLATED_BOUNDARY_PASS")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
