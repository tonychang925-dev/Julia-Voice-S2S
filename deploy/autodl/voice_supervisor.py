#!/usr/bin/env python3
"""Voice Stack Supervisor — single process authority for :8765 + :7860.

CSA-P0: Exactly ONE authority to start/stop/restart Voice services.

Usage:
  python3 voice_supervisor.py start      # idempotent: start if not running
  python3 voice_supervisor.py stop       # graceful shutdown of owned PIDs
  python3 voice_supervisor.py restart    # deterministic restart
  python3 voice_supervisor.py status     # health check + PID ownership
"""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

STATE_DIR = Path("/tmp/julia-voice-supervisor")
PID_FILE_S2S = STATE_DIR / "s2s.pid"
PID_FILE_FRONTEND = STATE_DIR / "frontend.pid"
LOCK_FILE = STATE_DIR / "supervisor.lock"

GOLDEN_ROOT = Path("/root/julia_voice_v2/golden")
S2S_LAUNCHER = GOLDEN_ROOT / "launch_s2s.py"
FRONTEND_LAUNCHER = GOLDEN_ROOT / "start_frontend.sh"
S2S_LOG = GOLDEN_ROOT / "logs" / "s2s.log"
PYTHON = "/root/miniconda3/bin/python"


def _ensure_state_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _acquire_lock():
    """Exclusive lock for all supervisor operations."""
    import fcntl
    _ensure_state_dir()
    fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return fd


def _release_lock(fd):
    import fcntl
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


def _is_port_listening(port):
    """Check if port is in LISTEN state."""
    try:
        result = subprocess.run(
            ["ss", "-lntp"], capture_output=True, text=True, timeout=5
        )
        return f":{port}" in result.stdout
    except Exception:
        return False


def _is_pid_alive(pid):
    """Check if a process with given PID exists."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _read_pid(pid_file):
    """Read PID from file, return None if invalid."""
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text().strip())
        return pid if _is_pid_alive(pid) else None
    except (ValueError, OSError):
        return None


def _write_pid(pid_file, pid):
    pid_file.write_text(str(pid))


def _stop_service(name, pid_file, port):
    """Stop a service: SIGTERM → wait → SIGKILL → verify port released."""
    pid = _read_pid(pid_file)
    if pid is None:
        # Check if something else is on our port
        if _is_port_listening(port):
            print(f"[{name}] WARNING: port :{port} occupied by unknown process")
            # Force-claim: find the PID listening on this port
            result = subprocess.run(
                ["ss", "-lntp"], capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line:
                    print(f"[{name}] Found: {line.strip()}")
        else:
            print(f"[{name}] not running")
        return

    print(f"[{name}] stopping PID {pid}...")
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass

    # Wait up to 10s for graceful exit
    for _ in range(20):
        if not _is_pid_alive(pid):
            break
        time.sleep(0.5)

    # Force kill if still alive
    if _is_pid_alive(pid):
        print(f"[{name}] SIGKILL PID {pid}")
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        time.sleep(1)

    # Wait for port release
    for _ in range(10):
        if not _is_port_listening(port):
            break
        time.sleep(0.5)

    pid_file.unlink(missing_ok=True)
    print(f"[{name}] stopped")


def _start_s2s():
    """Start S2S via launcher. launcher does its own pkill internally."""
    log_dir = S2S_LOG.parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Save old log before launcher truncates it
    if S2S_LOG.exists():
        evidence_dir = STATE_DIR / "evidence"
        evidence_dir.mkdir(exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        backup = evidence_dir / f"s2s_crash_{ts}.log"
        backup.write_text(S2S_LOG.read_text())
        print(f"[s2s] previous log preserved: {backup.name}")

    subprocess.run(
        [PYTHON, str(S2S_LAUNCHER)],
        capture_output=True, timeout=30,
    )

    # Wait for :8765 to come up (model loading can take minutes)
    print("[s2s] waiting for :8765 (model loading)...")
    for i in range(120):  # up to 4 minutes
        if _is_port_listening(8765):
            # Find the actual PID listening on :8765
            result = subprocess.run(
                ["ss", "-lntp"], capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if ":8765" in line:
                    # Extract PID from ss output
                    parts = line.strip().split()
                    for p in parts:
                        if p.startswith("pid="):
                            pid_str = p.split("=")[1].split(",")[0]
                            pid = int(pid_str)
                            _write_pid(PID_FILE_S2S, pid)
                            print(f"[s2s] READY — PID {pid} on :8765 (took {i * 2}s)")
                            return True
        time.sleep(2)

    print("[s2s] FAILED to start within timeout")
    return False


def _start_frontend():
    """Start frontend via shell launcher."""
    try:
        proc = subprocess.Popen(
            ["bash", str(FRONTEND_LAUNCHER)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # start_frontend.sh uses exec uvicorn, so bash exits and uvicorn becomes child
        # Wait for the uvicorn process to appear
        time.sleep(3)

        # Find uvicorn PID on :7860
        result = subprocess.run(
            ["ss", "-lntp"], capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            if ":7860" in line:
                parts = line.strip().split()
                for p in parts:
                    if p.startswith("pid="):
                        pid_str = p.split("=")[1].split(",")[0]
                        pid = int(pid_str)
                        _write_pid(PID_FILE_FRONTEND, pid)
                        print(f"[frontend] READY — PID {pid} on :7860")
                        return True

        print("[frontend] FAILED — no listener on :7860 after 3s")
        return False
    except Exception as e:
        print(f"[frontend] FAILED: {e}")
        return False


def cmd_status():
    """Show current Voice stack status."""
    _ensure_state_dir()
    s2s_pid = _read_pid(PID_FILE_S2S)
    fe_pid = _read_pid(PID_FILE_FRONTEND)
    s2s_port = _is_port_listening(8765)
    fe_port = _is_port_listening(7860)

    print("VOICE STACK STATUS")
    print(f"  S2S      :8765  PID={s2s_pid or 'none':>6}  port={'UP' if s2s_port else 'DOWN'}")
    print(f"  Frontend :7860  PID={fe_pid or 'none':>6}  port={'UP' if fe_port else 'DOWN'}")

    if s2s_pid and not s2s_port:
        print("  ⚠ S2S PID exists but port not listening — likely crashed or loading")
    if fe_pid and not fe_port:
        print("  ⚠ Frontend PID exists but port not listening")

    s2s_health = s2s_pid and s2s_port
    fe_health = fe_pid and fe_port
    if s2s_health and fe_health:
        print("\n  ✅ Voice stack healthy")
    else:
        print("\n  ❌ Voice stack degraded")
        sys.exit(1)


def cmd_start():
    """Idempotent start: only start services that aren't running."""
    fd = _acquire_lock()
    try:
        _ensure_state_dir()

        # S2S
        if _read_pid(PID_FILE_S2S) and _is_port_listening(8765):
            print("[s2s] already running")
        else:
            print("[s2s] starting...")
            if not _start_s2s():
                print("[s2s] FAILED")
                sys.exit(1)

        # Frontend
        if _read_pid(PID_FILE_FRONTEND) and _is_port_listening(7860):
            print("[frontend] already running")
        else:
            print("[frontend] starting...")
            if not _start_frontend():
                print("[frontend] FAILED")
                sys.exit(1)

        print("\n✅ Voice stack started")
        cmd_status()
    finally:
        _release_lock(fd)


def cmd_stop():
    """Graceful stop of all owned services."""
    fd = _acquire_lock()
    try:
        _stop_service("s2s", PID_FILE_S2S, 8765)
        _stop_service("frontend", PID_FILE_FRONTEND, 7860)
        print("\n✅ Voice stack stopped")
    finally:
        _release_lock(fd)


def cmd_restart():
    """Deterministic restart with exclusive lock."""
    fd = _acquire_lock()
    try:
        print("=== Voice Stack Restart ===\n")
        _stop_service("s2s", PID_FILE_S2S, 8765)
        _stop_service("frontend", PID_FILE_FRONTEND, 7860)
        time.sleep(2)
        print()
        if not _start_s2s():
            sys.exit(1)
        if not _start_frontend():
            sys.exit(1)
        print("\n✅ Voice stack restarted")
        cmd_status()
    finally:
        _release_lock(fd)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: voice_supervisor.py {start|stop|restart|status}")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "start":
        cmd_start()
    elif cmd == "stop":
        cmd_stop()
    elif cmd == "restart":
        cmd_restart()
    elif cmd == "status":
        cmd_status()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
