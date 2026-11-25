# shellcheck shell=bash

# script/hooks/test.pre.sh: Measure coverage on every full test run
#
# A bare `script/test`, which is what CI runs, gets coverage so that `fail_under` in pyproject.toml gates it. Runs
# narrowed by pytest arguments stay without it, because a partial suite always falls short.

if [[ ${#COVERAGE_ARGS[@]} -eq 0 && ${#PYTEST_ARGS[@]} -eq 0 ]]; then
    COVERAGE_ARGS+=("--cov=$INTEGRATION_PATH" "--cov-report=term-missing:skip-covered")
fi
