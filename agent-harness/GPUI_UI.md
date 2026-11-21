# gpui-ui: Agent Harness SOP

## Phase 1: Codebase analysis

**Software.** `gpui-ui` is a Rust workspace of web-inspired UI components for
GPUI (`crates/ui`) plus a gallery application, `story` (`crates/story`), that
renders every component in a real window.

**Backend engine.** GPUI (`gpui-pre =0.3.12`), a GPU-accelerated retained-mode
UI framework. Rendering uses DirectX on Windows, Metal on macOS and wgpu on
Linux. There is no project file: the "document" is the live component tree of
the running gallery.

**Native scripting interface.** `story --automation [--port N]` starts a
loopback JSON Lines server (`crates/story/src/automation.rs`, protocol in
`docs/AUTOMATION.md`). It is the only backend this harness talks to:

| GUI action | Backend request |
| --- | --- |
| look at the window | `{"cmd":"state"}` (theme, gallery values, every element with id, kind, label, disabled, checked, bounds) |
| click a button or switch | `{"cmd":"click","id":..}` (real mouse move/down/up through GPUI hit testing) |
| point at a component | `{"cmd":"hover","id":..}` |
| press "Dark mode" | `{"cmd":"set_theme","mode":"dark"}` |
| look at pixels | `{"cmd":"screenshot","path":..,"id":..}` (GPUI `render_to_image`, offscreen, device pixels) |
| close the window | `{"cmd":"quit"}` |

Changing commands reply only after the next frames are painted, so the returned
state already reflects the change.

**Data model.** The state object above. Elements are registered by the gallery
through `probe(id, ProbeInfo, element)`; component crates hold no automation
code. Test ids are listed in `docs/AUTOMATION.md`.

**Existing CLI tools.** `cargo build -p story` builds the backend;
`scripts/automation_smoke.py` is a stdlib smoke test of the protocol.

**Undo system.** None. The gallery state is a few in-memory values.

## Phase 2: CLI design

**Interaction model.** Both one-shot subcommands and a REPL (the default when
no subcommand is given).

**State model.** The persistent state is the *app session*: which `story`
process is running and on which port. It is stored in a JSON session file
(default `~/.cli-anything-gpui-ui/session.json`, override with `--session` or
`CLI_ANYTHING_GPUI_UI_SESSION`) written with exclusive locking. Every other
command reads it to find the app. There is no project file to save, so the
auto-save / `--dry-run` pattern does not apply (it is a service wrapper).

**Command groups.**

| Group | Commands | Purpose |
| --- | --- | --- |
| `app` | `build`, `start`, `stop`, `status`, `ping` | backend lifecycle |
| `inspect` | `state`, `elements`, `element` | read-only introspection |
| `act` | `click`, `hover` | pointer input |
| `theme` | `get`, `set`, `toggle` | light/dark |
| `check` | `element`, `gallery`, `theme` | assertions for automated tests; exit code 1 on failure |
| `screenshot` | `window`, `element` | PNG via the real renderer |
| `preview` | `recipes`, `capture`, `latest` | `preview-bundle/v1` bundles |
| `repl` | | interactive shell |

**Output.** Human-readable by default; `--json` prints exactly one JSON
document per command. Errors print `{"error": .., "type": ..}` and exit 1.

**Truthfulness.** Screenshots and previews come from GPUI's own offscreen
renderer through the backend, never from screen capture.
