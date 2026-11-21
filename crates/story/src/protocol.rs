//! Wire format of the automation server.
//!
//! The server speaks JSON Lines over TCP: each request is one JSON object on
//! one line, and each gets exactly one response line. See `docs/AUTOMATION.md`.

use std::path::PathBuf;

use gpui_ui::theme::ThemeMode;
use serde::Deserialize;
use serde::Serialize;
use serde_json::Value;

/// Bumped on every incompatible change to requests or responses.
pub const PROTOCOL_VERSION: u32 = 1;

/// A command sent by an automation client.
#[derive(Clone, Debug, PartialEq, Deserialize)]
#[serde(tag = "cmd", rename_all = "snake_case")]
pub enum Request {
    /// Checks that the server is up and reports its protocol version.
    Ping,
    /// Reports the theme, the gallery state and every probed element.
    State,
    /// Moves the pointer to the element's center and clicks the left button.
    Click { id: String },
    /// Moves the pointer to the element's center without clicking.
    Hover { id: String },
    /// Switches the light/dark theme.
    SetTheme { mode: ThemeName },
    /// Renders the window, or one element of it, to a PNG file.
    Screenshot {
        path: PathBuf,
        #[serde(default)]
        id: Option<String>,
    },
    /// Closes the gallery.
    Quit,
}

/// The serialized name of a [`ThemeMode`].
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ThemeName {
    Light,
    Dark,
}

impl From<ThemeName> for ThemeMode {
    fn from(name: ThemeName) -> Self {
        match name {
            ThemeName::Light => ThemeMode::Light,
            ThemeName::Dark => ThemeMode::Dark,
        }
    }
}

impl From<ThemeMode> for ThemeName {
    fn from(mode: ThemeMode) -> Self {
        match mode {
            ThemeMode::Light => ThemeName::Light,
            ThemeMode::Dark => ThemeName::Dark,
        }
    }
}

/// The reply to one request: `{"ok":true,"result":..}` or
/// `{"ok":false,"error":".."}`.
#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct Response {
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

impl Response {
    pub fn success(result: Value) -> Self {
        Self {
            ok: true,
            result: Some(result),
            error: None,
        }
    }

    pub fn failure(error: impl Into<String>) -> Self {
        Self {
            ok: false,
            result: None,
            error: Some(error.into()),
        }
    }

    /// Serializes the response as one line, without the trailing newline.
    pub fn to_line(&self) -> String {
        serde_json::to_string(self).expect("a Response holds only JSON-safe values")
    }
}

impl From<Result<Value, String>> for Response {
    fn from(result: Result<Value, String>) -> Self {
        match result {
            Ok(value) => Self::success(value),
            Err(error) => Self::failure(error),
        }
    }
}

/// Parses one request line.
pub fn parse_request(line: &str) -> Result<Request, String> {
    serde_json::from_str(line).map_err(|error| format!("invalid request: {error}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_commands_without_arguments() {
        assert_eq!(parse_request(r#"{"cmd":"ping"}"#), Ok(Request::Ping));
        assert_eq!(parse_request(r#"{"cmd":"state"}"#), Ok(Request::State));
        assert_eq!(parse_request(r#"{"cmd":"quit"}"#), Ok(Request::Quit));
    }

    #[test]
    fn parses_element_commands() {
        assert_eq!(
            parse_request(r#"{"cmd":"click","id":"primary"}"#),
            Ok(Request::Click {
                id: "primary".to_owned()
            })
        );
        assert_eq!(
            parse_request(r#"{"cmd":"hover","id":"danger"}"#),
            Ok(Request::Hover {
                id: "danger".to_owned()
            })
        );
    }

    #[test]
    fn parses_set_theme() {
        assert_eq!(
            parse_request(r#"{"cmd":"set_theme","mode":"dark"}"#),
            Ok(Request::SetTheme {
                mode: ThemeName::Dark
            })
        );
        assert!(parse_request(r#"{"cmd":"set_theme","mode":"sepia"}"#).is_err());
    }

    #[test]
    fn screenshot_id_is_optional() {
        assert_eq!(
            parse_request(r#"{"cmd":"screenshot","path":"out.png"}"#),
            Ok(Request::Screenshot {
                path: PathBuf::from("out.png"),
                id: None
            })
        );
        assert_eq!(
            parse_request(r#"{"cmd":"screenshot","path":"out.png","id":"primary"}"#),
            Ok(Request::Screenshot {
                path: PathBuf::from("out.png"),
                id: Some("primary".to_owned())
            })
        );
    }

    #[test]
    fn rejects_unknown_commands_and_bad_json() {
        assert!(parse_request(r#"{"cmd":"explode"}"#).is_err());
        assert!(
            parse_request(r#"{"cmd":"click"}"#).is_err(),
            "click needs an id"
        );
        assert!(parse_request("not json").is_err());
    }

    #[test]
    fn responses_serialize_to_documented_shape() {
        assert_eq!(
            Response::success(serde_json::json!({"pong": true})).to_line(),
            r#"{"ok":true,"result":{"pong":true}}"#
        );
        assert_eq!(
            Response::failure("boom").to_line(),
            r#"{"ok":false,"error":"boom"}"#
        );
    }

    #[test]
    fn theme_names_round_trip() {
        for mode in [ThemeMode::Light, ThemeMode::Dark] {
            assert_eq!(ThemeMode::from(ThemeName::from(mode)), mode);
        }
    }
}
