"""First-run Setup Wizard (spec §3, §33, §48).

Interactively (or in ``--check`` mode) reports the status of every connector,
writes/updates a local ``.env`` from user input, and NEVER echoes stored
secrets back. It only ever writes to the local ``.env`` — production secrets
belong in GitHub Secrets, never in Git.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from app.config import REPO_ROOT, get_settings, reload_settings

ENV_PATH = REPO_ROOT / ".env"


@dataclass
class Connector:
    name: str
    env_keys: list[str]
    required: bool
    purpose: str
    help_url: str


CONNECTORS = [
    Connector("YouTube", ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"], False,
              "Upload, thumbnail, captions, metadata", "https://console.cloud.google.com/"),
    Connector("GitHub", ["GITHUB_TOKEN", "GITHUB_REPOSITORY"], False,
              "CI, scheduler, automated failure Issues", "https://github.com/settings/tokens"),
    Connector("Agnes", ["AGNES_API_KEY"], False, "AI text/image-to-video (optional)", "https://agnes.ai/"),
    Connector("OpenRouter", ["OPENROUTER_API_KEY"], False, "Free LLMs for script/QC/metadata", "https://openrouter.ai/keys"),
    Connector("Pexels", ["PEXELS_API_KEY"], False, "Free stock video/photos", "https://www.pexels.com/api/"),
    Connector("Pixabay", ["PIXABAY_API_KEY"], False, "Free stock video/photos", "https://pixabay.com/api/docs/"),
    Connector("CourtListener", ["COURTLISTENER_API_TOKEN"], False, "Legal verification (works anon)", "https://www.courtlistener.com/help/api/rest/"),
    Connector("Google Drive", ["GOOGLE_DRIVE_FOLDER_ID"], False, "Optional archive", "https://console.cloud.google.com/"),
]


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def _write_env(env: dict[str, str]) -> None:
    lines = ["# Written by the Setup Wizard. Do NOT commit this file.", ""]
    for k in sorted(env):
        lines.append(f"{k}={env[k]}")
    ENV_PATH.write_text("\n".join(lines) + "\n")


def _mask(value: str) -> str:
    if not value:
        return "(unset)"
    if len(value) <= 6:
        return "***"
    return value[:3] + "…" + value[-2:]


def status_table() -> list[tuple[str, str, str]]:
    env = _load_env()
    rows = []
    for c in CONNECTORS:
        present = all(env.get(k) for k in c.env_keys)
        state = "CONNECTED" if present else ("OPTIONAL" if not c.required else "MISSING")
        rows.append((c.name, state, c.purpose))
    return rows


def print_status() -> None:
    rows = status_table()
    width = max(len(r[0]) for r in rows)
    print("Connector status (secrets never shown):\n")
    for name, state, purpose in rows:
        print(f"  {name.ljust(width)}   {state:9}  {purpose}")
    print(
        "\nStore real secrets in GitHub Secrets for production. This wizard only writes a local .env "
        "for development. See SETUP.md for the exact click-by-click steps per service."
    )


def configure(interactive: bool = True) -> int:
    env = _load_env()
    if not interactive:
        print_status()
        return 0
    print("Setup Wizard — press Enter to keep the current value. Secrets are masked.\n")
    for c in CONNECTORS:
        print(f"\n== {c.name} ==  ({c.purpose})\n   Docs: {c.help_url}")
        for key in c.env_keys:
            current = env.get(key, "")
            try:
                entered = input(f"   {key} [{_mask(current)}]: ").strip()
            except EOFError:
                entered = ""
            if entered:
                env[key] = entered
    _write_env(env)
    reload_settings()
    print("\nSaved to .env (local only). Re-run with --check to see connector status.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="First-run setup wizard.")
    parser.add_argument("--check", action="store_true", help="Print connector status and exit.")
    args = parser.parse_args(argv)
    get_settings()
    if args.check:
        print_status()
        return 0
    return configure(interactive=sys.stdin.isatty())


if __name__ == "__main__":
    sys.exit(main())
