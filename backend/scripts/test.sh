#!/usr/bin/env bash

set -e
set -x

uv run python -m coverage run -m pytest tests/
uv run python -m coverage report --fail-under=60
uv run python -m coverage html --title "${@-coverage}"
