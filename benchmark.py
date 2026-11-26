"""Prepare and independently score small, reproducible OpenCode tasks.

This runner never executes agent-generated code or launches an agent.
"""
import argparse
from collections import defaultdict
import hashlib
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
from statistics import median
import sys

from agent_refine import analyze


HTML_BEFORE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Atlas benchmark</title>
<style>
body{background:#0a0e17;color:#e6eaf2;font-family:system-ui}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.card{background:#111827;border:1px solid #1f2937;border-radius:14px;padding:20px}
</style>
</head>
<body>
<section id="features" class="grid"><article class="card">Predictive insights</article></section>
"""
HTML_AFTER = """<section id="pricing"><p>Starter: $19/mo</p></section>
<footer>Atlas benchmark fixture</footer>
</body>
</html>
"""
KPIS = (("Revenue", "$84,205"), ("Projected growth", "+27.3%"),
        ("Active customers", "1,482"), ("Risk score", "Low"))
CONDITIONS = ("baseline", "execution-first", "reasoning-off", "supervised", "recovery", "direct-staged")
TASKS = {
    "write-v1": {
        "budget_seconds": 120,
        "files": {"README.txt": "AgentRefine synthetic fixture.\n"},
        "prompt": ("Create hello.txt containing exactly Hello Atlas followed by a single newline. "
                   "Do not modify README.txt or create other files. Work only in this directory. "
                   "Do not install dependencies or use external services.")
    },
    "kpi-v1": {
        "budget_seconds": 300,
        "files": {"index.html": HTML_BEFORE + HTML_AFTER},
        "prompt": ("Modify only index.html. Insert a section with id demo and class grid immediately "
                   "between features and pricing. Add exactly four direct child article elements, each "
                   "with classes card and kpi, displaying these label/value pairs: Revenue / $84,205; "
                   "Projected growth / +27.3%; Active customers / 1,482; Risk score / Low. "
                   "Use plain HTML with existing styles; no new CSS, scripts or inline styles. "
                   "Use only section, article, div, h2, h3, p, strong or span tags in the insertion; "
                   "only class and id attributes are allowed. Preserve every existing byte outside "
                   "the insertion and do not create other files. Work only in this directory. "
                   "Do not install dependencies or use external services.")
    }
}


def spec_hash(task):
    payload = json.dumps(TASKS[task], sort_keys=True, ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()


def prepare(task, workspace):
    workspace.mkdir(parents=True, exist_ok=False)
    for name, content in TASKS[task]["files"].items():
        (workspace / name).write_bytes(content.encode("utf-8"))
    return TASKS[task]["prompt"]


class KpiParser(HTMLParser):
    """Strict parser for the small, explicitly constrained insertion, not general HTML."""
    tags = {"section", "article", "div", "h2", "h3", "p", "strong", "span"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.roots = 0
        self.cards = []
        self.valid = True

    def handle_starttag(self, tag, attrs):
        depth = len(self.stack)
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if (tag not in self.tags or len(attrs) != len(attributes)
                or any(key not in {"class", "id"} or value is None for key, value in attrs)):
            self.valid = False
        if depth == 0:
            self.roots += 1
            self.valid &= tag == "section" and attributes.get("id") == "demo" and "grid" in classes
        elif depth == 1:
            self.valid &= tag == "article" and {"card", "kpi"} <= classes
            self.cards.append([])
        elif tag in {"section", "article"}:
            self.valid = False
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.valid = False
        else:
            self.stack.pop()

    def handle_startendtag(self, tag, attrs):
        self.valid = False

    def handle_data(self, data):
        if data.strip():
            if len(self.stack) < 2 or not self.cards:
                self.valid = False
            else:
                self.cards[-1].append(data.strip())

    def handle_decl(self, decl):
        self.valid = False

    def unknown_decl(self, data):
        self.valid = False

    def handle_pi(self, data):
        self.valid = False

    def result(self):
        actual = [" ".join(" ".join(card).split()) for card in self.cards]
        expected = [f"{label} {value}" for label, value in KPIS]
        return (bool(self.valid and not self.stack and self.roots == 1 and len(self.cards) == 4),
                sorted(actual) == sorted(expected))


def evaluate(task, workspace):
    if not workspace.is_dir() or workspace.is_symlink():
        raise ValueError("Workspace must be an existing non-symlink directory")
    names = {"README.txt", "hello.txt"} if task == "write-v1" else {"index.html"}
    entries = list(workspace.iterdir())
    scope = {p.name for p in entries} == names and all(
        p.is_file() and not p.is_symlink() for p in entries)
    # Do not follow symlinks, read devices or execute any output.
    def read(name):
        path = workspace / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
            return None
        return path.read_bytes()

    checks = {"workspace_scope": scope}
    if task == "write-v1":
        checks["fixture_preserved"] = read("README.txt") == TASKS[task]["files"]["README.txt"].encode()
        checks["exact_output"] = read("hello.txt") == b"Hello Atlas\n"
    else:
        raw = read("index.html")
        try:
            html = raw.decode("utf-8") if raw is not None else ""
        except UnicodeDecodeError:
            html = ""
        shell = html.startswith(HTML_BEFORE) and html.endswith(HTML_AFTER)
        checks["fixture_preserved"] = shell
        checks["valid_demo_structure"] = False
        checks["exact_kpi_values"] = False
        if shell:
            parser = KpiParser()
            try:
                parser.feed(html[len(HTML_BEFORE):-len(HTML_AFTER)])
                parser.close()
                checks["valid_demo_structure"], checks["exact_kpi_values"] = parser.result()
            except (ValueError, AssertionError):
                pass
    return checks


def score(task, workspace, condition, trial, profile, elapsed, outcome, session=None):
    if condition not in CONDITIONS or not isinstance(trial, int) or trial < 1:
        raise ValueError("Invalid condition or trial")
    if not isinstance(profile, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", profile):
        raise ValueError("Use a neutral lowercase environment profile ID (max 40 characters)")
    if not math.isfinite(elapsed) or elapsed < 0 or outcome not in ("completed", "timeout", "aborted"):
        raise ValueError("Invalid elapsed time or outcome")
    checks = evaluate(task, workspace)
    budget = TASKS[task]["budget_seconds"]
    return {
        "schema_version": 1, "task": task, "task_spec_sha256": spec_hash(task),
        "profile": profile, "condition": condition, "trial": trial,
        "budget_seconds": budget, "elapsed_seconds": elapsed, "outcome": outcome,
        "checks": checks, "acceptance_passed": all(checks.values()),
        "success": all(checks.values()) and elapsed <= budget and outcome == "completed",
        "telemetry": analyze(session) if session is not None else None,
    }


def compare(reports):
    groups = defaultdict(list)
    seen = set()
    for report in reports:
        task = report["task"]
        if (report.get("schema_version") != 1 or task not in TASKS
                or report["task_spec_sha256"] != spec_hash(task)):
            raise ValueError("Report uses a different task specification or schema")
        key = (task, report["profile"], report["condition"])
        identity = (*key, report["trial"])
        if identity in seen:
            raise ValueError("Duplicate trial; use one report per task/profile/condition/trial")
        seen.add(identity)
        groups[key].append(report)
    result = []
    for (task, profile, condition), runs in sorted(groups.items()):
        successful = [r for r in runs if r["success"]]
        result.append({
            "task": task, "profile": profile, "condition": condition, "trials": len(runs),
            "successes": len(successful), "success_rate": len(successful) / len(runs),
            "median_elapsed_all_seconds": median(r["elapsed_seconds"] for r in runs),
            "median_elapsed_success_seconds": median(r["elapsed_seconds"] for r in successful) if successful else None,
        })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    for action in ("prepare", "check"):
        cmd = commands.add_parser(action)
        cmd.add_argument("task", choices=TASKS)
        cmd.add_argument("workspace", type=Path)
        if action == "check":
            cmd.add_argument("--condition", choices=CONDITIONS, required=True)
            cmd.add_argument("--trial", type=int, required=True)
            cmd.add_argument("--profile", required=True)
            cmd.add_argument("--elapsed", type=float, required=True)
            cmd.add_argument("--outcome", choices=("completed", "timeout", "aborted"), required=True)
            cmd.add_argument("--session", type=Path)
    comparison = commands.add_parser("compare")
    comparison.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "list":
            for task, spec in TASKS.items():
                print(f"{task}: {spec['budget_seconds']}s budget")
            return 0
        if args.command == "prepare":
            print(prepare(args.task, args.workspace))
            return 0
        if args.command == "compare":
            reports = [json.loads(path.read_text(encoding="utf-8")) for path in args.reports]
            print(json.dumps(compare(reports), indent=2))
            return 0
        session = json.loads(args.session.read_text(encoding="utf-8")) if args.session else None
        report = score(args.task, args.workspace, args.condition, args.trial, args.profile,
                       args.elapsed, args.outcome, session)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["success"] else 2
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(f"Benchmark error ({type(exc).__name__}); check inputs and workspace.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
