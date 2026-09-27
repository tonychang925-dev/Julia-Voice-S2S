# VOICE SERVER IMMUTABILITY RULE v1

FROZEN: 2026-09-15
SCOPE: every server experiment, not only ElevenLabs
STATUS: normative. Overrides convenience, deadlines, and "just this once".

This document is the deployment-authority companion to
`docs/JULIA_VOICE_MANUAL_DEPLOYMENT_SOP_v1.1.md` (SOP v1.1). SOP v1.1 remains the
only authority for *how* to deploy. This document is the authority for *what may
be touched on a server while doing so*. Both are binding.

---

## Core invariant

```text
Repository = Source Authority
Server     = Runtime Evidence

仓库是什么，服务器就跑什么。
服务器不产生第四份代码。
```

The server is a **deploy-only runtime**. It is never a development environment.
If something must be authored, edited, patched, installed or improvised, it
belongs in a repository commit, and only then may it reach a server.

---

## The rule

1. Production server is not a development environment.
2. No code may be authored, edited, patched, or repaired on the server.
3. No package or dependency may be installed or modified on the server for an experiment.
4. All executable logic must originate from a reviewed repository commit.
5. All deployments must be built from an exact Git SHA.
6. Server-side deployment may only materialize immutable repository-built artifacts.
7. Any missing dependency, test capability, configuration, or behavior is a repository/artifact defect.
8. Such defects must be fixed locally, committed, reviewed, rebuilt, and redeployed.
9. Runtime-generated state is permitted only in explicitly defined run/log/cache locations.
10. Server state is evidence, not source authority.

---

## Mutation policy

### Allowed

```text
upload repository-built immutable artifact
verify artifact and manifest
create a new immutable release directory from that artifact
create repository-defined runtime directories
start / stop a repository-defined experimental process
write runtime-generated logs / pids / cache only to declared namespaces
inject existing secret VALUES through repository-defined environment interfaces
```

### Forbidden

```text
server-side source editing
server-side config editing
pip install / conda install / apt install
package upgrades
site-packages mutation
copying loose source files
copying loose test files
ad-hoc test harness creation
sed / vim / nano patches
server-side cherry-pick
server-side git repair
single-file hotfix
manual dependency repair
```

### The missing-capability rule

```text
If the deployed artifact lacks a dependency, test capability, configuration,
script, or runtime behavior:

RESULT = DEPLOYMENT_ARTIFACT_INCOMPLETE
STOP.
Return to the repository.
```

**Do not provide a server workaround.** There is no "temporary" exception, and an
"isolated" environment on the server is still a mutation of the server.

---

## Secrets

A secret VALUE may be injected from the server's existing secret/environment
store. Everything else about it is repository code: the **name** of the variable,
the interface that reads it, and the rule that it is never passed as a command
line argument, never placed in a URL, never written into an artifact or a
manifest, and never logged.

---

## Consequences for experiments

An experiment must be isolated from production at every one of these layers:

```text
filesystem · python environment · runtime process · ports
run directory · logs · temporary files · configuration · release activation
```

Isolation is achieved by the artifact's own definitions, not by hand on the
server. When server-native validation is wanted, the test capability must itself
be a build product of the repository:

```text
repo
├── runtime source
├── test definitions
├── deployment manifest
└── reproducible test runner
        ↓ canonical build
immutable experimental artifact
        ↓
server executes only:  <artifact>/run_tests
```

See `docs/authority/VOICE_EL_P0D1_IMMUTABLE_EXPERIMENT_DESIGN.md` for the
namespace contract, the import-locus gate, and the native gate set.

---

## Why this exists

The first attempt at deploying the ElevenLabs experiment reached its native-test
gate and found that the server had no pytest and the artifact shipped no tests.
The available shortcut — create a venv on the server, install pytest, copy the
test files up — is forbidden by rules 2, 3 and 6. The correct response was
`DEPLOYMENT_ARTIFACT_INCOMPLETE`, a return to the repository, and this rule.

Recorded so the shortcut is never taken: a server that can be edited is a server
whose state can no longer be evidence.
