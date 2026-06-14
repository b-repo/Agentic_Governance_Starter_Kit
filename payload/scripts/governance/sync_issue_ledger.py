#!/usr/bin/env python3
"""Governance-first issue ledger auditor, synchronizer, and health check."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
LEDGER_PATH = ROOT / "docs" / "ISSUE_LEDGER.json"
REPORT_PATH = ROOT / "docs" / "ISSUE_LEDGER_AUDIT.md"

OPEN_STATUSES = {"planned", "in_progress", "blocked"}
DONE_STATUS = "done"
STATUS_VALUES = {DONE_STATUS, *OPEN_STATUSES}

DEFAULT_REQUIRED_FOR_OPEN = [
    "problem_statement",
    "scope_in",
    "scope_out",
    "target_files",
    "implementation_steps",
    "test_plan",
    "success_metrics",
    "dependencies",
]

DEFAULT_WEIGHTS = {
    "problem_statement": 15,
    "scope_in": 15,
    "scope_out": 10,
    "target_files": 15,
    "implementation_steps": 15,
    "test_plan": 15,
    "success_metrics": 10,
    "dependencies": 5,
}

BASE_LABELS = {
    "ledger-managed",
    "phase:0",
    "phase:1",
    "phase:2",
    "phase:3",
    "type:architecture",
    "type:bug",
    "type:documentation",
    "type:feature",
    "type:governance",
    "type:risk",
    "type:technical-debt",
    "priority:high",
    "priority:medium",
    "priority:low",
    "status:planned",
    "status:in-progress",
    "status:blocked",
    "status:done",
    "gate:ready",
    "gate:review",
    "gate:blocked",
    "gate:done",
}

REQUIRED_FILES = [
    "docs/ISSUE_GOVERNANCE.md",
    "docs/ISSUE_LEDGER_AUDIT.md",
    "docs/ISSUE_LEDGER.json",
    "scripts/governance/sync_issue_ledger.py",
    ".github/workflows/issue-ledger-audit.yml",
    ".github/workflows/issue-ledger-sync.yml",
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/ISSUE_TEMPLATE/feature.yml",
    ".github/ISSUE_TEMPLATE/architecture-decision.yml",
    ".github/ISSUE_TEMPLATE/technical-debt.yml",
    ".github/ISSUE_TEMPLATE/governance-gap.yml",
    ".github/ISSUE_TEMPLATE/documentation.yml",
    ".github/labels.yml",
]

@dataclass
class IssueQuality:
    issue_id: str
    score: int
    gate: str
    missing: list[str]


@dataclass
class AuditResult:
    total: int
    done: int
    open_items: int
    errors: list[str]
    quality: list[IssueQuality]


@dataclass
class SyncAction:
    action: str
    issue_id: str
    detail: str


@dataclass
class HealthResult:
    ledger_issues_count: int
    github_linked_issues_count: int
    missing_github_issues: list[str]
    closed_mismatch: list[str]
    status_mismatch: list[str]
    label_mismatch: list[str]

    @property
    def governance_drift(self) -> int:
        return (
            len(self.missing_github_issues)
            + len(self.closed_mismatch)
            + len(self.status_mismatch)
            + len(self.label_mismatch)
        )


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def gh_json(cmd: list[str]) -> Any:
    res = run_cmd(cmd)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "gh command failed")
    return json.loads(res.stdout or "null")


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Ledger not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_ledger(path: Path, ledger: dict[str, Any]) -> None:
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_filled(field: str, value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        if field == "dependencies":
            return True
        return len(value) > 0
    return value is not None


def label_names_from_yaml(path: Path) -> set[str]:
    if not path.exists():
        return set()
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*-\s*name:\s*[\"']?([^\"']+?)[\"']?\s*$", line)
        if match:
            names.add(match.group(1).strip())
    return names


def issue_github(issue: dict[str, Any]) -> dict[str, Any]:
    github = issue.setdefault("github", {})
    if not isinstance(github, dict):
        issue["github"] = {}
    return issue["github"]


def issue_number(issue: dict[str, Any]) -> int | None:
    github = issue.get("github") if isinstance(issue.get("github"), dict) else {}
    number = github.get("number")
    if number is None:
        number = issue.get("github_number")
    try:
        return int(number) if number not in (None, "") else None
    except (TypeError, ValueError):
        return None


def issue_url(issue: dict[str, Any]) -> str:
    github = issue.get("github") if isinstance(issue.get("github"), dict) else {}
    return str(github.get("url") or issue.get("github_url") or "")


def score_issue(issue: dict[str, Any], weights: dict[str, int], gate_min: int) -> IssueQuality:
    issue_id = issue.get("id", "<missing-id>")
    max_score = max(sum(weights.values()), 1)
    got = 0
    missing: list[str] = []

    for field, weight in weights.items():
        if is_filled(field, issue.get(field)):
            got += weight
        else:
            missing.append(field)

    score = round((got / max_score) * 100)
    status = issue.get("status")

    if status == DONE_STATUS:
        gate = "n/a (done)"
    elif score >= gate_min:
        gate = "ready"
    elif score >= max(60, gate_min - 20):
        gate = "review"
    else:
        gate = "blocked"

    return IssueQuality(issue_id=issue_id, score=score, gate=gate, missing=missing)


def normalize_phase(value: Any) -> str:
    raw = str(value or "0").strip().lower()
    if raw.startswith("phase"):
        raw = raw.removeprefix("phase")
    return raw or "0"


def normalize_label_value(value: Any) -> str:
    raw = str(value or "unknown").strip().lower()
    raw = raw.replace("_", "-").replace(" ", "-")
    aliases = {
        "docs": "documentation",
        "doc": "documentation",
        "arch": "architecture",
        "architecture-decision": "architecture",
        "debt": "technical-debt",
        "ops": "governance",
        "enhancement": "feature",
        "in-progress": "in-progress",
        "inprogress": "in-progress",
    }
    return aliases.get(raw, raw)


def normalize_gate(gate: str) -> str:
    if gate == "n/a (done)":
        return "done"
    return normalize_label_value(gate)


def expected_labels(issue: dict[str, Any], quality: IssueQuality) -> list[str]:
    labels = [
        "ledger-managed",
        f"phase:{normalize_phase(issue.get('phase'))}",
        f"type:{normalize_label_value(issue.get('type'))}",
        f"priority:{normalize_label_value(issue.get('priority'))}",
        f"status:{normalize_label_value(issue.get('status'))}",
        f"gate:{normalize_gate(quality.gate)}",
    ]
    return sorted(set(labels))


def validate_required_files(errors: list[str]) -> None:
    if not LEDGER_PATH.exists():
        return

    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            errors.append(f"governance setup: missing required file '{rel}'")

    audit_workflow = ROOT / ".github" / "workflows" / "issue-ledger-audit.yml"
    if audit_workflow.exists():
        text = audit_workflow.read_text(encoding="utf-8")
        if "--audit --report" not in text:
            errors.append("governance setup: audit workflow must run '--audit --report'")
        if "pull_request:" not in text:
            errors.append("governance setup: audit workflow must run on pull_request")

    sync_workflow = ROOT / ".github" / "workflows" / "issue-ledger-sync.yml"
    if sync_workflow.exists():
        text = sync_workflow.read_text(encoding="utf-8")
        if "--apply" not in text:
            errors.append("governance setup: sync workflow must run apply synchronization")
        if "--health-check" not in text:
            errors.append("governance setup: sync workflow must run health-check")
        if "GITHUB_TOKEN" not in text:
            errors.append("governance setup: sync workflow must configure GitHub token access")
        if "main" not in text or "master" not in text or "release/**" not in text:
            errors.append("governance setup: sync workflow must run on main, master, and release/*")
        if "Reject direct pushes to protected branches" not in text:
            errors.append("governance setup: sync workflow must reject direct pushes to protected branches")
        if "pull-requests: read" not in text:
            errors.append("governance setup: sync workflow must be able to inspect associated pull requests")


def audit_ledger(ledger: dict[str, Any]) -> AuditResult:
    issues = ledger.get("issues", [])
    meta = ledger.get("meta", {})
    required = meta.get("semantic_required_fields_for_open") or DEFAULT_REQUIRED_FOR_OPEN
    weights = meta.get("quality_score_weights") or DEFAULT_WEIGHTS
    gate_min = int(meta.get("quality_gate_min_score_for_agentic") or 80)

    errors: list[str] = []
    quality_rows: list[IssueQuality] = []

    validate_required_files(errors)

    if not isinstance(issues, list):
        errors.append("ledger: 'issues' must be a list")
        issues = []

    seen_ids: set[str] = set()
    local_labels = label_names_from_yaml(ROOT / ".github" / "labels.yml")

    for issue in issues:
        issue_id = issue.get("id", "<missing-id>")
        if issue_id in seen_ids:
            errors.append(f"{issue_id}: duplicate issue id")
        seen_ids.add(issue_id)

        for key in ["id", "title", "phase", "status", "priority", "type", "github", "evidence", "acceptance_criteria"]:
            if key not in issue:
                errors.append(f"{issue_id}: missing required key '{key}'")

        status = issue.get("status")
        if status not in STATUS_VALUES:
            errors.append(f"{issue_id}: invalid status '{status}'")

        if status in OPEN_STATUSES:
            for field in required:
                if field not in issue:
                    errors.append(f"{issue_id}: missing semantic field '{field}'")
                elif not is_filled(field, issue.get(field)):
                    errors.append(f"{issue_id}: semantic field '{field}' empty")

        if status == DONE_STATUS:
            for p in issue.get("evidence", []):
                if not (ROOT / p).exists():
                    errors.append(f"{issue_id}: missing evidence file '{p}'")

        q = score_issue(issue, weights, gate_min)
        quality_rows.append(q)

        if local_labels:
            for label in expected_labels(issue, q):
                if label not in local_labels:
                    errors.append(f"{issue_id}: ledger label '{label}' is missing from .github/labels.yml")

    missing_base_labels = sorted(BASE_LABELS - local_labels) if local_labels else sorted(BASE_LABELS)
    if (ROOT / ".github" / "labels.yml").exists() and missing_base_labels:
        errors.append(f"governance setup: .github/labels.yml missing required labels: {', '.join(missing_base_labels)}")

    done = sum(1 for i in issues if i.get("status") == DONE_STATUS)
    open_items = sum(1 for i in issues if i.get("status") in OPEN_STATUSES)

    return AuditResult(total=len(issues), done=done, open_items=open_items, errors=errors, quality=quality_rows)


def write_report(ledger: dict[str, Any], audit: AuditResult) -> None:
    issues = ledger.get("issues", [])
    meta = ledger.get("meta", {})
    gate_min = int(meta.get("quality_gate_min_score_for_agentic") or 80)
    weights = meta.get("quality_score_weights") or DEFAULT_WEIGHTS

    open_quality = [
        q
        for q in audit.quality
        if next((i for i in issues if i.get("id") == q.issue_id and i.get("status") in OPEN_STATUSES), None)
    ]
    avg_open = round(sum(q.score for q in open_quality) / len(open_quality), 1) if open_quality else 0.0

    lines = [
        "[README](../README.md) | [Issue Governance](ISSUE_GOVERNANCE.md) | [Issue Ledger](ISSUE_LEDGER.json) | [Audit Report](ISSUE_LEDGER_AUDIT.md)",
        "",
        "# ISSUE LEDGER Audit Report",
        "",
        "## Summary",
        "",
        f"- Total issues: **{audit.total}**",
        f"- Done: **{audit.done}**",
        f"- Open: **{audit.open_items}**",
        f"- Audit status: **{'fail' if audit.errors else 'pass'}**",
        "",
        "## Quality Score",
        "",
        f"- Agentic gate minimum: **{gate_min}**",
        f"- Average open issue score: **{avg_open}**",
        "",
    ]

    if open_quality:
        lines.extend(["| Issue | Score | Gate | Missing |", "|---|---:|---|---|"])
        for row in sorted(open_quality, key=lambda x: x.score, reverse=True):
            miss = ", ".join(row.missing) if row.missing else "-"
            lines.append(f"| `{row.issue_id}` | {row.score} | {row.gate} | {miss} |")
        lines.append("")

    lines.extend(["## Findings", ""])
    if audit.errors:
        for err in audit.errors:
            lines.append(f"- FAIL: {err}")
    else:
        lines.append("- PASS: No validation issues found")

    lines.extend(["", "## Quality Model", ""])
    for k, v in weights.items():
        lines.append(f"- `{k}`: {v}")

    lines.extend(
        [
            "",
            "[README](../README.md) | [Issue Governance](ISSUE_GOVERNANCE.md) | [Issue Ledger](ISSUE_LEDGER.json) | [Audit Report](ISSUE_LEDGER_AUDIT.md)",
            "",
        ]
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def infer_repo_from_origin() -> str:
    res = run_cmd(["git", "remote", "get-url", "origin"])
    if res.returncode != 0:
        return ""
    raw = res.stdout.strip()
    if "github.com" not in raw:
        return ""
    if raw.endswith(".git"):
        raw = raw[:-4]
    if ":" in raw and raw.startswith("git@"):
        return raw.split(":", 1)[1]
    return raw.split("github.com/", 1)[1] if "github.com/" in raw else ""


def require_repo(repo: str) -> str:
    repo = repo or infer_repo_from_origin()
    if not repo:
        raise RuntimeError("Could not infer repo slug. Use --repo owner/repo")
    if "/" not in repo:
        raise RuntimeError("Repository must use owner/repo format")
    return repo


def has_github_auth() -> bool:
    if shutil.which("gh") is None:
        return False
    if os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        return True
    return run_cmd(["gh", "auth", "status"]).returncode == 0


def validate_github_auth() -> None:
    if not has_github_auth():
        raise RuntimeError(
            "GitHub authentication is not configured.\n"
            "Cannot synchronize ISSUE_LEDGER.json with GitHub Issues."
        )


def ensure_labels(repo: str, labels: list[str], apply: bool, offline: bool = False) -> list[SyncAction]:
    actions: list[SyncAction] = []
    existing = [] if offline else gh_json(["gh", "label", "list", "--repo", repo, "--limit", "500", "--json", "name"])
    existing_names = {x.get("name") for x in existing}

    for label in sorted(set(labels) | BASE_LABELS):
        if label in existing_names:
            continue
        actions.append(SyncAction("label:create", label, f"Create missing label '{label}'"))
        if apply:
            res = run_cmd(
                [
                    "gh",
                    "label",
                    "create",
                    label,
                    "--repo",
                    repo,
                    "--color",
                    "1D76DB",
                    "--description",
                    "Managed by issue governance sync",
                ]
            )
            if res.returncode != 0 and "already exists" not in (res.stderr or "").lower():
                raise RuntimeError(res.stderr.strip() or f"Failed creating label {label}")
    return actions


def build_body(issue: dict[str, Any], q: IssueQuality, gate_min: int) -> str:
    def bl(lst: list[Any], code: bool = False) -> str:
        if not lst:
            return "- n/a"
        if code:
            return "\n".join(f"- `{x}`" for x in lst)
        return "\n".join(f"- {x}" for x in lst)

    if q.gate == "ready":
        policy = f"- Current gate: **ready** (score={q.score}, threshold={gate_min})\n- Automatic agentic execution: **allowed**"
    elif q.gate == "review":
        policy = f"- Current gate: **review** (score={q.score}, threshold={gate_min})\n- Automatic agentic execution: **allowed with review recommended**"
    elif q.gate == "blocked":
        policy = f"- Current gate: **blocked** (score={q.score}, threshold={gate_min})\n- Automatic agentic execution: **not allowed**"
    else:
        policy = "- Current gate: **n/a (done)**\n- Automatic agentic execution: n/a"

    return (
        f"## Context\n"
        f"- Ledger ID: `{issue['id']}`\n"
        f"- Phase: `{issue.get('phase', 'n/a')}`\n"
        f"- Type: `{issue.get('type', 'n/a')}`\n"
        f"- Priority: `{issue.get('priority', 'n/a')}`\n"
        f"- Status: `{issue.get('status', 'n/a')}`\n\n"
        f"## Problem Statement\n{issue.get('problem_statement', 'n/a')}\n\n"
        f"## Scope In\n{bl(issue.get('scope_in', []))}\n\n"
        f"## Scope Out\n{bl(issue.get('scope_out', []))}\n\n"
        f"## Target Files\n{bl(issue.get('target_files', []), code=True)}\n\n"
        f"## Dependencies\n{bl(issue.get('dependencies', []), code=True) if issue.get('dependencies') else '- none'}\n\n"
        f"## Implementation Steps\n{bl(issue.get('implementation_steps', []))}\n\n"
        f"## Test Plan\n{bl(issue.get('test_plan', []))}\n\n"
        f"## Success Metrics\n{bl(issue.get('success_metrics', []))}\n\n"
        f"## Risks\n{bl(issue.get('risks', []))}\n\n"
        f"## Execution Policy\n{policy}\n\n"
        f"## Acceptance Criteria\n{bl(issue.get('acceptance_criteria', []))}\n\n"
        f"## Evidence\n{bl(issue.get('evidence', []), code=True)}\n\n"
        f"## Governance\n"
        f"- Source ledger: `docs/ISSUE_LEDGER.json`\n"
        f"- Process: `docs/ISSUE_GOVERNANCE.md`\n"
        f"<!-- ledger-id: {issue['id']} -->\n"
    )


def fetch_existing_issues(repo: str) -> list[dict[str, Any]]:
    return gh_json(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--limit",
            "1000",
            "--json",
            "number,title,state,labels,url,body",
        ]
    )


def index_issues(existing: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in existing:
        title = item.get("title", "")
        if title.startswith("[") and "]" in title:
            by_id[title[1 : title.index("]")]] = item
            continue
        body = item.get("body") or ""
        match = re.search(r"ledger-id:\s*([A-Za-z0-9_.-]+)", body)
        if match:
            by_id[match.group(1)] = item
    return by_id


def sync_github(ledger_path: Path, ledger: dict[str, Any], apply: bool, repo: str) -> list[SyncAction]:
    repo = require_repo(repo)
    if apply:
        validate_github_auth()
    offline = not apply and not has_github_auth()
    if offline:
        print("GitHub authentication is not configured. Running dry-run from the ledger only.")

    meta = ledger.get("meta", {})
    gate_min = int(meta.get("quality_gate_min_score_for_agentic") or 80)
    weights = meta.get("quality_score_weights") or DEFAULT_WEIGHTS
    issues = ledger.get("issues", [])
    quality_map = {i["id"]: score_issue(i, weights, gate_min) for i in issues}
    wanted_labels = [label for issue in issues for label in expected_labels(issue, quality_map[issue["id"]])]

    actions = ensure_labels(repo, wanted_labels, apply=apply, offline=offline)
    existing = [] if offline else fetch_existing_issues(repo)
    by_id = index_issues(existing)
    ledger_changed = False

    for issue in issues:
        issue_id = issue["id"]
        q = quality_map[issue_id]
        labels = expected_labels(issue, q)
        title = f"[{issue_id}] {issue['title']}"
        body = build_body(issue, q, gate_min)
        found = by_id.get(issue_id)

        if not found:
            actions.append(SyncAction("issue:create", issue_id, title))
            if apply:
                res = run_cmd(["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body, "--label", ",".join(labels)])
                if res.returncode != 0:
                    raise RuntimeError(res.stderr.strip() or f"Create failed: {issue_id}")
                url = res.stdout.strip().splitlines()[-1]
                number = int(url.rstrip("/").split("/")[-1])
                github = issue_github(issue)
                github["number"] = number
                github["url"] = url
                issue["github_number"] = number
                issue["github_url"] = url
                ledger_changed = True
            continue

        number = str(found["number"])
        existing_labels = {x.get("name") for x in found.get("labels", []) if isinstance(x, dict)}
        desired_labels = set(labels)
        github = issue_github(issue)
        if github.get("number") != found.get("number") or github.get("url") != found.get("url"):
            github["number"] = found.get("number")
            github["url"] = found.get("url")
            issue["github_number"] = found.get("number")
            issue["github_url"] = found.get("url")
            ledger_changed = True

        if found.get("title") != title or (found.get("body") or "") != body or not desired_labels.issubset(existing_labels):
            actions.append(SyncAction("issue:update", issue_id, f"Update #{number} {title}"))
            if apply:
                remove_labels = sorted(
                    label
                    for label in existing_labels
                    if label.startswith(("phase:", "type:", "priority:", "status:", "gate:", "agentic:"))
                    and label not in desired_labels
                )
                for label in remove_labels:
                    res = run_cmd(["gh", "issue", "edit", number, "--repo", repo, "--remove-label", label])
                    if res.returncode != 0:
                        raise RuntimeError(res.stderr.strip() or f"Remove label failed: {issue_id}")
                res = run_cmd(["gh", "issue", "edit", number, "--repo", repo, "--title", title, "--body", body, "--add-label", ",".join(labels)])
                if res.returncode != 0:
                    raise RuntimeError(res.stderr.strip() or f"Update failed: {issue_id}")

        desired_closed = issue.get("status") == DONE_STATUS
        currently_closed = found.get("state", "").upper() == "CLOSED"
        if desired_closed and not currently_closed:
            actions.append(SyncAction("issue:close", issue_id, f"Close #{number}"))
            if apply:
                res = run_cmd(["gh", "issue", "close", number, "--repo", repo, "--comment", "Closing via issue governance sync (status=done)."])
                if res.returncode != 0:
                    raise RuntimeError(res.stderr.strip() or f"Close failed: {issue_id}")
        elif not desired_closed and currently_closed:
            actions.append(SyncAction("issue:reopen", issue_id, f"Reopen #{number}"))
            if apply:
                res = run_cmd(["gh", "issue", "reopen", number, "--repo", repo, "--comment", "Reopening via issue governance sync (status!=done)."])
                if res.returncode != 0:
                    raise RuntimeError(res.stderr.strip() or f"Reopen failed: {issue_id}")

    if apply and ledger_changed:
        save_ledger(ledger_path, ledger)

    return actions


def health_check(ledger: dict[str, Any], repo: str) -> HealthResult:
    repo = require_repo(repo)
    validate_github_auth()

    meta = ledger.get("meta", {})
    gate_min = int(meta.get("quality_gate_min_score_for_agentic") or 80)
    weights = meta.get("quality_score_weights") or DEFAULT_WEIGHTS
    issues = ledger.get("issues", [])
    existing = fetch_existing_issues(repo)
    by_id = index_issues(existing)

    missing: list[str] = []
    closed_mismatch: list[str] = []
    status_mismatch: list[str] = []
    label_mismatch: list[str] = []
    linked_count = 0

    for issue in issues:
        issue_id = issue["id"]
        found = by_id.get(issue_id)
        number = issue_number(issue)
        if number and not found:
            found = next((x for x in existing if int(x.get("number", 0)) == number), None)
        if not found:
            missing.append(issue_id)
            continue

        linked_count += 1
        desired_closed = issue.get("status") == DONE_STATUS
        currently_closed = found.get("state", "").upper() == "CLOSED"
        if desired_closed != currently_closed:
            closed_mismatch.append(issue_id)

        existing_labels = {x.get("name") for x in found.get("labels", []) if isinstance(x, dict)}
        desired_status = f"status:{normalize_label_value(issue.get('status'))}"
        if desired_status not in existing_labels:
            status_mismatch.append(issue_id)

        q = score_issue(issue, weights, gate_min)
        desired_labels = set(expected_labels(issue, q))
        missing_labels = sorted(desired_labels - existing_labels)
        if missing_labels:
            label_mismatch.append(f"{issue_id}: {', '.join(missing_labels)}")

    return HealthResult(
        ledger_issues_count=len(issues),
        github_linked_issues_count=linked_count,
        missing_github_issues=missing,
        closed_mismatch=closed_mismatch,
        status_mismatch=status_mismatch,
        label_mismatch=label_mismatch,
    )


def print_actions(actions: list[SyncAction]) -> None:
    if not actions:
        print("No synchronization actions required")
        return
    for action in actions:
        print(f"[{action.action}] {action.issue_id}: {action.detail}")


def print_health(result: HealthResult) -> None:
    payload = {
        "ledger_issues_count": result.ledger_issues_count,
        "github_linked_issues_count": result.github_linked_issues_count,
        "missing_github_issues": result.missing_github_issues,
        "closed_mismatch": result.closed_mismatch,
        "status_mismatch": result.status_mismatch,
        "label_mismatch": result.label_mismatch,
        "governance_drift": result.governance_drift,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Issue governance audit, GitHub sync, and health check")
    parser.add_argument("--ledger", default=str(LEDGER_PATH))
    parser.add_argument("--audit", action="store_true", help="Validate the ledger and required governance files")
    parser.add_argument("--report", action="store_true", help="Write docs/ISSUE_LEDGER_AUDIT.md")
    parser.add_argument("--repo", default="", help="GitHub repository in owner/repo format")
    parser.add_argument("--apply", action="store_true", help="Apply idempotent synchronization to GitHub Issues")
    parser.add_argument("--dry-run", action="store_true", help="Preview GitHub synchronization without writes")
    parser.add_argument("--health-check", action="store_true", help="Compare ISSUE_LEDGER.json with GitHub Issues")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ledger_path = Path(args.ledger)
    ledger = load_ledger(ledger_path)
    audit = audit_ledger(ledger)

    if args.report:
        write_report(ledger, audit)
        print(f"Audit report written to {REPORT_PATH}")

    if args.audit:
        if audit.errors:
            print("Ledger audit failed:")
            for error in audit.errors:
                print(f"- {error}")
            return 1
        print("Ledger audit passed")

    if args.apply and args.dry_run:
        print("Choose either --apply or --dry-run, not both")
        return 1

    if args.apply or args.dry_run or (args.repo and not args.health_check):
        if audit.errors:
            print("Cannot synchronize because ledger audit failed")
            for error in audit.errors:
                print(f"- {error}")
            return 1
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"Running GitHub synchronization in {mode} mode")
        actions = sync_github(ledger_path, ledger, apply=args.apply, repo=args.repo)
        print_actions(actions)

    if args.health_check:
        result = health_check(ledger, args.repo)
        print_health(result)
        if result.governance_drift > 0:
            return 1

    if not any([args.audit, args.report, args.repo, args.apply, args.dry_run, args.health_check]):
        write_report(ledger, audit)
        if audit.errors:
            print("Ledger audit failed. See report for details.")
            return 1
        print("Ledger audit passed. Report updated.")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
