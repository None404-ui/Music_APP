#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def _load_payload(raw: str) -> dict:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("JSON must be an object")
    return data


def _read_input(value: str | None) -> str:
    if value:
        p = Path(value)
        if p.exists():
            return p.read_text(encoding="utf-8")
        return value
    return sys.stdin.read()


def _check_json(url: str, timeout: float = 5.0) -> tuple[bool, str]:
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8").strip()
            return True, body[:240]
    except URLError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Принимает JSON от server-info, применяет env и запускает клиент."
    )
    parser.add_argument(
        "payload",
        nargs="?",
        help="JSON строка или путь к файлу с JSON. Если не задано, читается stdin.",
    )
    parser.add_argument("--check", action="store_true", help="Проверить доступность hub/backend")
    parser.add_argument(
        "--workspace",
        default=str(Path(__file__).resolve().parents[1]),
        help="Локальный путь к проекту на клиенте. По умолчанию берётся автоматически от расположения скрипта.",
    )
    parser.add_argument(
        "--print-env-only",
        action="store_true",
        help="Только распечатать env без запуска клиента",
    )
    parser.add_argument(
        "--emit-shell",
        action="store_true",
        help="Вывести только shell export-команды, чтобы можно было сделать eval.",
    )
    args = parser.parse_args()

    raw = _read_input(args.payload).strip()
    if not raw:
        raise SystemExit("Нет входных данных. Передайте JSON строкой, файлом или через stdin.")
    payload = _load_payload(raw)

    backend_url = str(payload.get("backend_url") or "").strip().rstrip("/")
    hub_url = str(payload.get("hub_url") or "").strip().rstrip("/")
    workspace = str(Path(args.workspace).resolve())

    if not backend_url or not hub_url:
        raise SystemExit("В JSON должны быть backend_url и hub_url.")

    env = os.environ.copy()
    env["CRATES_BACKEND_URL"] = backend_url
    env["CRATES_LAN_HUB_URL"] = hub_url

    if args.emit_shell:
        print(f'export CRATES_BACKEND_URL="{backend_url}"')
        print(f'export CRATES_LAN_HUB_URL="{hub_url}"')
        return

    print("=== CLIENT ENV ===")
    print(f'CRATES_BACKEND_URL="{backend_url}"')
    print(f'CRATES_LAN_HUB_URL="{hub_url}"')
    print(f'CLIENT_WORKSPACE="{workspace}"')
    print()

    if args.check:
        print("=== CONNECTIVITY CHECK ===")
        ok_hub, hub_msg = _check_json(f"{hub_url}/health")
        print(f"Hub:     {'OK' if ok_hub else 'FAIL'} {hub_msg}")
        ok_backend, backend_msg = _check_json(f"{backend_url}/api/music-items/")
        print(f"Backend: {'OK' if ok_backend else 'FAIL'} {backend_msg}")
        print()
        if not (ok_hub and ok_backend):
            raise SystemExit("Server connectivity check failed.")

    if args.print_env_only:
        print("=== EXPORT COMMANDS ===")
        print(f'export CRATES_BACKEND_URL="{backend_url}"')
        print(f'export CRATES_LAN_HUB_URL="{hub_url}"')
        print(f'# local workspace: {workspace}')
        return

    print("Starting client app...")
    subprocess.run(
        [sys.executable, "main.py"],
        cwd=workspace,
        env=env,
        check=True,
    )


if __name__ == "__main__":
    main()
