# Gallery automation protocol

`story --automation` opens the gallery and starts a server that lets external
tools (test scripts, a CLI-Anything harness, an AI agent) drive it: read the
state of every component, click and hover them through GPUI's real input path,
switch the theme, and render screenshots without capturing the screen.

## Starting the server

```sh
cargo run -p story -- --automation            # port 47711
cargo run -p story -- --automation --port 0   # any free port
```

The server listens on `127.0.0.1` only. Once it is ready, `story` prints one
line to stdout and keeps running:

```json
{"event":"listening","port":47711}
```

Clients should wait for that line (it carries the real port when `--port 0` is
used). Closing the window or sending `quit` ends the process.

## Wire format

JSON Lines over TCP: each request is one JSON object on one line, and the
server answers each with exactly one line, in order. A connection can carry
any number of requests. Several clients may connect at once; their requests
run one at a time on the UI thread.

Responses:

```json
{"ok":true,"result":{...}}
{"ok":false,"error":"no element with id `nope`; known ids: danger, disabled, ..."}
```

## Commands

| Request | Result |
| --- | --- |
| `{"cmd":"ping"}` | `{"app":"gpui-ui-story","version":"0.1.0","protocol":1}` |
| `{"cmd":"state"}` | the state object below |
| `{"cmd":"click","id":"primary"}` | state after the click |
| `{"cmd":"hover","id":"danger"}` | state after the pointer moved |
| `{"cmd":"set_theme","mode":"dark"}` | state after the switch (`light` or `dark`) |
| `{"cmd":"screenshot","path":"F:/out/all.png"}` | `{"path":..,"width":..,"height":..}` |
| `{"cmd":"screenshot","path":"F:/out/btn.png","id":"primary"}` | the same, cropped to one element |
| `{"cmd":"quit"}` | `{"quitting":true}`, then the gallery exits |

`click` and `hover` send real mouse events (move, down, up) to the element's
center, so hit testing, hover styles and disabled handling behave exactly as
for a user. Commands that change something answer only after the next frames
are painted, so the returned state already reflects the change.

`screenshot` renders the last frame offscreen with GPUI's `render_to_image`
and writes a PNG in device pixels. It needs the `screenshot` feature (on by
default). Use absolute paths; relative ones resolve against `story`'s working
directory.

### State object

```json
{
  "theme": "light",
  "gallery": { "clicks": 0, "notifications": true },
  "elements": [
    {
      "id": "primary",
      "kind": "button",
      "label": "Primary",
      "disabled": false,
      "checked": null,
      "bounds": { "x": 58.0, "y": 224.0, "width": 81.0, "height": 36.0 }
    }
  ]
}
```

- `gallery` holds the values the gallery owns: `clicks` counts clicks on
  `primary`, and `notifications` is the `notifications` switch.
- `elements` lists every element with a test id, sorted by id. `checked` is set
  for switches and `null` for buttons. `bounds` are logical pixels relative to
  the window content.

### Test ids

| id | kind | notes |
| --- | --- | --- |
| `toggle-theme` | button | switches light/dark |
| `primary` | button | increments `gallery.clicks` |
| `secondary`, `outline`, `ghost`, `danger` | button | variants, no action |
| `disabled` | button | disabled; clicking must not change `clicks` |
| `small`, `medium`, `large` | button | sizes, no action |
| `notifications` | switch | toggles `gallery.notifications` |
| `switch-disabled` | switch | disabled, always on |

## Adding a component

Wrap it in the gallery with `probe(id, ProbeInfo::new(kind, label), element)`
(`crates/story/src/probe.rs`). Add `.disabled(..)` / `.checked(..)` from the
values the gallery passes to the component, and add any state the gallery
owns to `GallerySnapshot`. Component crates need no automation code.

## Smoke test

`scripts/automation_smoke.py` starts the gallery on a free port, runs every
command and checks the results:

```sh
cargo build -p story
py -3 -I scripts/automation_smoke.py
```
