# Agentic Governance Starter Kit

[README](README.md) | [Issue Governance](payload/docs/ISSUE_GOVERNANCE.md) | [Issue Ledger](payload/docs/ISSUE_LEDGER.json) | [Audit Report](payload/docs/ISSUE_LEDGER_AUDIT.md)

Portable package to install Governance-First Development in any repository.

## Contents

- [What This Kit Installs](#what-this-kit-installs)
- [Governance-First Development](#governance-first-development)
- [Quick Start](#quick-start)
- [Required Commands](#required-commands)
- [GitHub Requirements](#github-requirements)
- [Completion Gate](#completion-gate)

## What This Kit Installs

- `AGENT_BOOTSTRAP_PROMPT.md`
- `docs/ISSUE_GOVERNANCE.md`
- `docs/ISSUE_LEDGER_AUDIT.md`
- `docs/ISSUE_LEDGER.json`
- `docs/OFFICIAL_DOCS_POLICY.md`
- `docs/STARTER_KIT_DEVELOPER_GUIDANCE.md`
- `scripts/governance/sync_issue_ledger.py`
- `scripts/governance/check_starter_kit_updates.py`
- `.github/workflows/issue-ledger-audit.yml`
- `.github/workflows/issue-ledger-sync.yml`
- `.github/ISSUE_TEMPLATE/`
- `.github/labels.yml`

## Governance-First Development

`docs/ISSUE_LEDGER.json` is the source of truth for governed work. It is not passive documentation. When a project contains the ledger, the repository must also contain the audit workflow, sync workflow, labels, issue templates, governance documentation, and sync script.

Work must enter the ledger before implementation. Do not open standalone GitHub Issues manually for governed project work. GitHub Issues are created or adopted by synchronization from `docs/ISSUE_LEDGER.json`.

Pull requests run audit only. Local validation and installation can run dry-run synchronization. Direct pushes to `main`, `master`, or `release/*` are not allowed. PR merges to protected branches run apply synchronization and then a health check that compares the ledger with GitHub Issues.

## Official Documentation First

Every external integration, API, SDK, CLI, cloud service, OAuth flow, webhook, or vendor endpoint must be checked against the current official documentation before implementation or debugging. Agents must not rely only on model memory, old examples, community snippets, or previously known endpoints.

Installed projects receive `docs/OFFICIAL_DOCS_POLICY.md`, and integration issues should record the official documentation URL plus the endpoint, SDK method, scope, parameter, or behavior used.

## Daily Starter Kit Update Check

When a developer agent is active in a project, it must check for starter kit updates at most once per UTC day. The installed helper records checks in `.agents/starter-kit-last-check`:

```bash
python scripts/governance/check_starter_kit_updates.py
```

The installer also runs this helper before audit so projects get a visible update-check status during governance maintenance.

## Quick Start

From inside this kit folder:

1. Run installer in the current repository:
   - `bash install.sh`
2. Or target another path:
   - `bash install.sh --target /path/to/repo --project-name my-project`

The installer copies the governance payload and `AGENT_BOOTSTRAP_PROMPT.md` into the target repository.

## Required Commands

- Audit and report:
  - `python scripts/governance/sync_issue_ledger.py --audit --report`
- Check starter kit updates:
  - `python scripts/governance/check_starter_kit_updates.py`
- Dry-run GitHub sync:
  - `python scripts/governance/sync_issue_ledger.py --repo owner/repo --dry-run`
- Apply GitHub sync:
  - `python scripts/governance/sync_issue_ledger.py --repo owner/repo --apply`
- Health check:
  - `python scripts/governance/sync_issue_ledger.py --repo owner/repo --health-check`

## GitHub Requirements

GitHub synchronization requires authenticated `gh`, `GH_TOKEN`, or `GITHUB_TOKEN`. The sync workflow uses `secrets.GITHUB_TOKEN` with `issues: write` and `contents: write` permissions.

Repositories should enforce branch protection or rulesets that require pull requests before merging and block direct pushes to `main`, `master`, and `release/*`.

If authentication is missing, apply and health-check fail clearly:

```text
GitHub authentication is not configured.
Cannot synchronize ISSUE_LEDGER.json with GitHub Issues.
```

## Completion Gate

A generated project is incomplete when `docs/ISSUE_LEDGER.json` exists and any governance automation is missing. Final validation must fail for missing audit workflow, missing sync workflow, missing labels, missing issue templates, missing GitHub token configuration, missing dry-run validation, missing apply validation, or governance drift.

The expected complete state is:

- Audit passes.
- Dry-run passes.
- Apply passes when credentials are available.
- Health check reports `governance_drift = 0`.
- Open GitHub Issues are either ledger-managed or intentionally backfilled/closed.
- Documentation is updated.
- Tests pass.

[README](README.md) | [Issue Governance](payload/docs/ISSUE_GOVERNANCE.md) | [Issue Ledger](payload/docs/ISSUE_LEDGER.json) | [Audit Report](payload/docs/ISSUE_LEDGER_AUDIT.md)
