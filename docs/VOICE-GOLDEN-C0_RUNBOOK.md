STATUS: HISTORICAL / SUPERSEDED
SUPERSEDED BY: docs/RMD3G_PRODUCTION_RUNBOOK.md and docs/authority/CURRENT_AUTHORITY.md
DO NOT USE FOR CURRENT PRODUCTION OPERATIONS

# VOICE-GOLDEN-C0 — AutoDL Execution Runbook

## Prerequisites
- :7860 and :8765 must be running
- Julia-Voice-S2S repo cloned to AutoDL or script copied manually

## Step 1: Copy snapshot script to AutoDL
```bash
# On Mac:
scp scripts/snapshot_runtime_provenance.sh root@<autodl>:/root/

# Or clone the repo:
git clone https://github.com/tonychang925-dev/Julia-Voice-S2S.git /root/Julia-Voice-S2S
```

## Step 2: Run snapshot
```bash
cd /root/Julia-Voice-S2S  # or wherever the script is
bash scripts/snapshot_runtime_provenance.sh
```

Output: `RUNTIME_PROVENANCE.md`

## Step 3: Verify Golden Gates

### Gate 1 — :7860 identity
```
:7860 PID != NOT RUNNING
→ exact frontend runtime source path
→ git commit matches frontend/ import
→ working_tree_dirty captured
```

### Gate 2 — :8765 identity
```
:8765 PID != NOT RUNNING
→ S2S_PYTHON == /proc/<pid>/exe (NOT fallback python3)
→ package_path points to actual running code
→ package_tree_sha256 matches after import
```

### Gate 3 — Launcher identity
```
launch_s2s.py hash matches imported copy
start_frontend.sh hash matches imported copy
```

### Gate 4 — Dirty modifications preserved
```
All staged + unstaged + untracked changes from RUNTIME_PROVENANCE.md
are present in the imported source.
```

## Step 4: Import sources
```bash
cd /root/Julia-Voice-S2S

# From the paths in RUNTIME_PROVENANCE.md:
cp -r <FRONTEND_DIR>/* frontend/
cp -r <S2S_PACKAGE_DIR>/* s2s/

# Copy launchers
cp /root/julia_voice_v2/golden/launch_s2s.py deploy/autodl/
cp /root/julia_voice_v2/golden/start_frontend.sh deploy/autodl/
```

## Step 5: Verify imported hashes
```bash
# Compare against RUNTIME_PROVENANCE.md values
sha256sum frontend/main.js
python3 -c "
import hashlib
from pathlib import Path
digest = hashlib.sha256()
for fp in sorted(Path('s2s').rglob('*.py')):
    digest.update(str(fp.relative_to('s2s')).encode())
    digest.update(fp.read_bytes())
print('imported package_tree_sha256:', digest.hexdigest())
"
```

## Step 6: Fill UPSTREAM.lock
Edit `UPSTREAM.lock` with actual values from RUNTIME_PROVENANCE.md.

## Step 7: Commit
```bash
git add frontend/ s2s/ deploy/autodl/ UPSTREAM.lock RUNTIME_PROVENANCE.md
git commit -m "VOICE-GOLDEN-C0: Import deployed Voice/S2S runtime baseline

Source: AutoDL $(hostname)
Date: $(date -I)

frontend: <FRONTEND_COMMIT>
s2s: <S2S_VERSION>
package_tree_sha256: <HASH>

All four Golden Gates PASS."
git tag voice-golden-pre-c1b-20260809
git push origin main --tags
```

## Next
After this commit → `feature/voice-c1b-transport-binding` → apply patches from `patches/voice-c1b/`
