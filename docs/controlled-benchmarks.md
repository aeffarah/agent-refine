# Controlled benchmarks v0.2

Two synthetic tasks isolate basic file execution and scoped HTML editing. They do not benchmark visual quality or interactive JavaScript yet.

| Task | Budget | Acceptance |
| --- | ---: | --- |
| write-v1 | 120 seconds | Exact file content; unchanged seed file; no extra files |
| kpi-v1 | 300 seconds | Four exact KPI cards; valid constrained markup; original bytes preserved; no extra files |

## Run locally

Use a fresh workspace outside the repository for each trial. Keep the agent's configuration outside that workspace (e.g. in OpenCode's global configuration) so the no-extra-files acceptance check remains meaningful. Configure OpenCode to deny unrelated filesystem, shell, network and installation access as appropriate; a prompt is not a sandbox. Run one local inference session at a time. Review agent permission requests rather than granting broad access.

From the repository directory:

~~~sh
python3 benchmark.py list
python3 benchmark.py prepare write-v1 ~/agent-refine-runs/write-baseline-1
~~~

Copy the printed prompt exactly into a fresh OpenCode session in that workspace. Use a stopwatch from submitting the prompt until the agent stops; manually interrupt at the task budget. Do not send follow-up instructions in the same trial. Export the session outside the repository, if available.

Return to the repository directory and score the workspace:

~~~sh
mkdir -p private/results
python3 benchmark.py check write-v1 ~/agent-refine-runs/write-baseline-1 \
  --profile m4-ornith-01 --condition baseline --trial 1 \
  --elapsed 120 --outcome timeout \
  > private/results/write-baseline-1.json
~~~

The elapsed time and outcome above are **illustrative**, not observed results. Replace them with the actual measurement; use completed, timeout or aborted as appropriate. Optionally append --session /path/to/private-export.json to include aggregate telemetry. The runner returns 0 on success, 2 for a scored failure (JSON is still emitted), and 1 for input errors. Missing telemetry is null, not zero.

Repeat each condition at least three times with fresh workspaces and sessions. For the execution-first condition, change only the agent instruction layer; for reasoning-off, verify runtime support first. Record the exact intervention separately. Never overwrite failed reports.

~~~sh
python3 benchmark.py compare private/results/*.json
~~~

Comparison groups by task, profile and condition, rejects duplicate trial IDs, and reports success rate and median elapsed time for all trials and successful trials separately. It does not rank different tasks against each other. A profile identifies a pinned environment (record hardware, quantization, runtime, OpenCode version, declared and verified limits, sampling settings, and baseline system instructions separately). Do not mix changed environments under the same profile except the explicitly tested intervention. Profiles are manual labels, not automatic verification. Task spec hashes identify the frozen prompt, budget and fixture. Bump the task version whenever acceptance criteria change.

## Limitations and privacy

The runner prepares fixtures and independently checks resulting files, but does not execute the agent, enforce a timeout or sandbox, or run generated HTML/JS. Wall time and termination status are operator-reported. Static HTML checks are intentionally narrow. Successful tests do not prove visual quality. A scored timeout or abort is a failure under this protocol, even when files pass acceptance, to keep the termination criterion explicit.

Reports omit file contents, local paths and raw transcripts. Use neutral profile IDs and review reports before publishing. Raw session exports and working directories stay private. The retrospective 001 case study is not comparable to these frozen tasks; no controlled model runs have been recorded yet.
