# Agentic Governance Starter Kit

Portable package to install issue governance, quality scoring, and hybrid execution policy in any repository.

## What this kit installs

- `AGENT_BOOTSTRAP_PROMPT.md`
- `docs/ISSUE_GOVERNANCE.md`
- `docs/ISSUE_LEDGER.json`
- `scripts/governance/sync_issue_ledger.py`
- `.github/workflows/issue-ledger-audit.yml`

## Hybrid policy included

- GitHub issue sync is always allowed.
- Automatic agentic execution is blocked only when gate is `blocked`.

## Quick start

From inside this kit folder:

1. Run installer in current repo:
   - `bash install.sh`
2. Or target another path:
   - `bash install.sh --target /path/to/repo --project-name my-project`

The installer also copies `AGENT_BOOTSTRAP_PROMPT.md` into the target repository root so the next agent can use a single, reusable instruction.

## Optional apply sync

After installation, from target repo:

- Dry run:
  - `python scripts/governance/sync_issue_ledger.py --repo owner/repo`
- Apply:
  - `python scripts/governance/sync_issue_ledger.py --repo owner/repo --apply`

## Notes

- Requires Python 3.10+.
- For GitHub sync, requires `gh` authenticated.
