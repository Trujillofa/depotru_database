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
    if os.getenv("BFF_SYNC_MAGENTO", "0").strip() not in ("1", "true", "yes"):
        return
    try:
        import paramiko  # type: ignore[import-untyped]
    except ImportError:
        log("paramiko missing — skip Magento sync")
        return

    host = os.getenv("MAGENTO_SSH_HOST", "174.142.205.80")
    user = os.getenv("MAGENTO_SSH_USER", "deptrujillob2c")
    key_path = Path(
        os.getenv(
            "MAGENTO_SSH_KEY",
            str(Path.home() / "Projects/depositotrujillo.co/.ssh/id_rsa"),
        )
    )
    pass_file = Path(
        os.getenv(
            "MAGENTO_SSH_KEY_PASSPHRASE_FILE",
            str(Path.home() / "Projects/depositotrujillo.co/.ssh/MAGENTO_SSH_KEY.txt"),
        )
    )
    passphrase = os.getenv("MAGENTO_SSH_KEY_PASSPHRASE", "").strip()
    if not passphrase and pass_file.is_file():
        for ln in [x.strip() for x in pass_file.read_text().splitlines() if x.strip()]:
            if ln.upper().startswith("MAGENTO") or ln.startswith(
                ("Generating", "Enter", "Your ", "The ", "SHA256", "+", "|")
            ):
                continue
            if "key pair" in ln or ln.startswith("ssh-"):
                continue
            if len(ln) < 40:
                passphrase = ln
                break
    if not key_path.is_file() or not passphrase:
        log("Magento SSH key/passphrase not available — skip base_url sync")
        return

    remote = "/home/deptrujillob2c/public_html"
    try:
        pkey = paramiko.RSAKey.from_private_key_file(str(key_path), password=passphrase)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            host,
            username=user,
            pkey=pkey,
            allow_agent=False,
            look_for_keys=False,
            timeout=25,
            auth_timeout=25,
        )
        cmds = [
            f"cd {remote} && php bin/magento config:set dt_assistant/general/base_url '{url}'",
            f"cd {remote} && php bin/magento config:set dt_assistant/general/enabled 1",
            f"cd {remote} && php bin/magento cache:clean config full_page",
        ]
        for cmd in cmds:
            _, stdout, stderr = client.exec_command(cmd, timeout=120)
            code = stdout.channel.recv_exit_status()
            if code != 0:
                log(f"Magento cmd failed ({code}): {stderr.read().decode()[-300:]}")
            else:
                log(
                    f"Magento OK: {cmd.split('config:set')[-1][:60] if 'config:set' in cmd else 'cache'}"
                )
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
