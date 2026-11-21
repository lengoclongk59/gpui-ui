---
name: "cli-anything-gpui-ui"
description: "Use when testing, verifying, inspecting, clicking, hovering or screenshotting gpui-ui components in the running story gallery (GPUI) — after changing a component in crates/ui, adding one to the gallery, checking light/dark theme rendering, or asserting that a click, toggle or disabled state behaves correctly. Drives the real app through `cli-anything-gpui-ui` with JSON output and exit codes."
---

# cli-anything-gpui-ui

Drive and test the **gpui-ui** component gallery: the `story` application in
the gpui-ui repository, built on GPUI. The CLI launches the real app with its
automation server, then inspects, clicks, asserts and screenshots components.
Every click is a real GPUI mouse event through hit testing; every image is
rendered by GPUI itself (offscreen), never screen-captured.

## Prerequisites

- The gpui-ui repository with Rust/cargo, and `story` built:
  `cli-anything-gpui-ui app build` (or `cargo build -p story`; the first build
  takes several minutes). Rebuild after changing Rust code, then restart the app.
- A desktop session (the gallery opens a window).
- The CLI on PATH: `uv tool install --editable agent-harness` from the repo.

## Core loop for agents

```bash
cli-anything-gpui-ui --json app start            # once; records pid/port in the session
cli-anything-gpui-ui --json inspect state        # discover ids, values, bounds
cli-anything-gpui-ui --json act click primary    # act; returns the state after the change
cli-anything-gpui-ui --json check gallery clicks 1   # assert; exit 1 + failures on mismatch
cli-anything-gpui-ui --json screenshot element primary C:/abs/path/primary.png
cli-anything-gpui-ui --json app stop             # always stop when done
```

Put `--json` **before** the command group. Every command prints exactly one
JSON document. Exit code 0 means success; 1 means an error
(`{"error": .., "type": ..}`) or a failed check
(`{"passed": false, "failures": [..]}`).

## Command groups

| Group | Commands | Notes |
| --- | --- | --- |
| `app` | `build [--release]`, `start [--port N] [--exe PATH] [--replace]`, `stop [--force]`, `status`, `ping` | `start` refuses if one is running; use `--replace` or `stop`. `stop` is safe when nothing runs. |
| `inspect` | `state`, `elements [--kind button\|switch]`, `element ID` | read-only |
| `act` | `click ID [--times N]`, `hover ID` | returns `state` after the frames are painted |
| `theme` | `get`, `set light\|dark`, `toggle` | |
| `check` | `element ID [--kind K] [--label TEXT] [--disabled/--enabled] [--checked/--unchecked]`, `gallery KEY VALUE`, `theme MODE` | `VALUE` is JSON: `3`, `true`, `"text"` |
| `screenshot` | `window OUT`, `element ID OUT` | PNG in device pixels; relative paths resolve against your cwd |
| `preview` | `recipes`, `capture [--recipe window\|elements] [--force] [--root DIR]`, `latest [--recipe R]` | `preview-bundle/v1`; reused while state is unchanged |
| `repl` | | default with no arguments; for humans |

Global options: `--json`, `--session PATH` (default
`~/.cli-anything-gpui-ui/session.json`, or `$CLI_ANYTHING_GPUI_UI_SESSION`).
Use a separate `--session` per parallel gallery.

## The gallery's test ids

| id | kind | behavior |
| --- | --- | --- |
| `toggle-theme` | button | switches light/dark; label is "Dark mode" / "Light mode" |
| `primary` | button | increments `gallery.clicks` |
| `secondary`, `outline`, `ghost`, `danger` | button | variants, no action |
| `disabled` | button | disabled; clicks must not change `clicks` |
| `small`, `medium`, `large` | button | sizes, no action |
| `notifications` | switch | toggles `gallery.notifications`; `checked` follows |
| `switch-disabled` | switch | disabled, always checked |

`inspect state` is the source of truth: new components appear there once the
gallery wraps them in `probe(...)` (see `docs/AUTOMATION.md`).

## State shape

```json
{
  "theme": "light",
  "gallery": {"clicks": 0, "notifications": true},
  "elements": [
    {"id": "primary", "kind": "button", "label": "Primary", "disabled": false,
     "checked": null, "bounds": {"x": 57.0, "y": 193.0, "width": 81.0, "height": 36.0}}
  ]
}
```

## Examples

Verify a behavior change:

```bash
cli-anything-gpui-ui --json app start
cli-anything-gpui-ui --json act click notifications
cli-anything-gpui-ui --json check element notifications --unchecked
cli-anything-gpui-ui --json act click disabled
cli-anything-gpui-ui --json check gallery clicks 0
cli-anything-gpui-ui --json app stop
```

Compare both themes visually:

```bash
cli-anything-gpui-ui --json screenshot window C:/tmp/light.png
cli-anything-gpui-ui --json theme set dark
cli-anything-gpui-ui --json screenshot window C:/tmp/dark.png
```

Then open the PNGs (an agent can read them as images) to judge the result.

Publish a preview bundle for a human reviewer (producer), then inspect it with
the read-only consumer:

```bash
cli-anything-gpui-ui --json preview capture --recipe elements
cli-hub previews inspect <_bundle_dir from the JSON>
```

## Agent guidance

- Start with `app status`; if `running` is false, `app start`. Stop the app at
  the end of the task.
- After editing Rust code: `app build`, then `app start --replace`; an old
  binary otherwise keeps running.
- Read ids from `inspect state` instead of guessing; an unknown id fails with
  the list of known ids.
- Prefer `check ...` over reading JSON yourself: the exit code is the verdict
  and `failures` explains the mismatch.
- Use absolute screenshot paths. Look at the PNG when appearance matters;
  checks only cover state.
- Hover state persists until the pointer moves: `act hover` another element
  before screenshotting an element at rest.
- `app start` failures include the tail of the app log; the full log path is
  in `app status`.

## Version

1.0.0
