#!/usr/bin/env python3
"""
InvestIQ Pipeline Watchdog
===========================
Monitors daily_update.py (or any long-running pipeline), detects stalls/crashes,
attempts one automatic restart, and sends Telegram notifications.

Usage (called by daily_update.py automatically — no need to run manually):
  python3 scripts/pipeline_watchdog.py --pid 12345 --log logs/daily_update.log

Or standalone:
  python3 scripts/pipeline_watchdog.py --cmd "python3 scripts/daily_update.py --skip-cache"
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime

WORKSPACE     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORKSPACE)
from scripts.telegram_utils import send_telegram

# Watchdog tunables
POLL_INTERVAL    = 60        # seconds between liveness checks
STALL_TIMEOUT    = 45 * 60  # seconds with no log growth = stall (45 min)
MAX_RUNTIME      = 3 * 3600 # hard timeout — 3 hours
MAX_RETRIES      = 1        # auto-restart attempts


# ── Helpers ───────────────────────────────────────────────────────────────────

def pid_alive(pid):
    """Return True if process with given PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def log_tail(log_path, n=8):
    """Return last n lines of log file as a string."""
    if not log_path or not os.path.exists(log_path):
        return '(no log file)'
    try:
        with open(log_path, 'rb') as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 4096))
            tail = f.read().decode('utf-8', errors='replace').splitlines()
            return '\n'.join(tail[-n:])
    except Exception:
        return '(could not read log)'


def log_mtime(log_path):
    """Return last-modified timestamp of log file, or 0."""
    try:
        return os.path.getmtime(log_path)
    except Exception:
        return 0


def elapsed_str(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f'{h}h {m}m'
    return f'{m}m {s}s'


def launch_pipeline(cmd, log_path):
    """Launch the pipeline as a background subprocess, redirecting to log."""
    log_dir = os.path.dirname(log_path)
    os.makedirs(log_dir, exist_ok=True)
    with open(log_path, 'a') as logf:
        logf.write(f'\n\n[watchdog] Launching at {datetime.now()}\n')
    with open(log_path, 'a') as logf:
        proc = subprocess.Popen(
            cmd, shell=True, cwd=WORKSPACE,
            stdout=logf, stderr=logf
        )
    return proc.pid


# ── Core watch loop ───────────────────────────────────────────────────────────

def watch(pid, log_path, cmd, retry_count=0):
    """
    Monitor a running PID. Returns exit status string:
      'success', 'failed', 'stalled', 'timeout', 'restarted'
    """
    start_time  = time.time()
    last_log_mt = log_mtime(log_path)
    last_log_check = time.time()

    print(f'[watchdog] Watching PID {pid}  log={log_path}')

    while True:
        time.sleep(POLL_INTERVAL)
        now     = time.time()
        elapsed = now - start_time

        # ── Hard timeout ──────────────────────────────────────────────────────
        if elapsed > MAX_RUNTIME:
            print(f'[watchdog] MAX_RUNTIME exceeded ({elapsed_str(elapsed)})')
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
            send_telegram(
                f'⏰ *Pipeline TIMEOUT* after {elapsed_str(elapsed)}\n'
                f'PID {pid} was killed (exceeded {MAX_RUNTIME//3600}h limit)\n\n'
                f'Last log:\n```\n{log_tail(log_path, 5)}\n```'
            )
            return 'timeout'

        # ── Process dead? ─────────────────────────────────────────────────────
        if not pid_alive(pid):
            # Give it 5s for log flush, then check exit evidence
            time.sleep(5)
            tail = log_tail(log_path, 10)

            # Success markers written by daily_update.py
            success = (
                'All steps complete' in tail
                or 'Daily Pipeline complete' in tail
                or 'Git push complete' in tail
            )
            fail_markers = (
                'failed' in tail.lower()
                or 'error' in tail.lower()
                or 'traceback' in tail.lower()
            )

            if success:
                print(f'[watchdog] Process exited successfully ({elapsed_str(elapsed)})')
                return 'success'

            # Died unexpectedly
            print(f'[watchdog] Process {pid} died after {elapsed_str(elapsed)}')
            send_telegram(
                f'💀 *Pipeline crashed* after {elapsed_str(elapsed)}\n'
                f'PID {pid} exited unexpectedly.\n\n'
                f'Last log:\n```\n{log_tail(log_path, 6)}\n```'
            )

            # ── Auto-restart ──────────────────────────────────────────────────
            if retry_count < MAX_RETRIES and cmd:
                send_telegram(
                    f'🔄 *Auto-restarting pipeline* (attempt {retry_count + 1}/{MAX_RETRIES})…'
                )
                new_pid = launch_pipeline(cmd, log_path)
                print(f'[watchdog] Restarted as PID {new_pid}')
                time.sleep(10)  # wait for subprocess to register
                return watch(new_pid, log_path, cmd, retry_count + 1)
            else:
                send_telegram(
                    f'🚫 *Pipeline failed — no more retries*\n'
                    f'Check logs: `logs/daily_update.log`\n'
                    f'To run manually:\n'
                    f'`cd ~/.openclaw/workspace && python3 scripts/daily_update.py --skip-cache`'
                )
                return 'failed'

        # ── Stall detection (log not growing) ─────────────────────────────────
        current_mt = log_mtime(log_path)
        if current_mt != last_log_mt:
            last_log_mt    = current_mt
            last_log_check = now
        else:
            stall_duration = now - last_log_check
            if stall_duration > STALL_TIMEOUT:
                print(f'[watchdog] STALL detected — no log activity for {elapsed_str(stall_duration)}')
                send_telegram(
                    f'⚠️ *Pipeline STALLED* (no activity for {elapsed_str(stall_duration)})\n'
                    f'PID {pid} still alive but log frozen.\n\n'
                    f'Last log:\n```\n{log_tail(log_path, 5)}\n```\n\n'
                    f'Killing and restarting…'
                )
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
                time.sleep(5)

                if retry_count < MAX_RETRIES and cmd:
                    new_pid = launch_pipeline(cmd, log_path)
                    print(f'[watchdog] Restarted stalled job as PID {new_pid}')
                    return watch(new_pid, log_path, cmd, retry_count + 1)
                else:
                    send_telegram(
                        f'🚫 *Stall restart failed — manual intervention needed*\n'
                        f'`python3 scripts/daily_update.py --skip-cache`'
                    )
                    return 'stalled'

        # ── Heartbeat log every 30 min ────────────────────────────────────────
        if int(elapsed) % (30 * 60) == 0 and elapsed > 0:
            print(f'[watchdog] Still running — {elapsed_str(elapsed)} elapsed, PID {pid} alive')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='InvestIQ Pipeline Watchdog')
    parser.add_argument('--pid',  type=int,  help='PID of already-running pipeline process')
    parser.add_argument('--log',  default=os.path.join(WORKSPACE, 'logs', 'daily_update.log'),
                        help='Path to pipeline log file')
    parser.add_argument('--cmd',  default=None,
                        help='Shell command to launch pipeline (used for restart)')
    args = parser.parse_args()

    if not args.pid:
        # No PID provided — launch the pipeline ourselves
        if not args.cmd:
            args.cmd = f'{sys.executable} {os.path.join(WORKSPACE, "scripts", "daily_update.py")}'
        print(f'[watchdog] No PID given, launching: {args.cmd}')
        pid = launch_pipeline(args.cmd, args.log)
        print(f'[watchdog] Launched PID {pid}')
        time.sleep(5)
    else:
        pid = args.pid

    result = watch(pid, args.log, args.cmd)
    print(f'[watchdog] Final result: {result}')
    sys.exit(0 if result == 'success' else 1)


if __name__ == '__main__':
    main()
