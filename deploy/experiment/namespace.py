#!/usr/bin/env python3
"""Repository-owned experiment namespace materialization (VOICE-EL-P0D-1-R1).

`namespace.env` ships *templates*. Both the artifact's native gate and the
launcher need the *concrete* roots, and they must agree exactly — a gate that
validates one namespace while the launcher creates another is worse than no
check at all.

There is therefore exactly one implementation, here, and two consumers:

  * ``run_tests``          imports this module and materializes in-process
  * ``launch_experiment.sh`` invokes it with ``--format shell`` and ``eval``s the
                            result, so the shell never re-implements expansion

The stamp is recovered from the release directory name (``exp-<sha7>-<stamp>``)
rather than generated afresh, so both consumers derive the same roots from the
same on-disk facts. No random value, no wall clock in the shared path.

Usage::

    python3 namespace.py --namespace-env <path> --release-root <path> \\
                         --sha <sha> [--stamp <stamp>] [--format shell|json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

SHA_PLACEHOLDER = "%SHA%"
STAMP_PLACEHOLDER = "%STAMP%"
SHA_LEN = 7

CONCRETE_KEYS = ("EXPERIMENT_RUN_ROOT", "EXPERIMENT_LOG_ROOT", "EXPERIMENT_TMP_ROOT")
TEMPLATE_KEYS = ("EXPERIMENT_RUN_ROOT_TEMPLATE", "EXPERIMENT_LOG_ROOT_TEMPLATE",
                 "EXPERIMENT_TMP_ROOT_TEMPLATE", "EXPERIMENT_RELEASE_ROOT_TEMPLATE")


def load_env_file(path: str) -> dict[str, str]:
    """Parse a simple KEY=VALUE file. No expansion, no shell execution."""
    values: dict[str, str] = {}
    if not os.path.isfile(path):
        return values
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def short_sha(sha: str) -> str:
    return sha[:SHA_LEN]


def stamp_from_release_root(release_root: str) -> str:
    """Recover the deployment stamp from ``<...>/exp-<sha7>-<stamp>``.

    Returns "" when the directory does not follow the convention, which makes
    the mismatch visible rather than inventing a value.
    """
    base = os.path.basename(os.path.realpath(release_root))
    parts = base.split("-")
    if len(parts) >= 3 and parts[0] == "exp":
        return "-".join(parts[2:])
    return ""


def materialize(namespace: dict[str, str], sha: str, stamp: str) -> dict[str, str]:
    """Expand every placeholder in every value. Total function, no partial fill."""
    out: dict[str, str] = {}
    for key, value in namespace.items():
        out[key] = value.replace(SHA_PLACEHOLDER, short_sha(sha)).replace(STAMP_PLACEHOLDER, stamp)
    return out


def concrete_for_release(namespace_env_path: str, release_root: str, sha: str,
                         stamp: str | None = None) -> dict[str, Any]:
    """Materialize the namespace and return it with the concrete roots resolved."""
    namespace = load_env_file(namespace_env_path)
    resolved_stamp = stamp if stamp is not None else stamp_from_release_root(release_root)
    concrete = materialize(namespace, sha, resolved_stamp)

    roots = {
        "EXPERIMENT_RELEASE_ROOT": os.path.realpath(release_root),
        "EXPERIMENT_RUN_ROOT": concrete.get("EXPERIMENT_RUN_ROOT_TEMPLATE", ""),
        "EXPERIMENT_LOG_ROOT": concrete.get("EXPERIMENT_LOG_ROOT_TEMPLATE", ""),
        "EXPERIMENT_TMP_ROOT": concrete.get("EXPERIMENT_TMP_ROOT_TEMPLATE", ""),
    }
    return {
        "sha": sha,
        "short_sha": short_sha(sha),
        "stamp": resolved_stamp,
        "roots": roots,
        "concrete": concrete,
        "unresolved": sorted(k for k, v in concrete.items() if SHA_PLACEHOLDER in v or STAMP_PLACEHOLDER in v),
        "missing_templates": sorted(k for k in TEMPLATE_KEYS if not namespace.get(k)),
    }


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize the experiment namespace contract.")
    parser.add_argument("--namespace-env", required=True)
    parser.add_argument("--release-root", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--stamp", default=None)
    parser.add_argument("--format", choices=("shell", "json"), default="json")
    args = parser.parse_args(argv)

    result = concrete_for_release(args.namespace_env, args.release_root, args.sha, args.stamp)

    if result["missing_templates"] or result["unresolved"]:
        print(f"FATAL: namespace contract is incomplete: missing={result['missing_templates']} "
              f"unresolved={result['unresolved']}", file=sys.stderr)
        return 2

    if args.format == "shell":
        for key in CONCRETE_KEYS:
            print(f"{key}={_shell_quote(result['roots'][key])}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
