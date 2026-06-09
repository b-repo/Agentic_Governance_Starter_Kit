# Agent Install Prompt (Copy/Paste)

Use this prompt inside any target project session:

Go to https://github.com/b-repo/Agentic_Governance_Starter_Kit and install it in this repository automatically.

Execution requirements:
1. Clone or download the repository.
2. Run `bash install.sh` in the current project (or `bash install.sh --target <current_project_path> --project-name <repo_name>` when needed).
3. Run governance audit and generate report.
4. Run GitHub sync dry-run; if I approve, run apply.
5. Return a final summary with installed files, audit status, sync status, and next steps.

Policy required:
- Hybrid mode: sync always allowed, automatic execution blocked only when gate is `blocked`.
