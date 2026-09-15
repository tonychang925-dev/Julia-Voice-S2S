# VOICE-EL-P0D-1 — Immutable Experiment Design

DATE: 2026-09-15
BASE_SHA: `f472579b6f65c5c7f6308eda69095778087e0970`
BRANCH: `experiment/voice-elevenlabs-p0`
SERVER COMMANDS EXECUTED: **0** · SERVER MUTATIONS: **0** · DEPLOYMENT: **no**

Make the ElevenLabs experimental deployment fully repository-owned and
reproducible, so a future GPU deployment requires **no** development, package
installation, source modification, test copying, configuration editing or
ad-hoc harness creation on the server.

Governing rule: [`SERVER_IMMUTABILITY_RULE_v1.md`](SERVER_IMMUTABILITY_RULE_v1.md).

---

## 1. What changed, and where

| Workstream | Artifact |
|---|---|
| A — immutability in governance | `docs/authority/SERVER_IMMUTABILITY_RULE_v1.md`; pointer added to `docs/authority/CURRENT_AUTHORITY.md` |
| B — namespace contract | `deploy/experiment/namespace.env` |
| C — import-locus gate | `deploy/experiment/locus.py` |
| D — runtime provenance order | `deploy/experiment/run_tests` (sets `PYTHONPATH`, then attests, then gates) |
| E — self-contained native gate | `deploy/experiment/native_gate.py` (stdlib only, gates G1–G10) |
| F — websockets 12 compatibility | tests + a structural guard; see §7 |
| G — manifest extension | `scripts/build_s2s_release.py --experiment` |
| H — backup contract | §8 (defined, **not executed**) |
| I — experimental launcher | `deploy/experiment/launch_experiment.sh` + `runtime.args` |

All of it is inside the build: `--experiment` ships `deploy/experiment/` as
`experiment/` inside the artifact.

No production runtime code was touched. `s2s/` is unchanged except for zero
files; Qwen3, VAD, STT, LLM, frontend, AEC and Core are untouched.

---

## 2. What the server is asked to do (Workstreams D + I)

```text
receive the immutable artifact
  → verify it (manifest SHA, archive SHA)
  → materialize <release>/release/ and <release>/experiment/
  → execute ONE repository-defined command:  <release>/experiment/run_tests --expected-sha <sha>
  → execute ONE repository-defined command:  <release>/experiment/launch_experiment.sh --expected-sha <sha>
  → emit runtime evidence
```

Nothing else. No shell history, no retyped argument vector, no hand-built
environment.

---

## 3. Namespace contract (Workstream B)

Defined once, in `deploy/experiment/namespace.env`, shipped inside the artifact:

```text
EXPERIMENT_RELEASE_ROOT = /root/julia_voice_v2/releases/exp-%SHA%-%STAMP%
EXPERIMENT_RUN_ROOT     = /root/julia_voice_v2/run/exp-%SHA%
EXPERIMENT_LOG_ROOT     = /root/julia_voice_v2/logs/exp-%SHA%
EXPERIMENT_TMP_ROOT     = /root/julia_voice_v2/tmp/exp-%SHA%
EXPERIMENT_S2S_PORT     = 8865      (production holds 8765)
EXPERIMENT_FRONTEND_PORT= 7960      (production holds 7860)
```

`%SHA%` expands to the exact source commit. Consequences encoded in the contract
and enforced by tests and by the gate:

- an experiment never reads or writes the Golden `current` symlink
- an experiment never writes a generic scratch path
  (`/tmp/manifest.json`, `/tmp/_an`, `/tmp/_p0d_release_path` are exactly what the
  aborted P0D wrote; rule 9 exists to prevent a repeat)
- an experiment never collides with a production port

The file must also stay valid POSIX shell, because the launcher sources it. A
space-separated value list was caught by the test suite as a real defect during
this task and replaced with a colon-separated one.

---

## 4. Import-locus gate (Workstream C)

`deploy/experiment/locus.py` — fail-closed, reusable, invoked by both the runner
and the launcher.

```text
pass  ⟺  realpath(speech_to_speech.__file__)
          .startswith( realpath(<EXPERIMENT_RELEASE_ROOT>/release) + os.sep )
```

Everything else exits `3` and prints the expected prefix, the actual path and a
classification. Named failure loci: `site-packages`, `named-release:<name>`
(a Golden release), `other-experiment-release`, `working-tree-or-unknown`,
`import-failed`.

Why this is load-bearing: the server has an installed `speech_to_speech 0.2.12`
in site-packages — a **fourth body of code**, distinct from the Golden release
and from any experiment release. If it wins the import race, unreviewed code
runs and every downstream check still reports green. This is the same failure
class the runtime `CC-2-RT-S2S-FAILCLOSED` gate guards against.

---

## 5. Runtime provenance order (Workstream D)

`run_tests` is self-locating (`<release>/experiment/run_tests`), loads the
namespace contract, then performs exactly this order:

```text
resolve release root (from __file__, never guessed)
  → load repository namespace contract
  → put <release>/release at the FRONT of sys.path and PYTHONPATH
  → import speech_to_speech
  → attest __file__ (locus gate)          ← refuses here if the release did not win
  → run gates G1 … G10
```

There is no fallback to site-packages at any step.

---

## 6. Native gate set (Workstream E)

`deploy/experiment/native_gate.py` — **standard library only**. The server has no
pytest and rule 3 forbids installing one, so the deployment-critical assertions
were extracted into a runner that is itself a build product rather than shipping
the development framework to production.

| Gate | Assertion |
|---|---|
| NAMESPACE | tmp/run/log roots are repository-defined and not generic scratch |
| G1 | manifest `source_commit` equals the expected SHA; archive SHA matches on disk |
| G2 | import locus is the experiment release (refusal point) |
| G3 | required imports resolve (numpy, torch, websockets, openai, handler, pipeline) |
| G4 | installed websockets is inside the declared compatibility envelope |
| G5 | `--tts elevenlabs` parses through the real CLI |
| G6 | `qwen3` remains available **and** the default |
| G7 | the ElevenLabs handler constructs through the renamed kwargs |
| G8 | `build_pipeline(realtime)` forwards the ElevenLabs kwargs by identity |
| G9 | the realtime unit injects `CancelScope` + the speculative tracker into the handler |
| G10 | `PIPELINE_SR == 16000`, `pcm_16000` default, `BLOCK_BYTES == 1024` |

G8 and G9 stub only the model-loading stages (VAD/STT/LLM); the TTS dispatch
under test is real. No gate opens a network connection: anything needing a live
ElevenLabs session belongs to the later live-runtime gate and is **not** faked
here as native validation.

Ordering matters: a G2 failure returns immediately with exit `3` and later gates
are not run, because they would otherwise validate the wrong body of code.

---

## 7. websockets compatibility (Workstream F) — PASS

P0D-0 recorded the server at `websockets 12.0` against a locally validated
`15.0.1`.

**Resolution: the implementation is compatible with both, and it is proven, not
assumed.** No server upgrade, no workaround.

API surface the handler uses, and why each is stable across 12.x → 15.x:

| Use | 12.0 | 15.0.1 | Notes |
|---|---|---|---|
| `await module.connect(url)` | legacy `Connect` object | asyncio client | both awaitable; asserted by test |
| `await ws.send(str)` | ✅ | ✅ | unchanged |
| `await ws.recv()` | ✅ | ✅ | unchanged |
| `await ws.close()` (no args) | ✅ | ✅ | argument-free call asserted by test |
| auth | first-message `xi_api_key` field | same | **deliberately avoids** the `extra_headers` → `additional_headers` rename |

`read()` never cancels an in-flight `recv()` during normal operation — it polls
with `asyncio.wait(..., timeout=...)` — so the version-sensitive
cancel-a-pending-recv behaviour is confined to `close()`, where the connection is
being torn down anyway.

Evidence:

```text
websockets 15.0.1 : tests/test_experiment_deployment_safety.py        42 passed
websockets 12.0   : tests/test_experiment_deployment_safety.py +
                    tests/test_elevenlabs_tts_handler.py               67 passed
```

The 12.0 run used an isolated local venv (`/tmp/ws12venv`, local machine — never
a server). The transport-path tests (real `_connect()` → `_open()` with only the
network call patched) execute under both versions.

Declared envelope, asserted by G4: `>=12, <16`.

---

## 8. Backup contract (Workstream H) — DEFINED, NOT EXECUTED

Required before any future server mutation. It is not executed by this task and
this task performs no server access.

### Must capture

| Asset | Method |
|---|---|
| Golden `current` symlink target | `readlink -f` as a string |
| Golden `manifest.json` + `archive_sha256` | copy + sha256 |
| Golden critical file hashes | sha256 of the seven runtime-critical files |
| Golden release archive | copy + sha256 |
| production Python package inventory | `pip freeze` / `conda list --export` (inventory, **not** an archive) |
| `/opt/julia`, `/etc/julia` | full `tar` + per-file sha256 |
| `/etc/supervisor/conf.d` | full `tar` + per-file sha256 |
| `run/` + pid state for the Golden release | `tar` |
| logs (`/var/log/julia`, `run/*/s2s.log`) | `tar` |
| listener state | `/proc/net/tcp` snapshot |

### Rules for the backup itself

```text
- it uses its OWN immutable namespace, e.g. /root/julia_voice_v2/backup/<stamp>/
- it never writes a generic /tmp filename
- it is read-only with respect to everything it captures
- it runs BEFORE the mutation it protects against, not after
```

### Feasibility

Byte-for-byte is feasible for everything except `/root/miniconda3` (several GB —
an inventory is proportionate, and the governing rule forbids touching it at
all). Disk space is not a constraint: the P0D-0 baseline measured 13 G free on
`/` and 63 G on `autodl-tmp`.

### Recovery

Because the experiment is additive by rule — new `releases/exp-*`, new
`run/log/tmp/exp-*`, `current` unmoved, site-packages and `/opt`/`/etc` untouched
— recovery is deletion of the added paths plus re-verification. The backup exists
to **prove** nothing else moved, not to restore anything.

---

## 9. Testing

`tests/test_experiment_deployment_safety.py` (local / CI only, no server):

```text
immutability rule present and normative incl. all ten statements
authority index points at the rule
every payload file free of pip/conda/apt install, sed -i, cherry-pick
every payload file free of generic /tmp writes
namespace defines all four roots, no /tmp, no releases/current, no port collision
gate refuses a generic tmp root and accepts an experiment namespace
locus PASS for the expected release
locus FAIL for another experiment release / Golden release / site-packages / unimportable
locus prints both expected and actual
runner REFUSES when the release does not own the import (deliberately wrong locus)
runner reports manifest SHA mismatch
launcher dry-run plans a fully experiment-scoped namespace
launcher REFUSES a Golden (manual-*) release
launcher REFUSES the current symlink
launcher hardcodes no production port and never calls the supervisor
builder emits the experiment capability block, with no secret material
builder refuses --experiment when the payload is absent from the commit
websockets envelope: accepts the declared range, REJECTS an excluding range
handler uses no version-specific connect kwarg and no header auth
handler passes an awaitable to asyncio.wait_for on the installed version
handler calls close() with no arguments
```

Non-vacuity: the runner-refusal test injects a decoy `speech_to_speech` outside
the release and asserts exit `3`; the launcher tests assert exit `65` on Golden
names; G4 is asserted in both directions. The namespace test caught a genuine
defect (space-separated value) during this task.

---

## 10. Required analysis

**Can the experiment run without modifying the production Python environment?**
Yes. The release is selected by `PYTHONPATH`/`sys.path`, which precedes
site-packages. Nothing is installed. `websockets 12.0` and the rest are already
present, and the compatibility of the code with them is proven (§7) rather than
worked around.

**Can tests run against the exact experimental release while forcing locus?**
Yes, and the locus is now *checked*, not merely arranged: the runner prepends the
release and then attests `speech_to_speech.__file__` before any gate that imports
the pipeline. A wrong locus refuses (exit 3).

**Separate ports and run directories?** Yes — 8865/7960 and `run|log|tmp/exp-<sha>`,
all repository-defined in `namespace.env`, all asserted distinct from production.

**Must `releases/current` move?** No. Nothing in the design reads it, and the
launcher explicitly refuses to run from it or from any `manual-*` release.

**Can Golden remain untouched?** Yes. The seven Golden file hashes from P0D-0 are
the continuously checkable invariant.

**What guarantees restoration?** Additive-only deployment plus an unmoved
`current`; the Gate H backup supplies the proof, not the repair.

**What must be backed up first?** §8.

---

## 11. Final status

```text
TASK_ID: VOICE-EL-P0D-1

BASE_SHA: f472579b6f65c5c7f6308eda69095778087e0970

SERVER_COMMANDS_EXECUTED: 0
SERVER_MUTATIONS:         0

IMMUTABILITY_RULE:            PASS   (doc + authority pointer + static tests)
EXPERIMENT_NAMESPACE:         PASS   (namespace.env + gate precondition + tests)
IMPORT_LOCUS_FAIL_CLOSED:     PASS   (locus.py; PASS/FAIL proven on 5 loci)
SELF_CONTAINED_NATIVE_GATE:   PASS   (stdlib-only runner, G1-G10)
WEBSOCKETS_12_COMPATIBILITY:  PASS   (67 passed under 12.0; 42 under 15.0.1)
MANIFEST_EXTENSION:           PASS   (--experiment block; default build byte-identical)
BACKUP_CONTRACT:              PASS   (defined, not executed)

GOLDEN_RUNTIME_CODE_CHANGED: 0
QWEN3_BEHAVIOR_CHANGED:      0

RESULT: READY_FOR_SHA_REVIEW
```

**Default-build safety.** Extending the canonical builder could have disturbed
Golden builds. It does not: rebuilding `f472579` with the extended builder
reproduces the previously recorded archive SHA byte for byte
(`a6025b19cf11478112ae11073ff8c426766b1cf7a40ab446e737934569b1e0d8`). The new
behaviour is reachable only via the explicit `--experiment` flag.

---

## 12. Promotion sequence (unchanged, no step may be skipped)

```text
P0D-1 repository implementation            ← this task
  → exact candidate SHA
  → SHA-bound review
  → explicit Owner authorization
  → P0D-2 read-only preflight
  → explicit deployment authorization
  → isolated experimental deployment
```

Completing P0D-1 does **not** authorize server deployment. The aborted
experimental release `exp-f472579-20260915_072715` remains on the server as
evidence and must not be reused or patched; a future deployment builds a new
artifact from a new SHA.
