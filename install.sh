#!/usr/bin/env bash
set -euo pipefail

TARGET=""
PROJECT_NAME=""
RUN_APPLY="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="$2"
      shift 2
      ;;
    --project-name)
      PROJECT_NAME="$2"
      shift 2
      ;;
    --apply)
      RUN_APPLY="true"
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOAD_DIR="$SCRIPT_DIR/payload"

if [[ -z "$TARGET" ]]; then
  TARGET="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

if [[ ! -d "$TARGET" ]]; then
  echo "Target directory not found: $TARGET"
  exit 1
fi

if [[ -z "$PROJECT_NAME" ]]; then
  PROJECT_NAME="$(basename "$TARGET")"
fi

echo "== Agentic Governance Installer =="
echo "Target: $TARGET"
echo "Project: $PROJECT_NAME"

mkdir -p "$TARGET/docs"
mkdir -p "$TARGET/scripts/governance"
mkdir -p "$TARGET/.github/workflows"

cp "$PAYLOAD_DIR/docs/ISSUE_GOVERNANCE.md" "$TARGET/docs/ISSUE_GOVERNANCE.md"
cp "$PAYLOAD_DIR/scripts/governance/sync_issue_ledger.py" "$TARGET/scripts/governance/sync_issue_ledger.py"
cp "$PAYLOAD_DIR/.github/workflows/issue-ledger-audit.yml" "$TARGET/.github/workflows/issue-ledger-audit.yml"
cp "$SCRIPT_DIR/AGENT_BOOTSTRAP_PROMPT.md" "$TARGET/AGENT_BOOTSTRAP_PROMPT.md"

LEDGER_TEMPLATE="$PAYLOAD_DIR/docs/ISSUE_LEDGER.json"
LEDGER_TARGET="$TARGET/docs/ISSUE_LEDGER.json"

python - "$LEDGER_TEMPLATE" "$LEDGER_TARGET" "$PROJECT_NAME" << 'PY'
import json
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
project_name = sys.argv[3]

obj = json.loads(src.read_text(encoding='utf-8'))
obj['meta']['project'] = project_name
obj['meta']['last_updated'] = '2026-06-09'
dst.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(f"Wrote {dst}")
PY

chmod +x "$TARGET/scripts/governance/sync_issue_ledger.py"

if [[ ! -f "$TARGET/.gitignore" ]]; then
  touch "$TARGET/.gitignore"
fi

if ! grep -q "ISSUE_LEDGER_AUDIT.md" "$TARGET/.gitignore"; then
  echo "docs/ISSUE_LEDGER_AUDIT.md" >> "$TARGET/.gitignore"
fi

pushd "$TARGET" >/dev/null

printf "\n-- Running audit --\n"
python scripts/governance/sync_issue_ledger.py --audit --report

if command -v gh >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
  REPO_SLUG=""
  if [[ "$ORIGIN_URL" =~ github.com[:/](.+)\.git$ ]]; then
    REPO_SLUG="${BASH_REMATCH[1]}"
  elif [[ "$ORIGIN_URL" =~ github.com[:/](.+)$ ]]; then
    REPO_SLUG="${BASH_REMATCH[1]}"
  fi

  if [[ -n "$REPO_SLUG" ]]; then
    printf "\n-- Running GitHub sync dry-run for %s --\n" "$REPO_SLUG"
    if ! python scripts/governance/sync_issue_ledger.py --repo "$REPO_SLUG"; then
      echo "Warning: dry-run sync failed (continuing installation)."
    fi

    if [[ "$RUN_APPLY" == "true" ]]; then
      printf "\n-- Applying GitHub sync for %s --\n" "$REPO_SLUG"
      if ! python scripts/governance/sync_issue_ledger.py --repo "$REPO_SLUG" --apply; then
        echo "Warning: apply sync failed (installation completed without GitHub apply)."
      fi
    fi
  else
    printf "\nSkipping GitHub sync: could not infer repo slug from origin\n"
  fi
else
  printf "\nSkipping GitHub sync: gh or git not available\n"
fi

popd >/dev/null

printf "\nInstallation complete.\n"
echo "Next steps:"
echo "1) Review docs/ISSUE_GOVERNANCE.md"
echo "2) Edit docs/ISSUE_LEDGER.json"
echo "3) Run: python scripts/governance/sync_issue_ledger.py --audit --report"
