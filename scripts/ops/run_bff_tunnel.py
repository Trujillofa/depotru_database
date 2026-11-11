#!/usr/bin/env python3
"""Run a public tunnel to the local BFF and optionally sync Magento base_url.

Modes (env BFF_TUNNEL_MODE):
  named — cloudflared tunnel run --token $CLOUDFLARE_TUNNEL_TOKEN  (stable hostname)
  quick — cloudflared tunnel --url http://127.0.0.1:$BFF_PORT
          parses trycloudflare.com URL and optionally updates Magento config

Env:
  CLOUDFLARE_TUNNEL_TOKEN   required for named
  BFF_PORT                 default 8000
  BFF_SYNC_MAGENTO=1       update Magento dt_assistant/general/base_url on URL change
  MAGENTO_SSH_*            see deploy/bff/env.bff.example
  CLOUDFLARED_BIN          default .tools/cloudflared
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CF = REPO / ".tools" / "cloudflared"
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def log(msg: str) -> None:
    print(msg, flush=True)


def cloudflared_bin() -> str:
    env = os.getenv("CLOUDFLARED_BIN", "").strip()
    if env and Path(env).is_file():
        return env
    if DEFAULT_CF.is_file():
        return str(DEFAULT_CF)
    which = subprocess.run(["which", "cloudflared"], capture_output=True, text=True)
    if which.returncode == 0 and which.stdout.strip():
        return which.stdout.strip()
    raise SystemExit("cloudflared not found — install to .tools/cloudflared")


def _magento_roots(primary: str) -> list[str]:
    """Production root plus sibling staging/ when present on the same host."""
    roots = [primary.rstrip("/")]
    staging = roots[0] + "/staging"
    if staging not in roots:
        roots.append(staging)
    return roots


def sync_magento_base_url(url: str) -> bool:
    """Push quick-tunnel URL into Magento dt_assistant/general/base_url over SSH.

    Returns True when every reachable Magento root accepted the update.
    """
    if os.getenv("BFF_SYNC_MAGENTO", "0").strip() not in ("1", "true", "yes"):
        log("BFF_SYNC_MAGENTO disabled — Magento base_url not updated")
        return False

    # Reuse shared Magento SSH config (password via MAGENTO_SSH_PASSWORD or
    # sibling depositotrujillo.co/config/env.php; key optional with passphrase).
    src = REPO / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    try:
        from business_analyzer.core.website_stock_magento_ssh import (  # noqa: WPS433
            MagentoSshConfig,
            _ssh_connect,
            _ssh_exec,
        )
    except ImportError as exc:
        log(f"Magento SSH helpers unavailable — skip base_url sync: {exc}")
        return False

    cfg = MagentoSshConfig.from_env()
    if not cfg:
        log(
            "Magento SSH not configured "
            "(set MAGENTO_SSH_PASSWORD or MAGENTO_ENV_PHP / config/env.php) "
            "— skip base_url sync"
        )
        return False

    # Basic URL safety: only allow https quick/named hostnames we control.
    if not url.startswith("https://") or any(c in url for c in " \t\n\r'\";&|"):
        log(f"Refusing to sync unsafe tunnel URL: {url!r}")
        return False

    ok_all = True
    try:
        client = _ssh_connect(cfg)
        cmds = [
            f"php bin/magento config:set dt_assistant/general/base_url '{url}'",
            "php bin/magento config:set dt_assistant/general/enabled 1",
            # Targeted clean only — never cache:flush.
            "php bin/magento cache:clean config full_page",
        ]
        for remote in _magento_roots(cfg.magento_root):
            # Staging may not exist / may lack Assistant module — skip quietly.
            probe = (
                f"test -f {remote}/bin/magento && "
                f"test -d {remote}/app/code/DepositoTrujillo/Assistant"
            )
            _ls, _err, ls_code = _ssh_exec(client, probe, working_dir="/", timeout=30)
            if ls_code != 0:
                log(f"Skip Magento root (no Assistant module): {remote}")
                continue
            root_ok = True
            for cmd in cmds:
                _out, err, code = _ssh_exec(
                    client, cmd, working_dir=remote, timeout=120
                )
                if code != 0:
                    root_ok = False
                    ok_all = False
                    log(f"Magento cmd failed on {remote} ({code}): {err[-300:]}")
                else:
                    label = (
                        cmd.split("config:set")[-1][:60]
                        if "config:set" in cmd
                        else "cache"
                    )
                    log(f"Magento OK ({remote}): {label}")
            if root_ok:
                log(f"Synced Magento base_url on {remote} → {url}")
        client.close()
    except Exception as exc:  # noqa: BLE001
        log(f"Magento sync failed: {exc}")
        return False
    return ok_all


def run_named(token: str) -> int:
    bin_cf = cloudflared_bin()
    log("Starting named Cloudflare tunnel (stable hostname)")
    proc = subprocess.Popen(
        [bin_cf, "tunnel", "--no-autoupdate", "run", "--token", token],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    def _stop(signum, frame):  # noqa: ARG001
        proc.terminate()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    return proc.wait()


def run_quick(port: int) -> int:
    bin_cf = cloudflared_bin()
    log(f"Starting quick tunnel → http://127.0.0.1:{port}")
    proc = subprocess.Popen(
        [
            bin_cf,
            "tunnel",
            "--no-autoupdate",
            "--url",
            f"http://127.0.0.1:{port}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    last_url: str | None = None
    sync_ok = False
    last_sync_attempt = 0.0
    sync_retry_s = float(os.getenv("BFF_SYNC_RETRY_SECONDS") or "60")
    sync_lock = threading.Lock()
    sync_thread: threading.Thread | None = None

    def _run_sync(url: str, reason: str) -> None:
        nonlocal sync_ok, last_sync_attempt
        log(f"Magento sync ({reason}) → {url}")
        ok = sync_magento_base_url(url)
        with sync_lock:
            # Ignore stale completions after a newer URL was published.
            if last_url == url:
                sync_ok = ok
                last_sync_attempt = time.time()

    def _start_sync(url: str, reason: str) -> None:
        nonlocal sync_thread
        # Never block the cloudflared stdout reader on Magento SSH.
        t = threading.Thread(target=_run_sync, args=(url, reason), daemon=True)
        sync_thread = t
        t.start()

    def _stop(signum, frame):  # noqa: ARG001
        proc.terminate()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        m = URL_RE.search(line)
        if m:
            url = m.group(0)
            if url != last_url:
                last_url = url
                with sync_lock:
                    sync_ok = False
                    last_sync_attempt = time.time()
                log(f"Public URL: {url}")
                # persist for operators
                out = REPO / "deploy" / "bff" / "last_tunnel_url.txt"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(url + "\n")
                _start_sync(url, "url-change")
        # Retry Magento sync if the URL is known but prior sync failed
        # (SSH blip / Magento busy). Avoids permanent FAB 502 drift.
        with sync_lock:
            need_retry = (
                bool(last_url)
                and not sync_ok
                and (time.time() - last_sync_attempt) >= sync_retry_s
                and not (sync_thread and sync_thread.is_alive())
            )
            retry_url = last_url
        if need_retry and retry_url:
            _start_sync(retry_url, "retry")

    return proc.wait()


def main() -> int:
    mode = (os.getenv("BFF_TUNNEL_MODE") or "quick").strip().lower()
    port = int(os.getenv("BFF_PORT") or "8000")
    token = (os.getenv("CLOUDFLARE_TUNNEL_TOKEN") or "").strip()

    # Wait briefly for BFF (any HTTP response = process is up; /v1 may require API key)
    for _ in range(30):
        try:
            import urllib.error
            import urllib.request

            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            except urllib.error.HTTPError:
                # 4xx still means the server is listening
                pass
            break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    else:
        log(f"WARNING: BFF not healthy on :{port} yet — tunnel will still start")

    if mode == "named":
        if not token:
            log("CLOUDFLARE_TUNNEL_TOKEN required for BFF_TUNNEL_MODE=named")
            return 2
        return run_named(token)

    return run_quick(port)


if __name__ == "__main__":
    raise SystemExit(main())
