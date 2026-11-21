# cli-anything-gpui-ui

An agent-native command-line interface for the **gpui-ui** component gallery.
It starts the real `story` application (GPUI) with its automation server, then
lets an agent or a script inspect, click, assert and screenshot every
component, with JSON output for every command.

## Requirements

- **The gpui-ui repository and Rust (cargo).** The real software is the `story`
  gallery built from that repository; the CLI is useless without it.
- A desktop session (the gallery opens a real window).
- Python 3.10+.

Build the gallery once (the first build compiles GPUI and takes several
minutes):

```sh
cargo build -p story            # in the gpui-ui repository
# or, after installing the CLI:
cli-anything-gpui-ui app build
```

The CLI finds `story` in this order: `app start --exe PATH`,
`$GPUI_UI_STORY_EXE`, the repository's `target/debug` then `target/release`,
then `PATH`. It finds the repository from its own location or
`$GPUI_UI_REPO`.

## Install

```sh
cd agent-harness
uv tool install --editable .      # puts cli-anything-gpui-ui on PATH
# or: pip install -e .
cli-anything-gpui-ui --help
```

## Usage

```sh
cli-anything-gpui-ui app start                    # launch the gallery, record the session
cli-anything-gpui-ui inspect elements --kind switch
cli-anything-gpui-ui act click primary --times 3
cli-anything-gpui-ui check gallery clicks 3       # exit 0 on pass, 1 on failure
cli-anything-gpui-ui check element notifications --checked --enabled
cli-anything-gpui-ui theme set dark
cli-anything-gpui-ui screenshot element primary out/primary.png
cli-anything-gpui-ui app stop
```

Add `--json` (before the command group) for machine-readable output:

```sh
cli-anything-gpui-ui --json act click notifications
```

Running `cli-anything-gpui-ui` with no arguments opens the REPL.

### Command groups

| Group | Commands |
| --- | --- |
| `app` | `build [--release]`, `start [--port] [--exe] [--replace]`, `stop [--force]`, `status`, `ping` |
| `inspect` | `state`, `elements [--kind]`, `element ID` |
| `act` | `click ID [--times N]`, `hover ID` |
| `theme` | `get`, `set light\|dark`, `toggle` |
| `check` | `element ID [--kind] [--label] [--disabled/--enabled] [--checked/--unchecked]`, `gallery KEY VALUE`, `theme MODE` |
| `screenshot` | `window OUT`, `element ID OUT` |
| `preview` | `recipes`, `capture [--recipe window\|elements] [--force] [--root]`, `latest` |
| `repl` | interactive shell (default) |

Test ids: `toggle-theme`, `primary`, `secondary`, `outline`, `ghost`,
`danger`, `disabled`, `small`, `medium`, `large`, `notifications`,
`switch-disabled`. Gallery values: `clicks`, `notifications`.

### Session

The running app (pid, port, exe, log) is stored in
`~/.cli-anything-gpui-ui/session.json`. Use `--session PATH` or
`$CLI_ANYTHING_GPUI_UI_SESSION` to run several galleries side by side. There is
no project file to save, so there is no auto-save or `--dry-run`.

### Previews

Producer (this CLI) and consumer (`cli-hub`) are separate:

```sh
cli-anything-gpui-ui --json preview capture --recipe elements   # publish a bundle
cli-hub previews inspect <_bundle_dir from the JSON>             # inspect it
```

Recipes: `window` (one hero PNG) and `elements` (hero plus one PNG per
element). Static capture only; no diff or live mode. Bundles follow
`preview-bundle/v1` and are reused while the gallery state is unchanged.

**Truthfulness:** every image is rendered by GPUI itself (`render_to_image`,
offscreen, device pixels) through the automation server; nothing is
screen-captured or drawn in Python. Pointer commands are real GPUI mouse events
through hit testing, so disabled components ignore them exactly as for a user.

## Tests

```sh
py -3 -m pytest cli_anything/gpui_ui/tests/test_core.py -v        # unit, no window
py -3 -m pytest cli_anything/gpui_ui/tests/ -v -s                 # + E2E on the real app
CLI_ANYTHING_FORCE_INSTALLED=1 py -3 -m pytest cli_anything/gpui_ui/tests/ -v -s
```

See `tests/TEST.md` for the plan and the latest results.
