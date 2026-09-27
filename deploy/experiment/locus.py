#!/usr/bin/env python3
"""Repository-owned import-locus attestation (VOICE-EL-P0D-1, Workstream C).

Proves that the package that will actually execute resolves underneath the
experiment release's ``release/`` directory — and refuses to continue on ANY
other locus.

Why this exists
---------------
The server has an installed ``speech_to_speech`` in site-packages. It is a
*fourth* body of code, distinct from the Golden release and from any experiment
release. If it ever wins the import race, everything runs against code nobody
reviewed and every downstream check still reports success. This module is the
fail-closed gate against that, in the same spirit as the runtime
``CC-2-RT-S2S-FAILCLOSED`` check.

Contract
--------
Passes only when::

    realpath(speech_to_speech.__file__).startswith(realpath(<release_root>/release) + os.sep)

Anything else — site-packages, the Golden release, a *different* experiment
release, a working tree, an unknown path — exits non-zero and prints both the
expected and the actual locus. It never silently continues.

Usage::

    python3 locus.py --expected-release-root /path/to/releases/exp-<sha>-<stamp>
    python3 locus.py --expected-release-root ... --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

EXIT_OK = 0
EXIT_LOCUS_MISMATCH = 3

RELEASE_SUBDIR = "release"
DEFAULT_MODULE = "speech_to_speech"


def expected_prefix(release_root: str) -> str:
    """The directory the import must land inside, with a trailing separator."""
    return os.path.realpath(os.path.join(release_root, RELEASE_SUBDIR)) + os.sep


def classify_locus(actual: str, release_root: str) -> str:
    """Best-effort human label for where the import actually came from.

    Purely diagnostic — the pass/fail decision is the prefix comparison, never
    this label.
    """
    real = os.path.realpath(actual)
    if f"{os.sep}site-packages{os.sep}" in real or real.endswith(os.sep + "site-packages"):
        return "site-packages"
    if os.sep + "releases" + os.sep in real:
        tail = real.split(os.sep + "releases" + os.sep, 1)[1]
        release_name = tail.split(os.sep, 1)[0]
        if release_name.startswith("exp-"):
            return "other-experiment-release" if not real.startswith(expected_prefix(release_root)) else "ok"
        return f"named-release:{release_name}"
    if os.sep + "julia_voice_v2" + os.sep not in real:
        return "working-tree-or-unknown"
    return "unknown"


def attest(release_root: str, module_name: str = DEFAULT_MODULE) -> dict[str, Any]:
    """Import the module and judge its resolved location. Never raises."""
    prefix = expected_prefix(release_root)
    result: dict[str, Any] = {
        "module": module_name,
        "expected_release_root": os.path.realpath(release_root),
        "expected_prefix": prefix,
        "ok": False,
        "actual": None,
        "classification": "import-failed",
        "detail": None,
    }

    try:
        module = __import__(module_name)
    except Exception as exc:  # noqa: BLE001 - an unimportable package is a failure, not a crash
        result["detail"] = f"{type(exc).__name__}: {exc}"
        return result

    actual_file = getattr(module, "__file__", None)
    if not actual_file:
        result["detail"] = "module has no __file__ (namespace package?)"
        return result

    actual = os.path.realpath(actual_file)
    result["actual"] = actual
    result["actual_module_path"] = os.path.realpath(getattr(module, "__path__", [""])[0]) if getattr(module, "__path__", None) else None
    result["ok"] = actual.startswith(prefix)
    result["classification"] = "ok" if result["ok"] else classify_locus(actual, release_root)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed import-locus attestation.")
    parser.add_argument("--expected-release-root", required=True,
                        help="Release root that contains the release/ tree, e.g. /root/.../releases/exp-<sha>-<stamp>")
    parser.add_argument("--module", default=DEFAULT_MODULE)
    parser.add_argument("--json", action="store_true", help="emit the result as JSON")
    args = parser.parse_args(argv)

    result = attest(args.expected_release_root, args.module)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"IMPORT LOCUS ATTESTATION ({result['module']})")
        print(f"  expected prefix : {result['expected_prefix']}")
        print(f"  actual          : {result['actual'] or '<unresolved>'}")
        print(f"  classification  : {result['classification']}")
        if result["detail"]:
            print(f"  detail          : {result['detail']}")
        print(f"  verdict         : {'PASS' if result['ok'] else 'FAIL'}")

    if not result["ok"]:
        print(
            "FATAL: import locus is not the experiment release — refusing to continue. "
            "Expected the package to live under "
            f"{result['expected_prefix']} but it resolved to {result['actual'] or '<unresolved>'} "
            f"({result['classification']}).",
            file=sys.stderr,
        )
        return EXIT_LOCUS_MISMATCH
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
