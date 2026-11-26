# Experimental reasoning governor

OpenCode 1.19.6 local server probes established session creation, asynchronous prompting, live SSE part deltas, reasoning/text attribution, and session-level abort at 102 streamed reasoning characters against a 100-character test threshold. Inference-side cancellation has not been independently verified.

Start a loopback-only OpenCode server using a trusted local model configuration. Use a separate server-mode profile, not the CLI or interactive profile. Run one task at a time:

```sh
python3 governor.py write-v1 --profile m4-ornith-server-01 --model local/ornith-1.5-9b-mlx
```

Omit the character threshold for a server-mode baseline. To test a cumulative reasoning threshold, add --reasoning-chars 1000. The threshold is exploratory, not calibrated or a token limit. The supervisor checks streamed text deltas, not hidden token counts. It uses the same frozen task and independent validator as the CLI runner. A directory query is supplied to the server and the session directory must match the fresh workspace before prompting. Directory routing is not a sandbox. Verify the backend is idle before each trial. No automatic retries or continuation yet.

Deadline or threshold triggers an abort request; network delay and cancellation cleanup may exceed the nominal deadline. Abort acknowledgment and OpenCode idle status are not proof of inference cancellation. Threshold-aborted runs are scored as aborted even if files happen to pass. Reports store aggregates only under gitignored private/governor. The server may retain raw sessions. No raw sessions or reasoning text should be published.

Next: verify workspace routing, compare server baselines with supervised conditions, establish safe cancellation and bounded same-session recovery. This version does not claim performance improvement.
