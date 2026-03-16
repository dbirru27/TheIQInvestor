#!/usr/bin/env python3
"""
Shared Telegram sender for InvestIQ scripts.

Uses the `openclaw message send` CLI — no hardcoded ports, no HTTP API.
The CLI auto-connects to whatever gateway is running, so port changes
never break notifications again.

Usage:
  from scripts.telegram_utils import send_telegram
  send_telegram('Hello!')

  # Custom chat id:
  from scripts.telegram_utils import Telegram
  Telegram(chat_id='-1001234567890').send('Hello group!')
"""

import os
import subprocess
import shutil
from typing import Optional

TELEGRAM_CHAT_ID = '690660528'

# Locate the openclaw binary (handles brew, volta, nvm, PATH installs)
def _find_openclaw() -> Optional[str]:
    # 1. Explicit env override
    override = os.environ.get('OPENCLAW_BIN')
    if override and os.path.isfile(override):
        return override
    # 2. PATH lookup
    found = shutil.which('openclaw')
    if found:
        return found
    # 3. Common install locations
    candidates = [
        '/opt/homebrew/bin/openclaw',
        '/usr/local/bin/openclaw',
        os.path.expanduser('~/.npm-global/bin/openclaw'),
        os.path.expanduser('~/.volta/bin/openclaw'),
        os.path.expanduser('~/.local/bin/openclaw'),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


class Telegram:
    def __init__(self, chat_id: str = TELEGRAM_CHAT_ID):
        self.chat_id = str(chat_id)
        self._bin: Optional[str] = None

    def _get_bin(self) -> Optional[str]:
        if not self._bin:
            self._bin = _find_openclaw()
        return self._bin

    def send(self, message: str) -> bool:
        """Send a Telegram message via openclaw CLI. Returns True on success."""
        bin_path = self._get_bin()
        if not bin_path:
            print('  [telegram] openclaw binary not found — message not sent')
            return False
        try:
            result = subprocess.run(
                [
                    bin_path, 'message', 'send',
                    '--channel', 'telegram',
                    '--target', self.chat_id,
                    '--message', message,
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                return True
            print(f'  [telegram] send failed (exit {result.returncode}): {result.stderr.strip()}')
            return False
        except subprocess.TimeoutExpired:
            print('  [telegram] send timed out')
            return False
        except Exception as e:
            print(f'  [telegram] send error: {e}')
            return False


# Module-level default sender
_default = Telegram()

def send_telegram(message: str, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    """Send a Telegram message. Silent on failure, never raises."""
    if chat_id != TELEGRAM_CHAT_ID:
        return Telegram(chat_id).send(message)
    return _default.send(message)


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    bin_path = _find_openclaw()
    print(f'openclaw binary: {bin_path}')
    ok = send_telegram('🐕 Watchdog self-test — telegram_utils.py CLI mode')
    print('Sent OK' if ok else 'Send FAILED')
