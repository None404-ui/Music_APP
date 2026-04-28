#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


def _detect_ip(interface: str) -> str:
    try:
        out = subprocess.check_output(
            ["ipconfig", "getifaddr", interface],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if out:
            return out
    except Exception:
        pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _wait_http(url: str, timeout_sec: float = 10.0) -> bool:
    import urllib.request

    started = time.time()
    while time.time() - started < timeout_sec:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if getattr(resp, "status", 200) < 500:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Генерирует JSON для клиента и запускает LAN Hub + Django backend."
    )
    parser.add_argument("--interface", default="en0", help="Сетевой интерфейс для определения IP")
    parser.add_argument("--hub-port", type=int, default=8765, help="Порт LAN Audio Hub")
    parser.add_argument("--backend-port", type=int, default=8000, help="Порт Django backend")
    parser.add_argument(
        "--json-out",
        default="lan_connection.json",
        help="Куда сохранить JSON для клиента (относительно корня проекта или абсолютный путь)",
    )
    parser.add_argument(
        "--workspace",
        default=str(Path(__file__).resolve().parents[1]),
        help="Корень проекта musicAPP",
    )
    args = parser.parse_args()

    ip = _detect_ip(args.interface)
    workspace = Path(args.workspace).resolve()
    json_out = Path(args.json_out)
    if not json_out.is_absolute():
        json_out = workspace / json_out
    payload = {
        "server_ip": ip,
        "hub_url": f"http://{ip}:{args.hub_port}",
        "backend_url": f"http://{ip}:{args.backend_port}",
        "django_allowed_hosts": f"{ip},127.0.0.1,localhost",
        "workspace": str(workspace),
        "client_exports": {
            "CRATES_BACKEND_URL": f"http://{ip}:{args.backend_port}",
            "CRATES_LAN_HUB_URL": f"http://{ip}:{args.hub_port}",
        },
    }
    json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    env = os.environ.copy()
    env["CRATES_LAN_HUB_URL"] = payload["hub_url"]
    env["DJANGO_ALLOWED_HOSTS"] = payload["django_allowed_hosts"]
    env["LAN_HUB_HOST"] = "0.0.0.0"
    env["LAN_HUB_PORT"] = str(args.hub_port)

    print(f"Saved client JSON to: {json_out}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print()
    print("Starting LAN Hub...")
    hub_proc = subprocess.Popen(
        [sys.executable, "-m", "lan_audio_hub"],
        cwd=str(workspace),
        env=env,
    )
    try:
        if not _wait_http(f"http://127.0.0.1:{args.hub_port}/health", timeout_sec=12.0):
            raise SystemExit("LAN Hub did not start in time.")

        print("Running Django migrations...")
        subprocess.run(
            [sys.executable, "manage.py", "migrate"],
            cwd=str(workspace / "backend"),
            env=env,
            check=True,
        )

        print("Starting Django backend...")
        print(f"Client JSON: {json_out}")
        print(f"Hub URL:     {payload['hub_url']}")
        print(f"Backend URL: {payload['backend_url']}")
        subprocess.run(
            [sys.executable, "manage.py", "runserver", f"0.0.0.0:{args.backend_port}"],
            cwd=str(workspace / "backend"),
            env=env,
            check=True,
        )
    finally:
        if hub_proc.poll() is None:
            hub_proc.send_signal(signal.SIGTERM)
            try:
                hub_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                hub_proc.kill()


if __name__ == "__main__":
    main()
