# Development checkpoint — 2026-11-26

## Current state
- Main includes the analyzer, independent benchmarks, automated CLI runner and SSE reasoning governor (PRs 3–5 merged).
- PR #6 adds opt-in bounded same-session recovery. Local tests: 30/30 passed; Python 3.10 and 3.12 CI passed at c8504b33788d4841a6259b4da9918db88672f9d4 before this checkpoint.
- Recovery trial failed acceptance: two reasoning interruptions, 6,003 streamed reasoning characters, 105.307 seconds, no completed edits. Infrastructure works, optimization not demonstrated.
- Native inference API rejects reasoning configuration for Ornith. A reversible chat-template override (set enable_thinking = false at top) produced zero recorded reasoning tokens in a direct chat smoke test.
- With this template, the server-mode KPI trial completed in 47.091 seconds, zero recorded reasoning tokens, zero tool calls, failed acceptance. The assistant asserted completion despite no file edits. Keep this modified-template profile separate from thinking-enabled trials.
- Direct OpenAI-compatible tool-call probe completed with 37 output tokens and zero reasoning tokens, but the choices payload was not captured. Tool-call success is unknown.

## Resume here
1. Start local inference API on loopback port 1235 with Ornith 1.5 9B MLX and the existing non-thinking template override. Keep original template backed up. Preserve model settings.
2. From the AgentRefine checkout, fetch and update the feature/bounded-recovery branch. Verify PR #6 CI and merge status before further changes.
3. Retrieve the choices array from the last direct tool-call probe, or repeat the probe below. Do not run another KPI trial yet.
4. Interpret tool_calls and finish_reason; if valid, test a small constrained direct tool loop against the synthetic fixture, without claiming optimization. If not, diagnose model selection versus parser behavior before changing the template again.
5. Keep raw sessions and tool outputs private. Publish only reviewed aggregate reports. Session-level abort works; inference-side cancellation remains unverified. Directory routing is not a sandbox.

## Direct probe
```sh
curl -s --max-time 60 http://127.0.0.1:1235/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"ornith-1.5-9b-mlx","messages":[{"role":"user","content":"Use the read_file tool to read index.html. Do not answer without calling the tool."}],"tools":[{"type":"function","function":{"name":"read_file","description":"Read the contents of a file","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}}],"tool_choice":"auto","max_tokens":256,"stream":false}' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps({k:d[k] for k in ("choices","usage","error") if k in d},indent=2))'
```

This only requests a tool call; it does not execute the tool. The eventual goal is improved verified completion under a controlled budget, not simply less reasoning.
