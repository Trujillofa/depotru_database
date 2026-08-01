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


def sync_magento_base_url(url: str) -> None:
    """Push quick-tunnel URL into Magento dt_assistant/general/base_url over SSH."""
    if os.getenv("BFF_SYNC_MAGENTO", "0").strip() not in ("1", "true", "yes"):
        return

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
        return

    cfg = MagentoSshConfig.from_env()
    if not cfg:
        log(
            "Magento SSH not configured "
            "(set MAGENTO_SSH_PASSWORD or MAGENTO_ENV_PHP / config/env.php) "
            "— skip base_url sync"
        )
        return

    # Basic URL safety: only allow https quick/named hostnames we control.
    if not url.startswith("https://") or any(c in url for c in " \t\n\r'\";&|"):
        log(f"Refusing to sync unsafe tunnel URL: {url!r}")
        return

    remote = cfg.magento_root
    try:
        client = _ssh_connect(cfg)
        cmds = [
            f"php bin/magento config:set dt_assistant/general/base_url '{url}'",
            "php bin/magento config:set dt_assistant/general/enabled 1",
            "php bin/magento cache:clean config full_page",
        ]
        for cmd in cmds:
            _out, err, code = _ssh_exec(client, cmd, working_dir=remote, timeout=120)
            if code != 0:
                log(f"Magento cmd failed ({code}): {err[-300:]}")
            else:
                label = (
                    cmd.split("config:set")[-1][:60] if "config:set" in cmd else "cache"
                )
                log(f"Magento OK: {label}")
        client.close()
        log(f"Synced Magento base_url → {url}")
    except Exception as exc:  # noqa: BLE001
        log(f"Magento sync failed: {exc}")


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
                log(f"Public URL: {url}")
                # persist for operators
                out = REPO / "deploy" / "bff" / "last_tunnel_url.txt"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(url + "\n")
                sync_magento_base_url(url)

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
