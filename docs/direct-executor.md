# Direct staged executor (experimental policy v1)

The direct tool-call probe with Ornith 1.5 9B MLX and the non-thinking Jinja override returned one valid read_file call, finish_reason tool_calls, 288 prompt tokens, 37 completion tokens and zero reasoning tokens. No actual tool was executed by that probe. This motivates testing a narrow executor without OpenCode.

Run with Python 3.10+ on POSIX, and the local OpenAI-compatible API on loopback port 1235. Keep the same model/template settings and use a distinct profile.

```sh
python3 direct_executor.py kpi-v1 --profile m4-ornith-direct-nothink-01 \
  --model ornith-1.5-9b-mlx
```

The task text and fixture are unchanged. The orchestration policy explicitly stages a read, then an edit; one tool is advertised per request with tool_choice auto. At most two read attempts and three edit attempts are allowed, with 1024 completion tokens per request. Each call receives a fresh prompt; file data is quoted, not instructions. The model supplies the actual content and exact replacement strings. No expected solution is supplied by the executor. Independent acceptance is evaluated after each executed edit and failed check names can guide retries. A model's plain-text completion claim cannot pass the task.

Tools are restricted to the benchmark's specific readable and writable basenames; no shell, code execution, arbitrary directory listing, external network access, or model-supplied paths outside the allowlist. File access uses a directory descriptor and refuses symlinks, hardlinks and oversized/nonregular files. Use only fresh synthetic workspaces, not a general security sandbox. A separately modified workspace is outside the threat model. The HTTP timeout is a socket timeout rather than a guaranteed end-to-end inference cancellation; the executor checks the monotonic task deadline before executing a returned call. Backend cancellation is not verified. Do not run concurrent experiments.

Reports contain aggregate token counts and fixed result labels, not tool arguments or responses. Completion tokens include reasoning if present; absent usage fields remain null. No OpenCode session export exists in this mode. The runner creates fresh workspaces and stores reports under gitignored private/direct. Choose another --trial on reruns.

This changes the tool interface, context size, generation cap and orchestration together. Compare as an exploratory system-level intervention, not a controlled claim about reasoning suppression alone. Next steps: test the same tasks repeatedly, document failure modes, and evaluate unseen tasks before claiming general improvement.
