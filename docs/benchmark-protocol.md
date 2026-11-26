# Evaluation protocol (draft)

## Objective

Improve verified task completion and time-to-completion while retaining useful reasoning. Avoid optimizing token count at the expense of correctness.

## Controlled comparisons

- Freeze an initial task fixture, acceptance tests and allowed tools.
- Start each run from a fresh project copy and session. Record hardware, model identifier, quantization, inference runtime, OpenCode version, model settings, prompt, and wall-clock budget. Record whether settings are verified or merely declared.
- Change one factor at a time (baseline, instructions, supported reasoning control, or supervisor). Keep inference/runtime settings fixed otherwise. Run at least three trials per condition initially; report each trial, success rate, and median elapsed time. Avoid claiming statistical significance from small samples.
- Verify output with independent acceptance tests, not agent self-report. Include a minimal file-writing task, a scoped HTML component edit, and a multi-component interactive dashboard task. Fixtures and acceptance tests for these tasks are future work.
- Record timeouts and aborted attempts as failures unless independent tests establish completion. Record wall time including overhead, and generation time separately when available. Report missing token counts rather than treating interrupted generation as zero work.
- Include total token consumption, tool calls, repeats, edit calls, tests passed, changed files, and hardware memory pressure where measured. Protect raw logs; publish only reviewed aggregates and synthetic fixtures.

## Initial observation

Experiment 001 is a retrospective exploratory session containing multiple prompts and a context compaction, not a controlled trial. Its aggregate report was produced from the original OpenCode export. The private source export is intentionally excluded. The reported wall-clock span uses the earliest creation and latest completion timestamp, including the final abort; session metadata's updated timestamp precedes that abort. Reported counts are sums of assistant message telemetry. Identical reads are compared by target and exact returned text between recognized completed edits. Repeated read targets do not prove an infinite loop. No dashboard acceptance tests were run because the session reported no file changes.

## Proposed interventions (untested)

- Short execution-first instructions: read once, make a small change, test, then continue.
- Verify runtime support for reasoning controls before relying on them.
- Cap retries and detect repeated reads without recognized progress; stop for human review if recovery fails.
- Consider fine-tuning only after identifying repeatable behavioral deficits and collecting corrected examples with verified outcomes.
