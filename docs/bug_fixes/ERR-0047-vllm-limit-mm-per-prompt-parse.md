# ERR-0047: vLLM JSON Argument Parse Error in Docker Compose

## Symptoms
The `vision-vllm` container fails to start and immediately exits with:
`api_server.py: error: argument --limit-mm-per-prompt: Value {"image": cannot be converted to <function loads at ...>`

## Investigation Notes
- The error indicates that the `--limit-mm-per-prompt '{"image": 4}'` argument became truncated at the space character, so the python script received `{"image":` instead of the full JSON string.
- The `vision-vllm` service in `docker-compose.yml` uses a custom entrypoint string:
  `/bin/bash -c "pip install -q num2words && exec python3 -m vllm.entrypoints.openai.api_server $$@" --`
- Because the `$$@` variable was unquoted inside the `-c` script string, `bash` applied word splitting to all positional parameters. The parameter `'{"image": 4}'` was passed to bash as one word, but bash split it into two (`{"image":` and `4}`) when substituting unquoted `$@`.

## Hypotheses Considered
1. **Docker Compose string parsing stripped the single quotes.** It did, but that just left the spaces exposed to the entrypoint script.
2. **Bash word splitting on unquoted `$@` caused the JSON string to split.** Confirmed. The entrypoint script executes unquoted `$$@`, causing any arguments with spaces to break.

## Experiments Tried
- Modified the entrypoint to quote `$$@` as `\"$$@\"`. This executes as `"$@"` in bash, preserving the integrity of arguments containing spaces.

## Final Fix
Added quotes to `$$@` in the `docker-compose.yml` `vision-vllm` entrypoint definition:
```yaml
    entrypoint: >
      /bin/bash -c "pip install -q num2words && exec python3 -m vllm.entrypoints.openai.api_server \"$$@\"" --
```

## Verification
- Restart the `vision-vllm` container.
- Check logs to confirm it starts without the argparse error.
- Verified vLLM engine initializes correctly.

## Status
resolved
