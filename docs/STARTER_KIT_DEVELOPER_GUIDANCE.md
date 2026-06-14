[Overview](../README.md) | [Official Docs Policy](OFFICIAL_DOCS_POLICY.md) | [Governance](GOVERNANCE.md)

# Starter Kit Developer Guidance

This guidance is for any developer agent maintaining or applying the Agentic Governance Starter Kit.

Starter kit repository:

```text
https://github.com/b-repo/Agentic_Governance_Starter_Kit
```

## Mandatory Change To Promote

The starter kit must promote the official-documentation-first policy to every project where it is installed or updated.

Every project bootstrapped by the starter kit should receive a policy equivalent to:

> For any external integration, API, SDK, CLI, cloud service, OAuth flow, webhook, or vendor endpoint, consult the current official documentation before implementation or debugging. Do not rely only on model memory, old examples, community snippets, or previously known endpoints. Record the official documentation URL and the specific endpoint/behavior used in project docs or issue notes.

## Required Starter Kit Updates

Update the starter kit so new and existing projects receive:

1. A bootstrap instruction requiring official documentation checks for all external integrations.
2. A reusable document equivalent to `docs/OFFICIAL_DOCS_POLICY.md`.
3. Issue template or ledger guidance requiring official documentation URLs for integration work.
4. Audit behavior that flags integration issues missing official documentation references.
5. Migration notes for existing projects so this policy can be applied without overwriting local project-specific docs.

## Propagation Behavior

When a developer agent is operating in any project that uses the starter kit, it must:

1. Check whether the project has the official-documentation-first policy.
2. If missing, add it using the starter kit's current template.
3. Preserve local project-specific examples and integration notes.
4. Record the change in the issue ledger, audit notes, or project documentation.
5. Report whether the project is compliant.

## Ledger-First Issue Behavior

When maintaining or applying the starter kit, governed project work must start in `docs/ISSUE_LEDGER.json`.

Developer agents must not open standalone GitHub Issues manually for governed work. They must:

1. Add or update a semantically complete ledger entry.
2. Run audit and sync dry-run.
3. Run apply sync when credentials are available.
4. Confirm health-check reports `governance_drift = 0`.
5. Only then implement, close, or report the governed work.

If a manual GitHub Issue already exists, adopt it by recording `github.number` and `github.url` in the ledger, then run sync apply so the title, body, labels, and `ledger-id` marker are corrected.

The starter kit sync script must keep this recovery path resilient by matching existing issues by `github.number` as well as by canonical title/body marker.

## Daily Starter Kit Update Check

When a developer agent is active in a project, it must check for starter kit updates at most once per UTC day.

The check should happen before installing, updating, syncing, or auditing starter kit governance assets.

Recommended behavior:

1. Determine the current UTC date.
2. Look for a local marker recording the last starter kit update check date, for example:

```text
.agents/starter-kit-last-check
```

3. If the marker is absent or older than the current UTC date, check the remote starter kit repository for updates.
4. If updates are available, report them and apply only the safe/documented starter kit update path.
5. Write the current UTC date to the marker after the check completes.
6. If network access is unavailable, record the attempted check and report that update verification is blocked by network access.

Suggested command pattern when network access is available:

```bash
git ls-remote https://github.com/b-repo/Agentic_Governance_Starter_Kit HEAD
```

This repository also provides a dependency-free helper:

```bash
python scripts/governance/check_starter_kit_updates.py
```

It returns JSON, skips repeated checks on the same UTC day, and writes the daily marker to:

```text
.agents/starter-kit-last-check
```

If a local clone of the starter kit exists, prefer:

```bash
git fetch origin
git status --short
git log --oneline HEAD..origin/main
```

Do not auto-apply remote changes blindly. The agent must summarize what changed and preserve project-specific governance files.

## Minimum Report

Every starter kit maintenance pass should report:

- whether the daily update check ran;
- remote revision or reason the check could not complete;
- whether the official-documentation-first policy exists in the target project;
- files added or updated;
- whether issue ledger/audit guidance was updated;
- any blocked propagation items.

## Rationale

This rule was introduced after the LinkedIn OAuth/OIDC integration initially used stale endpoint knowledge. The current official documentation showed that the correct OpenID Connect member information endpoint is:

```text
https://api.linkedin.com/v2/userinfo
```

Official reference:

```text
https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2
```

The starter kit must make this lesson reusable across all projects.
