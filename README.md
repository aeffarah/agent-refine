# AgentRefine

Local-first diagnostics and benchmarks for AI coding agents. The goal is to improve verified task completion on consumer hardware, not simply maximize token generation or suppress reasoning.

## Status

Early prototype (v0.4). Supports OpenCode JSON session analysis, controlled file-writing and HTML-editing benchmarks, independent static acceptance checks and experimental headless execution. It does not modify model weights. Experimental server supervision observes streamed reasoning characters and interrupts sessions at configurable thresholds; backend cancellation remains unverified.

## Quick start

Requires Python 3.10+; no third-party dependencies.

```sh
opencode session list
opencode export SESSION_ID > /tmp/session.json
python3 agent_refine.py /tmp/session.json
python3 -m unittest discover -s tests -v
```

To retain a report, redirect stdout to a file. The report uses aggregate counts, timing, and fixed diagnostic labels instead of prompts, reasoning text, tool arguments, file paths, or source code. Review any report before publishing it. Keep raw exports outside the repository.

### Local coding with OpenCode

The project-local OpenCode configuration uses Inkling 2 Mini Q2_K_XL via the LM Studio API on port 1235. See the [local coding guide](docs/local-coding.md) for the load settings and headless workflow. The [local model decision record](docs/local-model-decision.md) explains the model choice and how Codex supervises local jobs.

## Controlled benchmarks

Run `python3 benchmark.py list` to see the two frozen tasks. The benchmark runner prepares fresh synthetic fixtures, checks the final files independently, and compares reviewed aggregate results. See the [local benchmark guide](docs/controlled-benchmarks.md). Controlled aggregate results are available under `benchmarks/results/`. In three interactive KPI baseline trials, one passed within budget; three execution-first prompt trials all timed out without an edit. These small sequential samples are exploratory. Headless trials use a separate profile.

See the [automated runner guide](docs/automated-runner.md) for single-command execution. The first local headless write trial passed in 18.952 seconds; cancellation and containment remain unverified.

## First case study: Ornith 1.5 9B MLX

An exploratory OpenCode 1.19.6 session on an Apple M4 MacBook Air with 24 GB unified memory attempted to add an interactive dashboard to a static website. The model's declared OpenCode limits were 65,536 context tokens and 16,384 output tokens; actual runtime context behavior was not independently verified.

| Metric | Observed |
|---|---:|
| Wall-clock session span, including interruptions and gaps | 59m 55s |
| Recorded input tokens, cumulative | 127,168 |
| Recorded reasoning tokens | 34,048 |
| Recorded non-reasoning output tokens | 1,146 |
| Reasoning share of recorded generated tokens | 96.74% |
| Generation-limit stops | 2 |
| Completed read calls | 3 |
| Repeated read targets without recognized edits | 2 |
| Identical read outputs without recognized edits | 1 |
| Recognized completed edit calls | 0 |
| Files modified according to session summary | 0 |

Each length-limited generation recorded exactly 16,384 reasoning tokens and zero non-reasoning output tokens. The final aborted generation retained 21,076 reasoning characters but reported zero tokens. Recorded token totals therefore understate actual generation. The session includes a follow-up instruction and compaction; this is a failure case study, not a controlled benchmark trial or evidence of a universal model defect.

See the [aggregate baseline](benchmarks/001-ornith-baseline.json) and [evaluation protocol](docs/benchmark-protocol.md).

See the [governor guide](docs/reasoning-governor.md) and [experimental bounded recovery](docs/bounded-recovery.md).

See the [direct staged executor](docs/direct-executor.md) for an experimental local tool loop without OpenCode. It is not yet validated against the live model.

## Diagnostics

- Recorded token counts and per-response durations.
- Finish reasons, including length-limited and aborted responses.
- Repeated read targets and identical read results between recognized edits.
- Completed recognized editing calls, session-summary file count, and compaction events.
- Privacy-preserving JSON output for comparison across runs.

Signals are heuristics. Re-reading can be legitimate; shell commands or unfamiliar tools may edit files without being recognized. A successful editing call is not proof of a correct deliverable. The tool does not infer hidden reasoning or estimate missing token counts from character counts.

## Roadmap

1. Session analysis and privacy-safe reports (initial prototype).
2. Reproducible tasks, acceptance tests and comparisons (initial two-task suite implemented).
3. Controlled prompt and reasoning-budget experiments.
4. Live supervision with bounded retry and progress detection.
5. Multi-agent scheduling and visualization.
6. Fine-tuning only if supported by evidence and compatible licensing.

## Contributing

Feedback and sanitized reproducible cases are welcome. Do not share raw session exports, personal paths, credentials or proprietary source code. Report model/runtime versions and test criteria alongside performance results.
