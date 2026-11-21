//! Web-inspired UI components for GPUI.
//!
//! Each component lives in its own module and reads its colors and metrics
//! from the global [`theme::Theme`]. Call [`init`] once at startup, before
//! rendering any component.

pub mod button;
pub mod switch;
pub mod theme;

use gpui::App;

use crate::theme::Theme;
use crate::theme::ThemeMode;

/// Installs the default (light) theme. Call it once, before opening a window.
pub fn init(cx: &mut App) {
    Theme::change(ThemeMode::Light, cx);
}
