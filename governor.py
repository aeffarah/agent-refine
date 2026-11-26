"""Experimental OpenCode SSE supervisor; local server only, not a sandbox."""
import argparse
from collections import Counter
import json
from pathlib import Path
import queue
import re
import sys
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from agent_refine import analyze
from benchmark import TASKS, evaluate, prepare, score

REPO = Path(__file__).resolve().parent


class Observer:
    """Count streamed characters, not tokens; filter to one session."""
    def __init__(self, sid):
        self.sid = sid
        self.types = {}
        self.chars = Counter()
        self.busy = False
        self.activity = False
        self.idle = False
        self.error = False

    def feed(self, event):
        kind = event.get("type")
        p = event.get("properties", {})
        part = p.get("part", {})
        if p.get("sessionID", part.get("sessionID")) != self.sid:
            return
        if kind == "session.status":
            status = p.get("status", {}).get("type")
            if status == "busy":
                self.busy = True
        elif kind == "message.part.updated":
            pid = part.get("id")
            if isinstance(pid, str):
                self.types[pid] = part.get("type")
        elif kind == "message.part.delta":
            pid, delta = p.get("partID"), p.get("delta")
            if (isinstance(pid, str) and isinstance(delta, str)
                    and p.get("field", "text") == "text"):
                self.chars[pid] += len(delta)
                self.activity = True
        elif kind == "session.idle" and (self.busy or self.activity):
            self.idle = True
        elif kind == "session.error":
            self.error = True

    def totals(self):
        totals = Counter()
        for pid, n in self.chars.items():
            kind = self.types.get(pid)
            totals[kind if kind in ("reasoning", "text", "tool") else "unknown"] += n
        return dict(totals)

    def reason(self, limit):
        if self.error:
            return "session_error"
        if self.idle:
            return "completed"
        if limit is not None and self.totals().get("reasoning", 0) >= limit:
            return "reasoning_limit"
        return None


class Client:
    def __init__(self, port, workspace):
        self.base = f"http://127.0.0.1:{port}"
        self.query = "?" + urlencode({"directory": str(workspace)})

    def url(self, path):
        return self.base + path + self.query

    def api(self, path, body=None, timeout=10):
        req = Request(self.url(path),
                      data=json.dumps(body).encode() if body is not None else None,
                      headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=timeout) as r:
            raw = r.read()
        return json.loads(raw) if raw else None


def listen(client, events, stop):
    """Read SSE without printing or persisting raw reasoning."""
    try:
        with urlopen(client.url("/event"), timeout=30) as r:
            data = []
            for raw in r:
                if stop.is_set():
                    return
                line = raw.decode("utf-8").rstrip("\r\n")
                if line.startswith("data:"):
                    data.append(line[5:].lstrip())
                elif not line and data:
                    e = json.loads("\n".join(data))
                    data.clear()
                    if isinstance(e, dict):
                        events.put(e.get("payload", e))
    except (OSError, ValueError):
        pass
    finally:
        events.put({"type": "stream.closed"})


def supervise(client, sid, prompt, model, budget, limit, events):
    provider, model_id = model.split("/", 1)
    obs = Observer(sid)
    reason = "deadline"
    ack = None
    start = time.monotonic()
    try:
        client.api(f"/session/{sid}/prompt_async", {
            "agent": "build",
            "model": {"providerID": provider, "modelID": model_id},
            "parts": [{"type": "text", "text": prompt}],
        }, timeout=min(10, budget))
        while time.monotonic() - start < budget:
            try:
                event = events.get(timeout=min(0.25, max(0, budget - (time.monotonic() - start))))
            except queue.Empty:
                continue
            if event.get("type") == "stream.closed":
                reason = "stream_disconnected"
                break
            obs.feed(event)
            decision = obs.reason(limit)
            if decision:
                reason = decision
                break
    except KeyboardInterrupt:
        reason = "operator_abort"
    except (OSError, ValueError, TypeError, KeyError):
        reason = "api_error"
    finally:
        if reason != "completed":
            try:
                ack = client.api(f"/session/{sid}/abort", {}, timeout=5) is True
            except (OSError, ValueError):
                ack = False
    elapsed = time.monotonic() - start
    # An idle OpenCode session does not prove that its inference backend stopped.
    try:
        status = client.api("/session/status", timeout=5).get(sid, {}).get("type", "not-listed")
    except (OSError, ValueError, AttributeError):
        status = "unknown"
    return {"stop_reason": reason, "elapsed_seconds": round(elapsed, 3),
            "streamed_characters": obs.totals(), "abort_acknowledged": ack,
            "final_status": status if status in ("busy", "idle", "retry", "not-listed") else "unknown",
            "inference_cancellation_verified": False}


def recovery_prompt(prompt):
    return ("Your previous generation was interrupted by the reasoning budget. "
            "Continue the same task using the current workspace. "
            "If the requested change is missing, apply the simplest valid edit now "
            "using an appropriate editing tool. Then check the actual result against "
            "the requirements and correct confirmed defects. Do not merely describe "
            "the solution or reconsider equivalent designs.\n\nOriginal task:\n" + prompt)


def can_recover(result, checks, remaining):
    return (result["stop_reason"] == "reasoning_limit"
            and result["abort_acknowledged"] is True
            and result["final_status"] in ("idle", "not-listed")
            and not all(checks.values())
            and checks.get("fixture_preserved") is True
            and remaining > 15)


def connect_events(client, timeout=10):
    events, stop = queue.Queue(), threading.Event()
    threading.Thread(target=listen, args=(client, events, stop), daemon=True).start()
    try:
        if events.get(timeout=timeout).get("type") != "server.connected":
            raise ValueError("Event stream not connected")
        return events, stop
    except BaseException:
        stop.set()
        raise


def run_recovery(client, sid, prompt, model, budget, limit, events, stop, task, workspace):
    """One optional same-session retry, within a shared wall-clock deadline."""
    start = time.monotonic()
    def remaining():
        return budget - (time.monotonic() - start)
    first = supervise(client, sid, prompt, model, remaining(), limit, events)
    phases = [first]
    decision = "not_eligible"
    if first["stop_reason"] == "completed":
        decision = "initial_completed"
    elif first["stop_reason"] == "reasoning_limit":
        checks = evaluate(task, workspace)
        # Do not resume if unexpected entries appeared or the fixture was damaged.
        allowed = set(TASKS[task]["files"]) | ({"hello.txt"} if task == "write-v1" else set())
        safe_entries = all(p.name in allowed and p.is_file() and not p.is_symlink()
                           for p in workspace.iterdir())
        if all(checks.values()):
            decision = "acceptance_already_passed"
        elif safe_entries and can_recover(first, checks, remaining()):
            stop.set()
            second_stop = None
            try:
                # Give the cancellation a short settling window and reconnect, so
                # queued idle/delta events from the first phase are not replayed.
                time.sleep(2)
                status = client.api("/session/status", timeout=min(5, max(0.1, remaining())))
                if status.get(sid, {}).get("type", "not-listed") not in ("idle", "not-listed"):
                    decision = "session_not_idle"
                elif remaining() <= 15:
                    decision = "insufficient_budget"
                else:
                    second_events, second_stop = connect_events(client, timeout=min(10, remaining()))
                    if remaining() <= 0:
                        decision = "insufficient_budget"
                    else:
                        print("Reasoning limit reached; attempting one same-session recovery.", flush=True)
                        decision = "attempted"
                        phases.append(supervise(client, sid, recovery_prompt(prompt), model,
                                                remaining(), limit, second_events))
            except (OSError, ValueError, TypeError, AttributeError, queue.Empty):
                decision = "recovery_setup_failed"
            finally:
                if second_stop is not None:
                    second_stop.set()
    totals = Counter()
    for phase in phases:
        totals.update(phase["streamed_characters"])
    return dict(phases[-1], elapsed_seconds=round(time.monotonic() - start, 3),
                streamed_characters=dict(totals), recovery_attempts=len(phases)-1,
                recovery_decision=decision, phases=phases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=TASKS)
    parser.add_argument("--port", type=int, default=4097)
    parser.add_argument("--model", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--trial", type=int, default=1)
    parser.add_argument("--reasoning-chars", type=int,
                        help="Cumulative streamed reasoning character threshold; omit for server baseline")
    parser.add_argument("--recover-once", action="store_true",
                        help="Experimental same-session retry; requires accepting unverified backend cancellation")
    parser.add_argument("--workspace-root", type=Path, default=Path.home() / "agent-refine-runs")
    args = parser.parse_args()
    if (not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", args.profile)
            or args.trial < 1 or not 1 <= args.port <= 65535
            or "/" not in args.model or not all(args.model.split("/", 1))
            or (args.reasoning_chars is not None and args.reasoning_chars < 1)):
        parser.error("Invalid profile, trial, port, model or threshold")
    if args.recover_once and args.reasoning_chars is None:
        parser.error("--recover-once requires --reasoning-chars")
    root = args.workspace_root.expanduser().resolve()
    if root == REPO or REPO in root.parents:
        parser.error("Workspace root must be outside repository")
    condition = "recovery" if args.recover_once else ("supervised" if args.reasoning_chars is not None else "baseline")
    name = f"{args.task}-{args.profile}-{condition}-{args.trial}"
    workspace = root / name
    logs = REPO / "private" / "governor" / name
    if workspace.exists() or logs.exists():
        parser.error("Trial already exists; choose a new --trial")
    stop = threading.Event()
    try:
        prompt = prepare(args.task, workspace)
        logs.mkdir(parents=True, mode=0o700, exist_ok=False)
        client = Client(args.port, workspace)
        events, stop = connect_events(client)
        session = client.api("/session", {"title": "AgentRefine controlled benchmark"})
        sid = session["id"]
        # Refuse to prompt if the server does not confirm the intended directory.
        if not isinstance(session.get("directory"), str) or Path(session["directory"]).resolve() != workspace:
            raise ValueError("Server did not confirm benchmark workspace")
        print(f"Running {name}; reasoning limit={args.reasoning_chars}", flush=True)
        budget = TASKS[args.task]["budget_seconds"]
        if args.recover_once:
            result = run_recovery(client, sid, prompt, args.model, budget,
                                  args.reasoning_chars, events, stop, args.task, workspace)
        else:
            result = supervise(client, sid, prompt, args.model, budget, args.reasoning_chars, events)
        reason = result["stop_reason"]
        outcome = ("completed" if reason == "completed" and result["final_status"] in ("idle", "not-listed")
                   else "timeout" if reason == "deadline" else "aborted")
        report = score(args.task, workspace, condition, args.trial, args.profile,
                       result["elapsed_seconds"], outcome)
        report["governor"] = dict(result, reasoning_char_limit=args.reasoning_chars,
                                  mode="opencode-server", policy_version=2 if args.recover_once else 1)
        report["governor"].setdefault("recovery_attempts", 0)
        if result["final_status"] in ("idle", "not-listed"):
            try:
                messages = client.api(f"/session/{sid}/message")
                report["telemetry"] = analyze({"info": session, "messages": messages})
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                pass
        with (logs / "report.json").open("x", encoding="utf-8") as f:
            json.dump(report, f, indent=2, sort_keys=True)
            f.write("\n")
        print(json.dumps(report, indent=2, sort_keys=True))
        if reason != "completed" or args.recover_once:
            print("Verify local inference is idle before starting another run.", file=sys.stderr)
        return 0 if report["success"] else 2
    except (OSError, ValueError, TypeError, KeyError, queue.Empty) as exc:
        print(f"Governor stopped ({type(exc).__name__}); check server, workspace and logs.", file=sys.stderr)
        return 1
    finally:
        stop.set()


if __name__ == "__main__":
    raise SystemExit(main())
