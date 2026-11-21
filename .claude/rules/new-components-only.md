---
paths:
  - "crates/**"
  - "README.md"
---

# New Components Only: Never Re-Port What a GPUI Library Already Ships

**This crate only adds components that no existing GPUI library provides.**
Porting or rewriting a component that already exists in GPUI itself, in
[gpui-kit](https://github.com/longbridge/gpui-kit) or in another maintained
GPUI component library (listed below) is forbidden, even with a different
look, a different API, or "just a simpler version".

## Why

gpui-kit is the reference library for this workspace (same `gpui-pre` pin).
Apps that use `gpui-ui` can depend on gpui-kit, or on a specialized GPUI
crate, for everything those already cover. A second Button, Dialog or Select
only duplicates code, splits bug fixes across two copies and costs
maintenance. The value of this crate is in the components that are missing.

## The references, in order

### Tier 1: blocking (exists here means never port)

| Source | Where to look |
|---|---|
| GPUI (`gpui-pre =0.3.12`) | `~/.cargo/registry/src/*/gpui-pre-0.3.12/src/elements/`: `div`, `img`, `svg`, `canvas`, `list`, `uniform_list`, `anchored`, `deferred`, `surface`, `text`, `animation`, `image_cache`, `container_query` |
| [gpui-kit](https://github.com/longbridge/gpui-kit) (formerly `gpui-component`; the old URL redirects) | `crates/component/src/`, `crates/base/src/` (headless behavior), plus `crates/webview`, `crates/fps` |

### Tier 2: other GPUI component libraries (exists here means ask first)

If a component is missing from Tier 1 but exists in one of these, do **not**
port it by default. Tell the user where it lives and ask whether to port it
anyway or depend on that library.

| Library | Focus | License | Activity (2026-11) |
|---|---|---|---|
| [Zed `crates/ui`](https://github.com/zed-industries/zed/tree/main/crates/ui/src/components) | Zed's own components (callout, banner, chip, facepile, disclosure, keybinding hint, indent guides, split button, sticky items) | **GPL-3.0** | active |
| [Ely GPUI Components](https://github.com/ELY-Open-Source/Ely-GPUI-Components) | very large set: chat, code, data, charts, editors, pickers, WASM gallery | MIT | active |
| [adabraka-ui](https://github.com/Augani/adabraka-ui) | broad set plus animations and effects (confetti, marquee, number ticker, aurora, ripple, QR code, audio player, image viewer, crop) | MIT | stale since 2026-02 |
| [Bezel](https://github.com/crabtalk/bezel) | SwiftUI-like library; diagrams, mindmap, minimap, terminal graphics | MIT | active |
| [guise](https://github.com/wess/guise) | Mantine-inspired: spotlight, tour, transfer, timeline, dropzone, AI chat parts | MIT | active |
| [Base GPUI](https://github.com/LukeTandjung/base-gpui) | headless port of Base UI (meter, fieldset, navigation menu, drawer) | MIT | active |
| [gpuicn](https://github.com/karyalabs/gpuicn) | shadcn-styled, copy-source CLI; emoji picker, lightbox, commit graph | MIT | active |
| [HIG for GPUI](https://github.com/lavs9/hig-gpui) | Apple Human Interface Guidelines components | none | active, tiny |

Specialized widget crates (a component in their domain is already covered):

| Crate | Covers | License |
|---|---|---|
| [gpui-kit-grid](https://github.com/GigLaboCom/gpui-kit-grid) | live data grid (keyed updates, sort, filter, group, tree) | see repo |
| [gpui-flow](https://github.com/pacifio/gpui-flow), [ferrum-flow](https://github.com/tu6ge/ferrum-flow) | node editors in the style of React Flow | MIT, Apache-2.0 |
| [gpui-maps](https://github.com/swatmobility/gpui-maps) | vector maps, globe, overlays | Apache-2.0 |
| [gpui-video-player](https://github.com/cijiugechu/gpui-video-player) | video player | MIT |
| [zorite](https://github.com/packetThrower/zorite) `crates/gpui-pdf`, `gpui-whiteboard`, `ratex-gpui` | PDF viewer, whiteboard canvas, LaTeX renderer and formula editor | **GPL-3.0** |
| [sotf](https://github.com/pierreaubert/sotf) `gpui-d3rs`, `gpui-px`; [plotters-gpui](https://github.com/JakkuSakura/plotters-gpui) | plotting | see repo |
| [gpui-symbols](https://github.com/AprilNEA/gpui-symbols) | SF Symbols icons | see repo |
| [gpui-router](https://github.com/justjavac/gpui-router), [gpui-nav](https://github.com/benodiwal/gpui-nav) | routing, navigation stacks | see repo |
| [gpui-form](https://github.com/stayhydated/gpui-form), [gpui-storybook](https://github.com/stayhydated/gpui-storybook) | form derive macro, story gallery | see repo |

### Not component references

These are GPUI forks or app frameworks, not component sources:
[gpui-ce](https://github.com/gpui-ce/gpui-ce), [gpui-fast](https://github.com/longbridge/gpui-fast),
[GPUIX](https://github.com/remorses/gpuix), [Zopra](https://github.com/ppmpreetham/zopra),
[gpui-hooks](https://github.com/leset0ng/gpui-hooks), [gpui-tea](https://github.com/inkwadra/gpui-tea),
[gpui-mobile](https://github.com/itsbalamurali/gpui-mobile). Only count a fork
if it adds an element to GPUI's `src/elements/`.

To find libraries newer than this list, read the "Libraries" section of
[awesome-gpui](https://github.com/zed-industries/awesome-gpui) and run
`gh search repos "gpui component" --sort stars`. Add a library to Tier 2 when
it is maintained and has more than a toy set of components.

## Before writing a component

1. **Check Tier 1** on `main`, not just the inventory below. List the folders
   including subfolders
   (`gh api repos/longbridge/gpui-kit/contents/crates/component/src/<dir>`).
   Search by the web name *and* by its synonyms: "toast" is
   `notification.rs`, "drawer" is `sheet.rs`, "context menu" is in `menu/`,
   "segmented control" is `toggle_group.rs`, "date range" is in `time/`.
2. **Check Tier 2.** List each repo's tree and grep for the name and its
   synonyms:
   `gh api "repos/<owner>/<repo>/git/trees/<branch>?recursive=1" --jq '.tree[].path' | grep -i <name>`.
3. **Found in Tier 1:** do not port it. Tell the user which file provides it
   and stop. Do not create a "variant" of it in this crate.
4. **Found only in Tier 2:** stop and ask the user, naming the library, the
   file and its license.
5. **Only partly exists** (for example, gpui-kit has `slider.rs` but no
   range slider with two thumbs): port only the missing part as a new
   component with its own name, and reuse gpui-kit's pieces instead of
   copying them. Say in the module doc what the existing libraries lack.
6. **Missing everywhere:** allowed. Follow the porting steps in `README.md`.

The user can override this for one specific component by asking for it
explicitly ("port gpui-kit's X here anyway"). A general "port some components"
request is **not** an override.

## Licenses when reading other libraries

- **GPL-3.0 (Zed `crates/ui`, zorite):** read them for ideas only. Never copy
  or closely translate their code into this crate.
- **No license (HIG for GPUI):** same as GPL. Read only.
- **MIT / Apache-2.0:** code may be adapted. Keep the copyright notice and
  name the source file in the module doc.

## Already covered in Tier 1 (gpui-kit `main`, 2026-11-20, v0.10.0)

`crates/component/src/`:

- **Buttons:** button, button group, icon button, dropdown button, toggle,
  toggle group, link, kbd, clipboard (copy button)
- **Inputs and forms:** input, textarea, number input, OTP input, search, input
  group, checkbox, radio, radio group, switch, slider, select, combobox, color
  picker, rating, form/field, settings page
- **Date and time:** calendar, date picker, time field
- **Overlays:** dialog, alert dialog, sheet (drawer), popover, hover card,
  tooltip, notification (toast), context menu, dropdown menu, app menu bar,
  native menu, command palette
- **Navigation and layout:** tabs, tab bar, sidebar, breadcrumb, pagination,
  stepper, accordion, collapsible, resizable panels, dock, grid layout, group
  box, separator, title bar, status bar, toolbar, window border, scrollable
  and scrollbar
- **Data display:** list, virtual list, searchable list, table, data table,
  tree, description list, avatar, avatar group, badge, tag, label, icon,
  empty state, alert, progress, progress circle, spinner, skeleton, shimmer,
  carousel, markdown/rich text, syntax highlighter, diff view, code editor
- **Charts:** line, bar, area, pie, radar, candlestick, sankey, plot tooltip
- **Chat and AI:** message bubble, message scroller, attachment, speech
  (microphone, waveform, level indicator), questionnaire
- **Other:** webview (`crates/webview`), FPS meter (`crates/fps`), inspector,
  undo history, focus trap, motion and animation helpers

This list is a snapshot. When in doubt, checking `main` wins over this list.

## Existing code in this repo

`crates/ui` already has `Button` and `Switch`, written before this rule. Both
exist in gpui-kit. Do not extend them or use them as a template for more ports.
Keep them as they are until the user decides whether to remove them.
