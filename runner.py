"""Headless OpenCode benchmark runner. POSIX only; not a security sandbox."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from benchmark import TASKS, prepare, score, compare

PREFIX = ("Work execution-first. Inspect only what you need, choose the simplest "
          "implementation that satisfies the requirements, and apply it promptly. "
          "Do not repeatedly reconsider equivalent valid designs. After editing, "
          "check the actual result against the requirements using a concise, concrete "
          "verification. Correct any confirmed defect, then stop. Do not claim success "
          "without checking the result.")
KNOWN_EVENTS = {"step_start", "reasoning", "tool_use", "text", "step_finish", "error"}
KNOWN_FINISHES = {"stop", "tool-calls", "length", "error", "content-filter"}
REPO = Path(__file__).resolve().parent


def command(workspace, model, prompt):
    return ["opencode", "run", "--format", "json", "--thinking", "--dir",
            str(workspace), "--agent", "build", "--model", model, prompt]


def environment(workspace, config):
    env = os.environ.copy()
    env.update(PWD=str(workspace), OPENCODE_CONFIG=str(config))
    return env


def stop_group(proc):
    # The CLI and its descendants in this process group are interrupted.
    # A separately running inference server is not in this group.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            break
        if sig == signal.SIGTERM:
            try:
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
    proc.wait()


def run_process(args, workspace, env, stdout_path, stderr_path, budget):
    """Return elapsed wall-clock seconds to exit/cancellation, including cleanup."""
    with stdout_path.open("xb") as out, stderr_path.open("xb") as err:
        start = time.monotonic()
        proc = subprocess.Popen(args, cwd=workspace, env=env, stdout=out,
                                stderr=err, stdin=subprocess.DEVNULL,
                                start_new_session=True)
        outcome = "completed"
        try:
            proc.wait(timeout=max(0, budget - (time.monotonic() - start)))
        except subprocess.TimeoutExpired:
            outcome = "timeout"
            stop_group(proc)
        except KeyboardInterrupt:
            outcome = "aborted"
            stop_group(proc)
        elapsed = time.monotonic() - start
        if outcome == "completed":
            if elapsed > budget:
                outcome = "timeout"
            elif proc.returncode != 0:
                outcome = "aborted"
        return round(elapsed, 3), outcome, proc.returncode


def event_summary(path):
    """Read completed CLI events. Do not assume reasoning is streamed incrementally."""
    counts = Counter()
    ids = set()
    invalid = 0
    last_finish = None
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("not an object")
            except (ValueError, TypeError):
                invalid += 1
                continue
            kind = event.get("type")
            counts[kind if isinstance(kind, str) and kind in KNOWN_EVENTS else "other"] += 1
            sid = event.get("sessionID")
            if isinstance(sid, str) and re.fullmatch(r"ses_[A-Za-z0-9]+", sid):
                ids.add(sid)
            if kind == "step_finish":
                part = event.get("part")
                reason = part.get("reason") if isinstance(part, dict) else None
                last_finish = reason if isinstance(reason, str) and reason in KNOWN_FINISHES else "other"
    return ({"event_counts": dict(counts), "invalid_lines": invalid,
             "last_finish": last_finish, "session_count": len(ids)},
            next(iter(ids)) if len(ids) == 1 else None)


def export_session(sid, workspace, env, logdir):
    if not sid:
        return None, "missing_or_ambiguous_session"
    path = logdir / "session.json"
    try:
        _, outcome, rc = run_process(["opencode", "export", sid], workspace, env,
                                     path, logdir / "export.stderr.log", 30)
        if outcome != "completed" or rc != 0:
            return None, "export_failed"
        data = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or not isinstance(data.get("info"), dict)
                or data["info"].get("id") != sid or not isinstance(data.get("messages"), list)):
            return None, "invalid_export"
        return data, "available"
    except (OSError, ValueError, TypeError):
        return None, "export_failed"


class TrialExistsError(ValueError):
    pass


def run_trial(args, trial):
    name = f"{args.task}-{args.profile}-{args.condition}-{trial}"
    workspace = args.workspace_root / name
    logdir = REPO / "private" / "runner" / name
    if workspace.exists() or logdir.exists():
        raise TrialExistsError("Trial already exists; choose another --start-trial number.")
    logdir.mkdir(mode=0o700, parents=True, exist_ok=False)
    prompt = prepare(args.task, workspace)
    if args.condition == "execution-first":
        prompt = PREFIX + "\n\n" + prompt
    env = environment(workspace, args.config)
    events = logdir / "events.jsonl"
    print(f"Running {name} (budget {TASKS[args.task]['budget_seconds']}s)", flush=True)
    elapsed, outcome, rc = run_process(command(workspace, args.model, prompt),
                                       workspace, env, events, logdir / "stderr.log",
                                       TASKS[args.task]["budget_seconds"])
    summary, sid = event_summary(events)
    if outcome == "completed" and (summary["last_finish"] != "stop"
                                   or summary["event_counts"].get("error", 0)
                                   or summary["session_count"] != 1):
        outcome = "aborted"
    # Score immediately after CLI exit, before exporting session telemetry.
    report = score(args.task, workspace, args.condition, trial, args.profile, elapsed, outcome)
    session, export_status = export_session(sid, workspace, env, logdir)
    if session is not None:
        from agent_refine import analyze
        try:
            report["telemetry"] = analyze(session)
        except (TypeError, ValueError, AttributeError, KeyError):
            export_status = "unsupported_export"
    report["runner"] = dict(summary, mode="opencode-cli", exit_code=rc,
                            export_status=export_status,
                            elapsed_basis="monotonic_cli_launch_through_exit",
                            inference_cancellation_verified=False)
    with (logdir / "report.json").open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"Trial {trial}: {outcome}, {elapsed:.3f}s, "
          f"acceptance={report['acceptance_passed']}, success={report['success']}, "
          f"export={export_status}", flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=TASKS)
    parser.add_argument("--profile", required=True, help="Separate ID for headless CLI trials")
    parser.add_argument("--model", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--condition", choices=("baseline", "execution-first"), default="baseline")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--start-trial", type=int, default=1)
    parser.add_argument("--workspace-root", type=Path, default=Path.home() / "agent-refine-runs")
    args = parser.parse_args()
    if os.name != "posix":
        parser.error("Runner requires POSIX process groups")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", args.profile):
        parser.error("Use a neutral lowercase profile ID (max 40 characters)")
    if args.trials < 1 or args.start_trial < 1:
        parser.error("Trial counts must be positive")
    args.config = args.config.expanduser().resolve()
    args.workspace_root = args.workspace_root.expanduser().resolve()
    if not args.config.is_file():
        parser.error("Config must exist")
    if args.workspace_root == REPO or REPO in args.workspace_root.parents:
        parser.error("Workspace root must be outside the repository")
    reports = []
    try:
        for trial in range(args.start_trial, args.start_trial + args.trials):
            report = run_trial(args, trial)
            reports.append(report)
            if report["outcome"] != "completed":
                # Until cancellation has been verified, never start a new model run
                # automatically after timeout, CLI failure or operator interruption.
                print("Batch stopped after timeout/abort. Verify inference is idle before resuming.")
                break
        print(json.dumps(compare(reports), indent=2))
    except TrialExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyboardInterrupt) as exc:
        print(f"Runner stopped ({type(exc).__name__}); inspect private logs.", file=sys.stderr)
        return 1
    return 0 if all(r["success"] for r in reports) else 2


if __name__ == "__main__":
    raise SystemExit(main())
