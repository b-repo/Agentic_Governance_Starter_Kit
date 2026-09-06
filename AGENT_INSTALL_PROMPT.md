# Agent Install Prompt (Copy/Paste)

Use this prompt inside any target project session:

Go to https://github.com/b-repo/Agentic_Governance_Starter_Kit and install it in this repository automatically.

Execution requirements:
1. Clone or download the repository.
2. Run `bash install.sh` in the current project (or `bash install.sh --target <current_project_path> --project-name <repo_name>` when needed).
3. Inventory any supplied scope files in `docs/SCOPE_INTAKE.md`.
4. Ask blocking scope questions before implementation.
5. Decompose the full known scope into detailed issues in `docs/ISSUE_LEDGER.json`.
6. Run governance audit and generate report.
7. Run GitHub sync dry-run.
8. Run apply when GitHub credentials are available or I approve credentialed sync.
9. Run governance health-check and confirm `governance_drift = 0`.
10. Put code and governance changes on a named branch and open a pull request; do not push directly to `main`, `master`, or `release/*`.
11. Return a final summary with installed files, mapped scope files, open questions, audit status, sync status, health-check status, and next steps.

Policy required:
- Governance-first mode: `docs/ISSUE_LEDGER.json` is the source of truth, sync is mandatory when the ledger exists, and automatic execution is blocked only when gate is `blocked`.
- Scope-first mode: no implementation starts until supplied scope files are inventoried, unclear topics are asked, and the known scope is represented as issues.
- Branch policy: all updates go through pull requests from named branches.
