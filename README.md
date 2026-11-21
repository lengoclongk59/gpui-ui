# gpui-ui

Web-inspired UI components for [GPUI](https://www.gpui.rs), the GPU-accelerated
UI framework behind the Zed editor. The layout follows
[gpui-kit](https://github.com/longbridge/gpui-kit): a component library crate
plus a gallery application for developing components in a real window.

```text
crates/
├── ui      gpui-ui: theme tokens and components (Button, Switch)
└── story   gallery app: one section per component, optional automation server
```

## Website

`site/` holds the project page. `.github/workflows/pages.yml` publishes it to
GitHub Pages together with the `gpui-ui` API docs (`cargo doc`, served under
`/api/`) on every push to `main` that touches `crates/ui`, `site` or the
manifests. The gallery screenshots in `site/assets/` come from
`cli-anything-gpui-ui screenshot window`; regenerate them when a component
changes its look.

## Run the gallery

```sh
cargo run            # `story` is the default member
cargo test --workspace
```

The first build compiles GPUI and takes several minutes.

GPUI comes from the `gpui-pre-*` snapshot crates on crates.io. Every snapshot
may change the API, so `Cargo.toml` pins an exact version (`=0.3.12`, the same
snapshot gpui-kit 0.10 uses). Bump all `gpui-pre-*` crates together.

## Automated testing

`cargo run -p story -- --automation` also starts a loopback JSON Lines server
that clicks, hovers and inspects components through GPUI's real input path and
renders screenshots offscreen. The protocol and test ids are in
[`docs/AUTOMATION.md`](docs/AUTOMATION.md); the end-to-end check is:

```sh
cargo build -p story
py -3 -I scripts/automation_smoke.py
```

### Agent CLI (`cli-anything-gpui-ui`)

`agent-harness/` is a [CLI-Anything](https://github.com/HKUDS/CLI-Anything)
harness over that server: one command per action, `--json` output and exit
codes, so AI agents (Claude Code) and scripts can test components.

```sh
uv tool install --editable agent-harness     # once; puts the command on PATH
cli-anything-gpui-ui app start
cli-anything-gpui-ui act click notifications
cli-anything-gpui-ui check element notifications --unchecked
cli-anything-gpui-ui screenshot element primary out/primary.png
cli-anything-gpui-ui app stop
```

Claude Code picks up the `cli-anything-gpui-ui` skill from
`.claude/skills/` in this repository. The canonical skill is
`skills/cli-anything-gpui-ui/SKILL.md`, with a packaged copy in
`agent-harness/cli_anything/gpui_ui/skills/`; keep the three in sync. Usage,
tests and design notes: `agent-harness/cli_anything/gpui_ui/README.md`,
`agent-harness/cli_anything/gpui_ui/tests/TEST.md`, `agent-harness/GPUI_UI.md`.

## Porting a web component

Only port components that GPUI, gpui-kit and the other GPUI component
libraries do not already provide. See `.claude/rules/new-components-only.md`
for the check, the list of reference libraries and the covered components.

1. **Read the source design.** Note its variants, sizes, states (hover, active,
   focus, disabled) and the CSS variables it uses.
2. **Map CSS variables to theme tokens.** Add missing tokens to
   `crates/ui/src/theme.rs` (both `light()` and `dark()`); components never
   hard-code colors.
3. **Pick the component shape:**
   - *Stateless / controlled* (button, badge, switch, checkbox): a struct with a
     builder API, `#[derive(IntoElement)]` and `impl RenderOnce`. The owner
     keeps the value and passes it back each render, like a controlled React
     input. See `button.rs` and `switch.rs`.
   - *Stateful* (text input, select, date picker): an `Entity<State>` that
     implements `Render`, created with `cx.new(..)` and stored by the owner. It
     emits events with `cx.emit(..)` (`impl EventEmitter<Event>`).
4. **Translate CSS to GPUI styles.** GPUI's `Styled` methods follow Tailwind
   names: `flex`, `items_center`, `gap_2`, `px_4`, `rounded_md`, `border_1`,
   `bg(..)`, `text_color(..)`. `:hover` becomes `.hover(|s| ..)`, `:active`
   becomes `.active(|s| ..)`; both need an element id (`.id(..)`).
5. **Add a gallery section** in `crates/story/src/gallery.rs` showing every
   variant, size and state. Wrap each element in `probe(id, ProbeInfo, ..)` so
   the automation server and `cli-anything-gpui-ui` can find it.
6. **Register the module** in `crates/ui/src/lib.rs`.

Reference implementations: gpui-kit's `crates/component/src/` (styled) and
`crates/base/src/` (behavior only).
