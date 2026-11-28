# Local coding with OpenCode

AgentRefine uses Inkling 2 Mini Q2_K_XL through Bionic's LM Studio API on `http://127.0.0.1:1235/v1`. OpenCode uses that instance for both coding and auxiliary requests.

Start the server on loopback port 1235. Unload any idle model you were using for coding before loading Inkling. If Inkling is already loaded with different settings, unload it first. The active settings are listed under `loaded_instances` at `GET /api/v1/models`.

```sh
curl --fail-with-body -sS http://127.0.0.1:1235/api/v1/models/load \
  -H 'Content-Type: application/json' \
  -d '{"model":"inkling-2-mini@q2_k_xl","context_length":24576,"parallel":1,"eval_batch_size":512,"flash_attention":true,"context_checkpoints":2,"echo_load_config":true}'
```

The profile uses one parallel prediction, a 512-token evaluation batch, and two context checkpoints. The 24,576-token context includes the OpenCode system prompt, tools, history, and generated output. Keep OpenCode's declared context aligned with the loaded instance. Use a fresh session for a new job and limit file reads and command output to relevant sections. The 12,288-token trial ran out of working context after collecting tool output. OpenCode's initial request alone used about 8,100 input tokens.

From the checkout, confirm the model is resident and launch OpenCode.

```sh
python3 local_model_ready.py --model inkling-2-mini@q2_k_xl && opencode
```

For a headless task, use OpenCode's native runner.

```sh
python3 local_model_ready.py --model inkling-2-mini@q2_k_xl &&
  opencode run --agent build 'Describe the exact change and test command here.'
```

Keep each job scoped to the relevant files and give it an objective acceptance check. Use a fresh session per job and process jobs sequentially on this Mac. Run the acceptance check independently before treating a job as complete. The readiness probe checks model residency only. Unattended scheduling and restart recovery still need to be verified.

If the probe reports an unreachable server, check the local listener and shell network permissions. If a sandbox prevents OpenCode from writing to its normal data directory, point `XDG_DATA_HOME`, `XDG_CACHE_HOME`, and `XDG_STATE_HOME` at writable directories for that session.
