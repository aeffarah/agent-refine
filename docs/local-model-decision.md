# Local model decision record

Accepted for scoped coding jobs on a 24 GB M4 MacBook Air. Inference runs locally.

## Decision
Use Inkling Q2 (`inkling-2-mini@q2_k_xl`) at 24,576 tokens with tuned runtime settings for local coding jobs through the Bionic LM Studio API on `http://127.0.0.1:1235/v1`, driven by native OpenCode. See the [local coding guide](local-coding.md) for the current load configuration.

## Evidence
- Ornith 4-bit at 16K passed a small README edit and 38 tests.
- Ornith 6-bit at 16K guessed the API response, then attempted a mock server on Bionic’s occupied port. Its probe failed the live loaded and unloaded checks.
- Inkling Q2 queried the real API, wrote the working probe, and verified loaded/unloaded cases in about five minutes.
- Initial Inkling 16K left only 16–20% system-wide memory free. Tuned 16K (batch 512, two checkpoints, one prediction, Flash Attention) showed about 27–28% free and passed a follow-up fix plus 38 tests.
- A 12K trial exhausted context after collecting tool output. OpenCode’s initial request alone used about 8,100 input tokens.
- Bionic estimated about 300 MB more memory for 24K than 16K. One direct 24K request processed 23,621 input tokens and spent 510 of its 512 output tokens on reasoning. It returned no answer. A short request passed.

## Why this decision
Inkling had already demonstrated that it could inspect the live API and verify its own work. Reducing its evaluation batch and checkpoint count gave us concrete runtime settings to tune while keeping the same model weights. The follow-up edit and test run passed at tuned 16K. The memory percentages are system-wide snapshots.

Ornith's failure called for changes to how it gathers evidence and checks its work. Increasing the quantization from 4-bit to 6-bit did not establish an improvement across the two different tasks. The observed readiness-probe result made Inkling the better starting point for this workflow.

## Codex oversight

Codex defines the scope and acceptance command. Inkling runs the job locally through OpenCode with a fresh session, named files, and bounded tool output. Run the acceptance command independently and inspect the diff for scope. If a check fails, give Inkling one focused retry with the actual error. Escalate unresolved failures or judgment calls to Codex with the diff and failing output. Count jobs that pass without escalation to see whether the workflow saves paid inference.

The current workflow runs one job at a time. Persistent scheduling and restart recovery still need implementation and validation. The near-limit 24K coding workflow remains unverified. Synthetic benchmarks and custom executor development are paused.
