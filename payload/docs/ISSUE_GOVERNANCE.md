# Issue Governance & Agentic Delivery

This document defines how issue quality and execution governance works in this repository.

## Policy summary

- Issue sync to GitHub is always allowed.
- Automatic agentic execution is blocked only when gate is `blocked`.
- Open issues must include minimum semantic fields in `docs/ISSUE_LEDGER.json`.

## Required files

- `docs/ISSUE_LEDGER.json`
- `scripts/governance/sync_issue_ledger.py`
- `.github/workflows/issue-ledger-audit.yml`

## Open issue semantic minimum

Each open issue (`planned`, `in_progress`, `blocked`) must include:

- `problem_statement`
- `scope_in`
- `scope_out`
- `target_files`
- `implementation_steps`
- `test_plan`
- `success_metrics`
- `dependencies`

## Quality score

Quality score is calculated in range 0-100.

- Gate threshold default: 80
- Gate classes:
  - `ready`
  - `review`
  - `blocked`

## Recommended flow

1. Update `docs/ISSUE_LEDGER.json`
2. Run local audit:
   - `python scripts/governance/sync_issue_ledger.py --audit --report`
3. Sync with GitHub (dry-run/apply):
   - `python scripts/governance/sync_issue_ledger.py --repo owner/repo`
   - `python scripts/governance/sync_issue_ledger.py --repo owner/repo --apply`
