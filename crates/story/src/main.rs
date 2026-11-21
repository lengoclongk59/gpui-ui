//! Component gallery: one section per component, for developing and eyeballing
//! components in a real window.
//!
//! `story --automation [--port N]` also starts the automation server described
//! in `docs/AUTOMATION.md`, so tools can click, inspect and screenshot the
//! components.

mod automation;
mod gallery;
mod probe;
mod protocol;

use std::io::Write;
use std::process;

use gpui::App;
use gpui::Bounds;
use gpui::TitlebarOptions;
use gpui::WindowBounds;
use gpui::WindowOptions;
use gpui::prelude::*;

use crate::gallery::Gallery;

/// Port used by `--automation` when `--port` is not given.
const DEFAULT_AUTOMATION_PORT: u16 = 47711;

struct Args {
    /// `Some(port)` when the automation server should run.
    automation_port: Option<u16>,
}

impl Args {
    fn parse(mut args: impl Iterator<Item = String>) -> Result<Self, String> {
        let mut automation = false;
        let mut port = DEFAULT_AUTOMATION_PORT;
        while let Some(arg) = args.next() {
            match arg.as_str() {
                "--automation" => automation = true,
                "--port" => {
                    let value = args.next().ok_or("--port needs a value")?;
                    port = value
                        .parse()
                        .map_err(|_| format!("invalid --port `{value}`"))?;
                }
                other => return Err(format!("unknown argument `{other}`")),
            }
        }
        Ok(Self {
            automation_port: automation.then_some(port),
        })
    }
}

fn main() {
    let args = match Args::parse(std::env::args().skip(1)) {
        Ok(args) => args,
        Err(error) => {
            eprintln!("story: {error}\nusage: story [--automation [--port N]]");
            process::exit(2);
        }
    };

    gpui_platform::application().run(move |cx: &mut App| {
        gpui_ui::init(cx);

        let bounds = Bounds::centered(None, gpui::size(gpui::px(960.), gpui::px(680.)), cx);
        let options = WindowOptions {
            window_bounds: Some(WindowBounds::Windowed(bounds)),
            titlebar: Some(TitlebarOptions {
                title: Some("gpui-ui gallery".into()),
                ..Default::default()
            }),
            ..Default::default()
        };
        let window = cx
            .open_window(options, |_, cx| cx.new(|_| Gallery::new()))
            .expect("the platform should be able to open the gallery window");
        cx.on_window_closed(|cx, _| cx.quit()).detach();
        cx.activate(true);

        if let Some(port) = args.automation_port {
            match automation::start(port, window, cx) {
                Ok(port) => {
                    // Clients wait for this line to learn the port.
                    println!(r#"{{"event":"listening","port":{port}}}"#);
                    let _ = std::io::stdout().flush();
                }
                Err(error) => {
                    eprintln!("story: cannot start automation on port {port}: {error}");
                    process::exit(1);
                }
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(args: &[&str]) -> Result<Args, String> {
        Args::parse(args.iter().map(|arg| (*arg).to_owned()))
    }

    #[test]
    fn automation_is_off_by_default() {
        assert_eq!(parse(&[]).map(|args| args.automation_port), Ok(None));
    }

    #[test]
    fn automation_uses_default_or_given_port() {
        assert_eq!(
            parse(&["--automation"]).map(|args| args.automation_port),
            Ok(Some(DEFAULT_AUTOMATION_PORT))
        );
        assert_eq!(
            parse(&["--automation", "--port", "0"]).map(|args| args.automation_port),
            Ok(Some(0))
        );
    }

    #[test]
    fn rejects_bad_arguments() {
        assert!(parse(&["--port"]).is_err());
        assert!(parse(&["--port", "http"]).is_err());
        assert!(parse(&["--verbose"]).is_err());
    }
}
