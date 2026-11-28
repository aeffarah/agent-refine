#!/usr/bin/env python3
import argparse
import json
import sys
from urllib import request
from urllib.error import URLError

URL = "http://127.0.0.1:1235/api/v1/models"
TIMEOUT = 3
DEFAULT_MODEL = "ornith-1.5-9b-mlx@4bit"


def fail(message):
    print(f"local_model_ready: {message}", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Check whether a local model is loaded.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model key to check (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    try:
        with request.urlopen(URL, timeout=TIMEOUT) as response:
            body = response.read()
    except URLError as e:
        fail(f"unreachable server at {URL} ({e.reason})")
    except Exception as e:
        fail(f"unreachable server at {URL} ({e})")

    try:
        data = json.loads(body)
    except ValueError:
        fail("invalid response: not JSON")

    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        fail("invalid response: missing 'models' list")

    models = data["models"]
    for entry in models:
        if not isinstance(entry, dict) or "key" not in entry:
            continue
        if entry.get("key") == args.model:
            instances = entry.get("loaded_instances")
            if not isinstance(instances, list):
                fail("invalid response: missing or malformed loaded_instances")
            if len(instances) > 0:
                sys.exit(0)
            fail(f"installed but unloaded: {args.model}")

    fail(f"unknown model: {args.model}")


if __name__ == "__main__":
    main()
