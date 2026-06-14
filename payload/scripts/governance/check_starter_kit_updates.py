"""Daily starter kit update check helper.

This script is intentionally small and dependency-free so it can be copied into
projects that use the Agentic Governance Starter Kit.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_REPO_URL = "https://github.com/b-repo/Agentic_Governance_Starter_Kit"
DEFAULT_MARKER = Path(".agents/starter-kit-last-check")


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _read_marker(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _write_marker(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n", encoding="utf-8")


def check_starter_kit(repo_url: str, marker_path: Path, force: bool = False) -> dict:
    today = _today_utc()
    last_check = _read_marker(marker_path)

    if not force and last_check == today:
        return {
            "status": "skipped",
            "reason": "already_checked_today",
            "date": today,
            "marker": str(marker_path),
        }

    result = {
        "status": "unknown",
        "date": today,
        "repo_url": repo_url,
        "marker": str(marker_path),
        "remote_head": None,
    }

    try:
        completed = subprocess.run(
            ["git", "ls-remote", repo_url, "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        first_line = completed.stdout.strip().splitlines()[0] if completed.stdout.strip() else ""
        remote_head = first_line.split()[0] if first_line else ""
        result.update({
            "status": "ok",
            "remote_head": remote_head,
        })
    except Exception as exc:
        result.update({
            "status": "blocked",
            "reason": "starter_kit_update_check_failed",
            "error": str(exc),
        })

    try:
        _write_marker(marker_path, today)
    except OSError as exc:
        result["marker_warning"] = f"could_not_write_marker: {exc}"

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Check starter kit updates once per UTC day.")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--marker", default=str(DEFAULT_MARKER))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    result = check_starter_kit(args.repo_url, Path(args.marker), force=args.force)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
