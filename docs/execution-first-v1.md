# Execution-first instruction experiment (v1)

This exploratory intervention compares the existing kpi-v1 baseline (three trials) against three fresh execution-first trials on profile m4-ornith-01.

Keep the original task text, fixture, acceptance checker, model, model settings, OpenCode build mode and 300-second budget fixed. The only intended change is a generic instruction prefix in the same user message (not a system-prompt change). No external validator feedback or reasoning setting changes during the trial. Run a fresh session and workspace each time.

Exact prefix, followed by a blank line and the original task prompt:

> Work execution-first. Inspect only what you need, choose the simplest implementation that satisfies the requirements, and apply it promptly. Do not repeatedly reconsider equivalent valid designs. After editing, check the actual result against the requirements using a concise, concrete verification. Correct any confirmed defect, then stop. Do not claim success without checking the result.

Use condition execution-first, trial 1 through 3, with profile m4-ornith-01. Start timing at prompt submission and interrupt at 300 seconds if not complete. Record actual elapsed time and any cutoff deviations; do not cap reported observed runtime artificially. Keep all results. Report output acceptance separately from successful completion within budget. Compare median observed time (including timeouts), median recorded reasoning tokens (note incomplete telemetry), and success count. The small, sequential sample is exploratory, not statistical proof, and the intervention was selected after observing baseline failures. Later testing on unseen tasks is necessary to assess generalization.

Baseline trial 3 was manually interrupted at 356.663 seconds; the first completed edit was at 306.120 seconds, so it failed even under a strict 300-second cutoff. Acceptance at the late interruption does not establish acceptance at the deadline.
