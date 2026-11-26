# Bounded recovery (experimental policy v2)

The operator demonstrated that an earlier aborted read-only OpenCode session could be resumed. This does not prove that the inference backend cancels immediately. Recovery is opt-in and not a sandbox.

```sh
python3 governor.py kpi-v1 --profile m4-ornith-server-01 \
  --model local/ornith-1.5-9b-mlx --reasoning-chars 3000 --recover-once
```

This creates a new workspace and a new session, with condition recovery (distinct from baseline and abort-only supervised). The original task prompt and 300-second KPI budget remain unchanged. If the initial cumulative streamed reasoning limit is hit, the supervisor requests abort, checks acknowledgment and session status, validates the fixture and workspace, and waits two seconds before checking status again. If still eligible, a fresh SSE connection monitors one follow-up prompt in the same session. The follow-up restates the task and asks for direct implementation and concrete verification; it does not include the solution. Each phase has the same character threshold, so total reasoning can exceed that threshold. The shared wall clock includes cancellation and recovery setup; network cleanup can overrun. A second interruption ends the trial. No recovery on timeout, session error, unexpected entries, damaged fixture, already-passing acceptance or insufficient time. An already-passing aborted run is still scored as aborted under the existing benchmark contract.

Reports preserve per-phase aggregates and combined counts, not raw text. Backend cancellation is unverified, so run only one trial at a time with the local backend idle and monitor it during this experiment. If you see simultaneous generation, abort the session and stop. Do not use unattended. Session idle and a fresh event stream reduce stale-event risks but do not guarantee backend quiescence. This is a feasibility experiment, not an established optimization; threshold was chosen after earlier exploratory observations. No performance improvement claimed.
