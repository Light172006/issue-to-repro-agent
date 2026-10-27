# Issue-to-Repro Agent

A Python tool under development that aims to turn GitHub bug reports into verified, minimal failing tests, or explain why a bug could not be reproduced.

Built for the Meta Global AI Hackathon, indie track, Build for Your World.

## Status

Step 0: project setup. No reproduction or sandbox functionality has been implemented yet.

## Development setup

Requires Python 3.11 and Docker. In a checkout:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
```

An empty pytest suite reports `no tests ran` and exits with code 5. Verify Docker separately with `docker run hello-world`.
