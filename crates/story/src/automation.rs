//! Automation server: lets external tools drive the gallery over TCP.
//!
//! A background thread accepts connections on a loopback port and forwards
//! each parsed request to the GPUI main thread, which executes it against the
//! live window and answers once the next frames are painted. Pointer commands
//! dispatch real mouse events through GPUI's hit testing, so they exercise the
//! same code path as a user's click, including disabled elements ignoring it.

use std::io::BufRead;
use std::io::BufReader;
use std::io::Write;
use std::net::Ipv4Addr;
use std::net::TcpListener;
use std::net::TcpStream;
use std::pin;
use std::thread;
use std::time::Duration;

use futures::StreamExt;
use futures::channel::mpsc;
use futures::channel::oneshot;
use futures::executor;
use futures::future;
use gpui::App;
use gpui::AsyncApp;
use gpui::Modifiers;
use gpui::MouseButton;
use gpui::MouseDownEvent;
use gpui::MouseMoveEvent;
use gpui::MouseUpEvent;
use gpui::Pixels;
use gpui::PlatformInput;
use gpui::Point;
use gpui::WindowHandle;
use gpui::prelude::*;
use gpui_ui::theme::Theme;
use serde_json::Value;
use serde_json::json;

use crate::gallery::Gallery;
use crate::probe::ProbeRegistry;
use crate::protocol;
use crate::protocol::Request;
use crate::protocol::Response;
use crate::protocol::ThemeName;

/// How many frames to wait after a command so its effects are painted and
/// recorded by the probes.
const SETTLE_FRAMES: usize = 2;

/// Upper bound per frame wait, for windows that are minimized or occluded and
/// therefore not drawing.
const FRAME_TIMEOUT: Duration = Duration::from_millis(500);

type Job = (Request, oneshot::Sender<Response>);

/// Starts the server on `127.0.0.1:port` (0 picks a free port) and returns
/// the bound port.
pub fn start(port: u16, window: WindowHandle<Gallery>, cx: &mut App) -> std::io::Result<u16> {
    let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, port))?;
    let port = listener.local_addr()?.port();
    cx.set_global(ProbeRegistry::default());

    let (jobs_tx, mut jobs_rx) = mpsc::unbounded::<Job>();
    thread::Builder::new()
        .name("automation-server".to_owned())
        .spawn(move || accept_loop(&listener, &jobs_tx))?;

    cx.spawn(async move |cx: &mut AsyncApp| {
        while let Some((request, reply)) = jobs_rx.next().await {
            let quit = request == Request::Quit;
            let response = Response::from(execute(request, window, cx).await);
            // The client may have disconnected; nothing to do about it.
            let _ = reply.send(response);
            if quit {
                cx.update(|cx| cx.quit());
                break;
            }
        }
    })
    .detach();

    Ok(port)
}

fn accept_loop(listener: &TcpListener, jobs: &mpsc::UnboundedSender<Job>) {
    for stream in listener.incoming() {
        let Ok(stream) = stream else { continue };
        let jobs = jobs.clone();
        // One thread per client; the main thread still runs jobs one at a time.
        let spawned = thread::Builder::new()
            .name("automation-client".to_owned())
            .spawn(move || serve_client(stream, &jobs));
        if let Err(error) = spawned {
            eprintln!("automation: cannot spawn client thread: {error}");
        }
    }
}

fn serve_client(stream: TcpStream, jobs: &mpsc::UnboundedSender<Job>) {
    let Ok(mut writer) = stream.try_clone() else {
        return;
    };
    for line in BufReader::new(stream).lines() {
        let Ok(line) = line else { return };
        if line.trim().is_empty() {
            continue;
        }
        let response = match protocol::parse_request(&line) {
            Ok(request) => run_on_main_thread(request, jobs),
            Err(error) => Response::failure(error),
        };
        if writeln!(writer, "{}", response.to_line()).is_err() {
            return;
        }
    }
}

fn run_on_main_thread(request: Request, jobs: &mpsc::UnboundedSender<Job>) -> Response {
    let (reply_tx, reply_rx) = oneshot::channel();
    if jobs.unbounded_send((request, reply_tx)).is_err() {
        return Response::failure("the gallery is shutting down");
    }
    executor::block_on(reply_rx)
        .unwrap_or_else(|_| Response::failure("the gallery dropped the request"))
}

async fn execute(
    request: Request,
    window: WindowHandle<Gallery>,
    cx: &mut AsyncApp,
) -> Result<Value, String> {
    match request {
        Request::Ping => Ok(json!({
            "app": "gpui-ui-story",
            "version": env!("CARGO_PKG_VERSION"),
            "protocol": protocol::PROTOCOL_VERSION,
        })),
        Request::State => state(window, cx),
        Request::Click { id } => {
            let position = element_center(window, &id, cx)?;
            dispatch_click(window, position, cx)?;
            settle(window, cx).await;
            state(window, cx)
        }
        Request::Hover { id } => {
            let position = element_center(window, &id, cx)?;
            dispatch(window, &[mouse_move(position)], cx)?;
            settle(window, cx).await;
            state(window, cx)
        }
        Request::SetTheme { mode } => {
            cx.update(|cx| Theme::change(mode.into(), cx));
            settle(window, cx).await;
            state(window, cx)
        }
        Request::Screenshot { path, id } => {
            settle(window, cx).await;
            screenshot(window, &path, id.as_deref(), cx)
        }
        Request::Quit => Ok(json!({ "quitting": true })),
    }
}

fn state(window: WindowHandle<Gallery>, cx: &mut AsyncApp) -> Result<Value, String> {
    window
        .update(cx, |gallery, _window, cx| {
            let theme = ThemeName::from(Theme::global(cx).mode);
            let elements: Vec<Value> = cx
                .global::<ProbeRegistry>()
                .entries()
                .map(|(id, entry)| {
                    json!({
                        "id": id.as_ref(),
                        "kind": entry.info.kind,
                        "label": entry.info.label.as_ref(),
                        "disabled": entry.info.disabled,
                        "checked": entry.info.checked,
                        "bounds": {
                            "x": f32::from(entry.bounds.origin.x),
                            "y": f32::from(entry.bounds.origin.y),
                            "width": f32::from(entry.bounds.size.width),
                            "height": f32::from(entry.bounds.size.height),
                        },
                    })
                })
                .collect();
            json!({
                "theme": theme,
                "gallery": gallery.snapshot(),
                "elements": elements,
            })
        })
        .map_err(window_closed)
}

fn element_center(
    window: WindowHandle<Gallery>,
    id: &str,
    cx: &mut AsyncApp,
) -> Result<Point<Pixels>, String> {
    window
        .update(cx, |_, _, cx| {
            let registry = cx.global::<ProbeRegistry>();
            match registry.get(id) {
                Some(entry) => Ok(entry.bounds.center()),
                None => Err(format!(
                    "no element with id `{id}`; known ids: {}",
                    registry.ids().join(", ")
                )),
            }
        })
        .map_err(window_closed)?
}

fn dispatch_click(
    window: WindowHandle<Gallery>,
    position: Point<Pixels>,
    cx: &mut AsyncApp,
) -> Result<(), String> {
    let down = PlatformInput::MouseDown(MouseDownEvent {
        button: MouseButton::Left,
        position,
        modifiers: Modifiers::default(),
        click_count: 1,
        first_mouse: false,
    });
    let up = PlatformInput::MouseUp(MouseUpEvent {
        button: MouseButton::Left,
        position,
        modifiers: Modifiers::default(),
        click_count: 1,
    });
    dispatch(window, &[mouse_move(position), down, up], cx)
}

fn mouse_move(position: Point<Pixels>) -> PlatformInput {
    PlatformInput::MouseMove(MouseMoveEvent {
        position,
        pressed_button: None,
        modifiers: Modifiers::default(),
    })
}

/// Feeds `events` to the window as if they came from the platform.
fn dispatch(
    window: WindowHandle<Gallery>,
    events: &[PlatformInput],
    cx: &mut AsyncApp,
) -> Result<(), String> {
    // `update_window` leases only the window, not the `Gallery` entity, so
    // listeners created with `cx.listener` can update the gallery.
    cx.update_window(window.into(), |_, window, cx| {
        for event in events {
            window.dispatch_event(event.clone(), cx);
        }
    })
    .map_err(window_closed)
}

/// Waits until the effects of the last command are painted, so the probes
/// have re-recorded every element.
async fn settle(window: WindowHandle<Gallery>, cx: &mut AsyncApp) {
    for _ in 0..SETTLE_FRAMES {
        let (frame_tx, frame_rx) = oneshot::channel::<()>();
        let requested = window.update(cx, |_, window, _| {
            window.refresh();
            window.on_next_frame(move |_, _| {
                let _ = frame_tx.send(());
            });
        });
        if requested.is_err() {
            return;
        }
        let timeout = cx.background_executor().timer(FRAME_TIMEOUT);
        future::select(frame_rx, pin::pin!(timeout)).await;
    }
}

#[cfg(feature = "screenshot")]
fn screenshot(
    window: WindowHandle<Gallery>,
    path: &std::path::Path,
    id: Option<&str>,
    cx: &mut AsyncApp,
) -> Result<Value, String> {
    use image::imageops;

    let (image, crop) = cx
        .update_window(window.into(), |_, window, cx| {
            let image = window
                .render_to_image()
                .map_err(|error| format!("cannot render the window: {error}"))?;
            let crop = match id {
                None => None,
                Some(id) => {
                    let registry = cx.global::<ProbeRegistry>();
                    let entry = registry.get(id).ok_or_else(|| {
                        format!(
                            "no element with id `{id}`; known ids: {}",
                            registry.ids().join(", ")
                        )
                    })?;
                    Some((entry.bounds, window.scale_factor()))
                }
            };
            Ok::<_, String>((image, crop))
        })
        .map_err(window_closed)??;

    let image = match crop {
        None => image,
        Some((bounds, scale)) => {
            // Probe bounds are logical pixels; the image is in device pixels.
            let to_device = |value: Pixels| (f32::from(value) * scale).round().max(0.) as u32;
            let x = to_device(bounds.origin.x).min(image.width());
            let y = to_device(bounds.origin.y).min(image.height());
            let width = to_device(bounds.size.width).min(image.width() - x);
            let height = to_device(bounds.size.height).min(image.height() - y);
            imageops::crop_imm(&image, x, y, width, height).to_image()
        }
    };
    image
        .save(path)
        .map_err(|error| format!("cannot write `{}`: {error}", path.display()))?;
    Ok(json!({
        "path": path.display().to_string(),
        "width": image.width(),
        "height": image.height(),
    }))
}

#[cfg(not(feature = "screenshot"))]
fn screenshot(
    _window: WindowHandle<Gallery>,
    _path: &std::path::Path,
    _id: Option<&str>,
    _cx: &mut AsyncApp,
) -> Result<Value, String> {
    Err("screenshots are disabled; rebuild `story` with `--features screenshot`".to_owned())
}

fn window_closed(error: impl std::fmt::Display) -> String {
    format!("the gallery window is closed: {error}")
}
