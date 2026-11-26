# AgentRefine

Local-first diagnostics and benchmarks for AI coding agents. The goal is to improve verified task completion on consumer hardware, not simply maximize token generation or suppress reasoning.

## Status

Early prototype (v0.1). Supports OpenCode JSON session exports. It analyzes completed sessions; it does not modify model weights, supervise live agents, or prove task success.

## Quick start

Requires Python 3.10+; no third-party dependencies.

```sh
opencode session list
opencode export SESSION_ID > /tmp/session.json
python3 agent_refine.py /tmp/session.json
python3 -m unittest discover -s tests -v
```

To retain a report, redirect stdout to a file. The report uses aggregate counts, timing, and fixed diagnostic labels instead of prompts, reasoning text, tool arguments, file paths, or source code. Review any report before publishing it. Keep raw exports outside the repository.

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

## Diagnostics

- Recorded token counts and per-response durations.
- Finish reasons, including length-limited and aborted responses.
- Repeated read targets and identical read results between recognized edits.
- Completed recognized editing calls, session-summary file count, and compaction events.
- Privacy-preserving JSON output for comparison across runs.

Signals are heuristics. Re-reading can be legitimate; shell commands or unfamiliar tools may edit files without being recognized. A successful editing call is not proof of a correct deliverable. The tool does not infer hidden reasoning or estimate missing token counts from character counts.

## Roadmap

1. Session analysis and privacy-safe reports (initial prototype).
2. Reproducible tasks, acceptance tests and comparisons.
3. Controlled prompt and reasoning-budget experiments.
4. Live supervision with bounded retry and progress detection.
5. Multi-agent scheduling and visualization.
6. Fine-tuning only if supported by evidence and compatible licensing.

## Contributing

Feedback and sanitized reproducible cases are welcome. Do not share raw session exports, personal paths, credentials or proprietary source code. Report model/runtime versions and test criteria alongside performance results.
