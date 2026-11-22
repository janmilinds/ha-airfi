# Manual steps

What an integration repository has to do by hand because template sync cannot do it, newest first. Each step has an id
for the `skipped` list in `.agents/blueprint-update.json`, the date it entered the blueprint, and a check that passes
once it is done. Run the check from the repository root.

## `test-timeout` — 2026-11-21

**Check:** `grep -q '^timeout = ' pyproject.toml && grep -q -- '--picked' .vscode/tasks.json`

Like Home Assistant Core, every test now fails after 10 seconds instead of hanging a whole run, and VS Code gets tasks
for the changed tests and for snapshot updates. Neither file is synced:

1. Add `timeout = 10` under `[tool.pytest.ini_options]` in `pyproject.toml` (`pytest-timeout` is installed already).
2. Copy the blueprint's `Run Changed Tests` and `Update Test Snapshots` tasks into `.vscode/tasks.json`.

## `ha-environments` — 2026-11-21

**Check:** `grep -q 'script/ha-env' .vscode/tasks.json`

The sync brings `script/ha-env`, the environment-aware `script/setup/bootstrap` and `script/develop`, and the prompt
hook; `minimum` stays the default and `latest` or `beta` are added on demand
([`CUSTOMIZATION.md`](../../../../docs/development/CUSTOMIZATION.md#testing-against-a-newer-home-assistant)).

1. Run `script/setup/bootstrap` once, then `bash .devcontainer/setup-shell.sh`. The first moves the venv to one
   directory per Home Assistant version inside the same volume, the second brings the `ha-env` alias and the prompt
   hook into `.bashrc` and `.zshrc` — no container rebuild.
2. Copy the blueprint's `Run Home Assistant (Environment)`, `Switch`, `Add` and `Refresh Home Assistant
Environment(s)` and `Pin Home Assistant Version (custom Environment)` tasks and the `inputs` block into
   `.vscode/tasks.json`, which the sync leaves alone.

## `pytest-homeassistant` — 2026-11-21

**Check:** `! grep -rq pytest_homeassistant_custom_component tests/ && script/ha-version-sync >/dev/null 2>&1`

The sync replaces `pytest-homeassistant-custom-component` in `requirements_test.txt` with Home Assistant's own
`pytest-homeassistant`, which starts at 2026.11. `tests/` and `hacs.json` are not synced, so until this is done
`script/test` fails on the imports and `script/ha-version-sync` on the release train:

1. Raise `homeassistant` in `hacs.json` to `2026.11.0`. Users on an older Home Assistant get no further updates, so
   name the new minimum in your changelog; it is not a breaking change on its own
   ([`ha-breaking-changes`](../../ha-breaking-changes/SKILL.md#1-recognise-it)).
2. Replace `pytest_homeassistant_custom_component` with `pytest_homeassistant` in every import under `tests/`.
3. Delete the autouse `auto_enable_custom_integrations` fixture from `tests/conftest.py` — the new `hass` fixture
   loads custom integrations itself.
4. Move recorded payloads to `tests/fixtures/`: `load_fixture()` now resolves there, no longer next to the test file.
5. Add `-p no:respx` to `addopts` under `[tool.pytest.ini_options]` in `pyproject.toml`. Some Home Assistant releases
   otherwise abort the test run with "httpx was already imported".
6. Run `script/setup/bootstrap`, which rebuilds the virtual environment for the new Home Assistant version, then
   `script/test`.

To stay below 2026.11 instead, record this step as skipped and keep the old pin as
[`CUSTOMIZATION.md`](../../../../docs/development/CUSTOMIZATION.md#staying-on-an-older-home-assistant-version)
describes — including the 2026.11 APIs from the synced skills that such a repository must not adopt.

## `upstream-rename` — 2026-11-02

**Check:** `grep -q 'jpawlowski/ha-integration-blueprint' .github/workflows/template-sync.yml`

The blueprint moved from `jpawlowski/hacs.integration_blueprint` to `jpawlowski/ha-integration-blueprint`. GitHub
redirects the old name, so the sync keeps working, but only for as long as nobody claims that name again. Replace the
old name in `source_repo_path` of this repository's `template-sync.yml`; the workflow is excluded from the sync.

## `brand-images` — 2026-11-02

**Check:** `ls custom_components/*/brand/icon.png`

Replace `custom_components/<domain>/brand/` with the product's images — what is required:
[`ha-marketplace`](../../ha-marketplace/SKILL.md#3-brand-images). `custom_components/` is never synced, so only new repositories get the blueprint's placeholder. Once the file exists,
the HACS validation in `validate.yml` stops skipping its `brands` check.

## `root-gitignore` — 2026-11-02

**Check:** `grep -qE '^![^/]+/$' custom_components/.gitignore && ! grep -qxF '.gitignore' .templatesyncignore`

The root `.gitignore` is now template-synced and no longer generated from toptal, whose unanchored patterns such as
`image`, `tts` and `lib` hid integration platforms of that name. Opt in in this order: first create
`custom_components/.gitignore` containing `!<domain>/`, then delete the `.gitignore` line from `.templatesyncignore`.
The other way round, Git silently ignores every new file in the integration, and already tracked files hide that.
Move anything this repository added to its root `.gitignore` into `custom_components/.gitignore` or
`.git/info/exclude` first — the next sync overwrites the root file.

## `squash-pull-requests` — 2026-11-01

**Check:** `gh api "repos/{owner}/{repo}" --jq '.allow_merge_commit == false' | grep -q true`

The blueprint's `main` ruleset now takes every change through a pull request, admins included — squash by default,
rebase for a pull request whose commits each pass the commit rules — and a new workflow `pr-title.yml` checks the
title, which becomes the squash commit, and reports whether each commit would survive a rebase.
Ask the developer whether they want that: if so, copy the workflow (`script/blueprint-update` lists it) and run
`script/setup/github`; if not, follow _Want it less strict?_ in `docs/development/REPOSITORY_SETUP.md` of the
blueprint and record the step as skipped.

## `lint-and-test-check` — 2026-11-01

**Check:** `! gh api "repos/{owner}/{repo}/rules/branches/main" --jq '.[].parameters.required_status_checks[]?.context' 2>/dev/null | grep -qx Ruff`

The lint workflow's job is now called _Lint and test_ and also runs `script/type-check` and `script/test`. A ruleset
or branch protection that still requires the old `Ruff` check waits for it forever and blocks every pull request:
replace it with `Lint and test` — `script/setup/github` does that for the `main` ruleset it manages.

## `repository-settings` — 2026-11-01

**Check:** `gh api "repos/{owner}/{repo}/rulesets" --jq 'map(.name) | index("main") != null' | grep -q true`

Run `script/setup/github --dry-run`, show the developer what it would change, and run it without the flag once they
agree. It turns on Dependabot alerts and, on a public repository, secret scanning and push protection, and imports the
`main` ruleset; `docs/development/REPOSITORY_SETUP.md` in the blueprint explains each setting and what it costs on a
private repository. The new workflows `codeql.yml` and `secret-history-scan.yml` arrive through the sync only with a
`TEMPLATE_SYNC_TARGET_PAT`; otherwise `script/blueprint-update` lists them as new files to copy.

## `blueprint-identity` — 2026-11-01

**Check:** `grep -q '"identity"' .agents/blueprint-update.json`

Record this repository's names in `.agents/blueprint-update.json`, as `initialize.sh` now does for a new one:
`"identity": {"domain": …, "title": …, "prefix": …, "owner": …, "repository": …, "author": …}` beside `reviewed`.
Without it `script/blueprint-update` infers them from the manifest, the coordinator class and `LICENSE`, and a renamed
class lets the blueprint's own class prefix through into the diff. The values are what `initialize.sh` asked for:
the domain, the title, the class prefix, the GitHub owner and repository name, and the author.

## `template-sync-guard` — 2026-11-01

**Check:** `grep -q template-sync-guard .github/workflows/template-sync.yml`

Copy the step _Keep this repository's newer versions_ from the blueprint's `template-sync.yml` to the end of this
repository's; `script/blueprint-update` shows it in context. Without it, a sync lowers every version this repository's
Dependabot or Renovate raised further than the blueprint has. The script it calls, `script/template-sync-guard`,
already arrives through the sync — only the workflow is excluded.

## `mise-project-tools` — 2026-11-01

**Check:** `grep -qxF '.config/mise/conf.d/project.toml' .templatesyncignore`

Add `.config/mise/conf.d/project.toml` to `.templatesyncignore`, in the section for project-owned files. It is where
this repository's own command-line tools go; `mise.toml` holds the blueprint's and is overwritten by the sync.
Create the file from the blueprint's copy if the project wants a tool of its own now.

## `agents-md-outside-container` — 2026-11-01

**Check:** `grep -q '^## Outside the dev container' AGENTS.md && grep -q 'never wait for an answer' AGENTS.md`

Carry over three changes to `AGENTS.md`: the CLI tools paragraph now names `mise.toml` instead of the dev container,
_Commands you run yourself never wait for an answer_ joined the validation section, and _Outside the dev container_
is new. They tell agents how the repository works in a cloud session or on a machine without the dev container.
`script/blueprint-update` shows all three as hunks.
