# Automated runner (experimental)

Python 3.10+, POSIX process groups, installed OpenCode and a configured model. Start with a single trial. Use a separate profile for headless execution: earlier interactive trials are not directly controlled comparisons.

```sh
python3 runner.py write-v1 --profile m4-ornith-cli-01 \
  --model local/ornith-1.5-9b-mlx \
  --config "$HOME/Projects/first-website/opencode.json"
```

The runner creates a fresh workspace outside the repository, sets cwd, PWD and --dir, launches OpenCode in build mode without --auto, records JSON events and stderr, enforces the frozen task's wall-clock budget, scores the files using benchmark.py, and attempts a session export. Report and raw logs are stored under gitignored private/runner/; never commit raw logs. The runner does not publish results. Choose a new --start-trial number for reruns. --trials N runs sequentially but stops the batch after timeout or abort until inference cancellation is verified. --condition execution-first uses the documented prefix unchanged. The default is baseline.

Timing includes CLI startup and cancellation cleanup, not export. A zero exit code is insufficient: a final stop event and a valid independent acceptance check are required, along with the time limit. Missing export telemetry does not invalidate verified file acceptance. JSON events are summarized after the run; incremental reasoning visibility has not been established. Process-group termination does not prove the separate inference server has stopped. Verify it is idle before resuming after abort or timeout.

This is not a sandbox. cwd/PWD/--dir are execution context, not containment. Use only trusted local configuration and synthetic fixtures, with no secrets or unrelated accessible files. The runner does not enforce local-only provider routing, prevent external filesystem writes, or constrain shell tools. Do not use unattended on sensitive systems. The initial smoke test wrote outside the workspace; the combined cwd/PWD/--dir correction passed a second smoke test, but cannot guarantee isolation. The automated runner itself needs local integration testing.
