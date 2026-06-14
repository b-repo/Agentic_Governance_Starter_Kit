# Agent Install Prompt (Copy/Paste)

Use this prompt inside any target project session:

Go to https://github.com/b-repo/Agentic_Governance_Starter_Kit and install it in this repository automatically.

Execution requirements:
1. Clone or download the repository.
2. Run `bash install.sh` in the current project (or `bash install.sh --target <current_project_path> --project-name <repo_name>` when needed).
3. Run governance audit and generate report.
4. Run GitHub sync dry-run.
5. Run apply when GitHub credentials are available or I approve credentialed sync.
6. Run governance health-check and confirm `governance_drift = 0`.
7. Put code and governance changes on a named branch and open a pull request; do not push directly to `main`, `master`, or `release/*`.
8. Return a final summary with installed files, audit status, sync status, health-check status, and next steps.

Policy required:
- Governance-first mode: `docs/ISSUE_LEDGER.json` is the source of truth, sync is mandatory when the ledger exists, and automatic execution is blocked only when gate is `blocked`.
- Branch policy: all updates go through pull requests from named branches.
