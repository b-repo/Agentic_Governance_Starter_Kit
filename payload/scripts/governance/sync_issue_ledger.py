#!/usr/bin/env python3
"""Portable issue governance auditor + GitHub sync.

Hybrid mode:
- Sync is always allowed.
- Automatic execution should be blocked only when gate=blocked.
"""

from __future__ import annotations

import argparse
import json
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

AGENTIC_LABELS = {
    "ready": "agentic:ready",
    "review": "agentic:review",
    "blocked": "agentic:blocked",
    "n/a (done)": "agentic:n/a",
}


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


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def gh_json(cmd: list[str]) -> Any:
    res = run_cmd(cmd)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "gh command failed")
    return json.loads(res.stdout)


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Ledger not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def is_filled(field: str, value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        if field == "dependencies":
            return True
        return len(value) > 0
    return value is not None


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


def audit_ledger(ledger: dict[str, Any]) -> AuditResult:
    issues = ledger.get("issues", [])
    meta = ledger.get("meta", {})
    required = meta.get("semantic_required_fields_for_open") or DEFAULT_REQUIRED_FOR_OPEN
    weights = meta.get("quality_score_weights") or DEFAULT_WEIGHTS
    gate_min = int(meta.get("quality_gate_min_score_for_agentic") or 80)

    errors: list[str] = []
    quality_rows: list[IssueQuality] = []

    for issue in issues:
        issue_id = issue.get("id", "<missing-id>")
        for key in ["id", "title", "phase", "status", "evidence", "acceptance_criteria"]:
            if key not in issue:
                errors.append(f"{issue_id}: missing required key '{key}'")

        status = issue.get("status")
        if status not in {DONE_STATUS, *OPEN_STATUSES}:
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

        quality_rows.append(score_issue(issue, weights, gate_min))

    done = sum(1 for i in issues if i.get("status") == DONE_STATUS)
    open_items = sum(1 for i in issues if i.get("status") in OPEN_STATUSES)

    return AuditResult(total=len(issues), done=done, open_items=open_items, errors=errors, quality=quality_rows)


def write_report(ledger: dict[str, Any], audit: AuditResult) -> None:
    issues = ledger.get("issues", [])
    meta = ledger.get("meta", {})
    gate_min = int(meta.get("quality_gate_min_score_for_agentic") or 80)
    weights = meta.get("quality_score_weights") or DEFAULT_WEIGHTS

    open_quality = [q for q in audit.quality if next((i for i in issues if i.get("id") == q.issue_id and i.get("status") in OPEN_STATUSES), None)]
    avg_open = round(sum(q.score for q in open_quality) / len(open_quality), 1) if open_quality else 0.0

    lines: list[str] = []
    lines.append("# ISSUE LEDGER Audit Report")
    lines.append("")
    lines.append(f"- Total issues: **{audit.total}**")
    lines.append(f"- Done: **{audit.done}**")
    lines.append(f"- Open: **{audit.open_items}**")
    lines.append("")
    lines.append("## Quality Score (0–100)")
    lines.append("")
    lines.append(f"- Agentic gate mínimo: **{gate_min}**")
    lines.append(f"- Média de score (issues abertas): **{avg_open}**")
    lines.append("")

    if open_quality:
        lines.append("| Issue | Score | Gate | Missing |")
        lines.append("|---|---:|---|---|")
        for row in sorted(open_quality, key=lambda x: x.score, reverse=True):
            miss = ", ".join(row.missing) if row.missing else "-"
            lines.append(f"| `{row.issue_id}` | {row.score} | {row.gate} | {miss} |")
        lines.append("")

    lines.append("## Findings")
    lines.append("")
    if audit.errors:
        for err in audit.errors:
            lines.append(f"- ❌ {err}")
    else:
        lines.append("- ✅ No validation issues found")

    lines.append("")
    lines.append("## Quality model")
    lines.append("")
    for k, v in weights.items():
        lines.append(f"- `{k}`: {v}")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def ensure_labels(repo: str, labels: list[str], apply: bool) -> None:
    existing = gh_json(["gh", "label", "list", "--repo", repo, "--limit", "500", "--json", "name"])
    existing_names = {x.get("name") for x in existing}
    for label in labels:
        if label in existing_names:
            continue
        print(f"[LABEL] missing '{label}'")
        if not apply:
            continue
        res = run_cmd(["gh", "label", "create", label, "--repo", repo, "--color", "1D76DB", "--description", "Managed by issue governance sync"])
        if res.returncode != 0 and "already exists" not in (res.stderr or "").lower():
            raise RuntimeError(res.stderr.strip() or f"Failed creating label {label}")


def build_body(issue: dict[str, Any], q: IssueQuality, gate_min: int) -> str:
    def bl(lst: list[Any], code: bool = False) -> str:
        if not lst:
            return "- n/a"
        if code:
            return "\n".join(f"- `{x}`" for x in lst)
        return "\n".join(f"- {x}" for x in lst)

    policy = ""
    if q.gate == "ready":
        policy = f"- Current gate: **ready** (score={q.score}, threshold={gate_min})\n- Automatic agentic execution: **allowed**"
    elif q.gate == "review":
        policy = f"- Current gate: **review** (score={q.score}, threshold={gate_min})\n- Automatic agentic execution: **allowed with review recommended**"
    elif q.gate == "blocked":
        policy = f"- Current gate: **blocked** (score={q.score}, threshold={gate_min})\n- Automatic agentic execution: **NOT allowed**"
    else:
        policy = "- Current gate: **n/a (done)**\n- Automatic agentic execution: n/a"

    return (
        f"## Context\n"
        f"- Ledger ID: `{issue['id']}`\n"
        f"- Phase: `{issue.get('phase', 'n/a')}`\n"
        f"- Type: `{issue.get('type', 'n/a')}`\n"
        f"- Priority: `{issue.get('priority', 'n/a')}`\n\n"
        f"## Problem Statement\n{issue.get('problem_statement', 'n/a')}\n\n"
        f"## Scope In\n{bl(issue.get('scope_in', []))}\n\n"
        f"## Scope Out\n{bl(issue.get('scope_out', []))}\n\n"
        f"## Target Files\n{bl(issue.get('target_files', []), code=True)}\n\n"
        f"## Dependencies\n{bl(issue.get('dependencies', []), code=True) if issue.get('dependencies') else '- none'}\n\n"
        f"## Implementation Steps\n{bl(issue.get('implementation_steps', []))}\n\n"
        f"## Test Plan\n{bl(issue.get('test_plan', []))}\n\n"
        f"## Success Metrics\n{bl(issue.get('success_metrics', []))}\n\n"
        f"## Risks\n{bl(issue.get('risks', []))}\n\n"
        f"## Execution Policy (Hybrid Mode)\n{policy}\n\n"
        f"## Acceptance Criteria\n{bl(issue.get('acceptance_criteria', []))}\n\n"
        f"## Evidence\n{bl(issue.get('evidence', []), code=True)}\n\n"
        f"## Governance\n"
        f"- Source ledger: `docs/ISSUE_LEDGER.json`\n"
        f"- Process: `docs/ISSUE_GOVERNANCE.md`\n"
    )


def sync_github(ledger: dict[str, Any], apply: bool, repo: str) -> None:
    if shutil.which("gh") is None:
        raise RuntimeError("gh not found")

    repo = repo or infer_repo_from_origin()
    if not repo:
        raise RuntimeError("Could not infer repo slug. Use --repo owner/repo")

    meta = ledger.get("meta", {})
    gate_min = int(meta.get("quality_gate_min_score_for_agentic") or 80)
    weights = meta.get("quality_score_weights") or DEFAULT_WEIGHTS
    issues = ledger.get("issues", [])

    quality_map = {i["id"]: score_issue(i, weights, gate_min) for i in issues}

    wanted_labels = {"ledger-managed"}
    for i in issues:
        wanted_labels.add(f"phase:{i.get('phase', 'unknown')}")
        wanted_labels.add(f"type:{i.get('type', 'unknown')}")
        wanted_labels.add(f"priority:{i.get('priority', 'unknown')}")
        wanted_labels.add(f"status:{i.get('status', 'unknown')}")
        wanted_labels.add(AGENTIC_LABELS[quality_map[i['id']].gate])

    ensure_labels(repo, sorted(wanted_labels), apply=apply)

    existing = gh_json(["gh", "issue", "list", "--repo", repo, "--state", "all", "--limit", "500", "--json", "number,title,state,labels"])
    by_id: dict[str, dict[str, Any]] = {}
    for e in existing:
        t = e.get("title", "")
        if t.startswith("[") and "]" in t:
            by_id[t[1:t.index("]")]] = e

    for issue in issues:
        issue_id = issue["id"]
        q = quality_map[issue_id]
        gate_label = AGENTIC_LABELS[q.gate]
        labels = [
            "ledger-managed",
            f"phase:{issue.get('phase', 'unknown')}",
            f"type:{issue.get('type', 'unknown')}",
            f"priority:{issue.get('priority', 'unknown')}",
            f"status:{issue.get('status', 'unknown')}",
            gate_label,
        ]
        title = f"[{issue_id}] {issue['title']}"
        body = build_body(issue, q, gate_min)

        found = by_id.get(issue_id)
        if not found:
            print(f"[CREATE] {title}")
            if apply:
                r = run_cmd(["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body, "--label", ",".join(labels)])
                if r.returncode != 0:
                    raise RuntimeError(r.stderr.strip() or f"Create failed: {issue_id}")
            continue

        n = str(found["number"])
        print(f"[UPDATE] #{n} {title}")
        if apply:
            existing_names = {x.get("name") for x in found.get("labels", []) if isinstance(x, dict)}
            for old in [x for x in existing_names if x in set(AGENTIC_LABELS.values()) and x != gate_label]:
                rr = run_cmd(["gh", "issue", "edit", n, "--repo", repo, "--remove-label", old])
                if rr.returncode != 0:
                    raise RuntimeError(rr.stderr.strip() or f"Remove label failed: {issue_id}")

            r = run_cmd(["gh", "issue", "edit", n, "--repo", repo, "--title", title, "--body", body, "--add-label", ",".join(labels)])
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip() or f"Update failed: {issue_id}")

        desired_closed = issue.get("status") == DONE_STATUS
        currently_closed = found.get("state", "").upper() == "CLOSED"

        if desired_closed and not currently_closed:
            print(f"[CLOSE] #{n} {issue_id}")
            if apply:
                r = run_cmd(["gh", "issue", "close", n, "--repo", repo, "--comment", "Closing via issue governance sync (status=done)."])
                if r.returncode != 0:
                    raise RuntimeError(r.stderr.strip() or f"Close failed: {issue_id}")

        if not desired_closed and currently_closed:
            print(f"[REOPEN] #{n} {issue_id}")
            if apply:
                r = run_cmd(["gh", "issue", "reopen", n, "--repo", repo, "--comment", "Reopening via issue governance sync (status!=done)."])
                if r.returncode != 0:
                    raise RuntimeError(r.stderr.strip() or f"Reopen failed: {issue_id}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Issue governance audit and GitHub sync")
    p.add_argument("--ledger", default=str(LEDGER_PATH))
    p.add_argument("--audit", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--repo", default="")
    p.add_argument("--apply", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    ledger = load_ledger(Path(args.ledger))
    audit = audit_ledger(ledger)

    if args.report:
        write_report(ledger, audit)
        print(f"Audit report written to {REPORT_PATH}")

    if args.audit:
        if audit.errors:
            print("Ledger audit failed:")
            for e in audit.errors:
                print(f"- {e}")
            return 1
        print("Ledger audit passed")

    if args.repo or args.apply:
        print(f"Running GitHub sync in {'APPLY' if args.apply else 'DRY-RUN'} mode")
        sync_github(ledger, apply=args.apply, repo=args.repo)

    if not args.audit and not args.report and not args.repo and not args.apply:
        write_report(ledger, audit)
        if audit.errors:
            print("Ledger audit failed. See report for details.")
            return 1
        print("Ledger audit passed. Report updated.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
