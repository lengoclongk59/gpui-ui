//! Design tokens shared by every component.

use gpui::App;
use gpui::Global;
use gpui::Hsla;
use gpui::Pixels;

/// Whether the light or the dark palette is active.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub enum ThemeMode {
    #[default]
    Light,
    Dark,
}

/// Semantic color and shape tokens.
///
/// Components never hard-code colors: they pick a token here, so switching
/// [`ThemeMode`] restyles the whole application. When porting a web
/// component, map its CSS variables to these tokens and add new tokens here
/// rather than inside the component.
#[derive(Clone, Debug, PartialEq)]
pub struct Theme {
    pub mode: ThemeMode,
    pub font_family: &'static str,
    pub radius: Pixels,

    pub background: Hsla,
    pub surface: Hsla,
    pub foreground: Hsla,
    pub muted_foreground: Hsla,
    pub border: Hsla,

    pub primary: Hsla,
    pub primary_hover: Hsla,
    pub primary_active: Hsla,
    pub primary_foreground: Hsla,

    pub secondary: Hsla,
    pub secondary_hover: Hsla,
    pub secondary_active: Hsla,
    pub secondary_foreground: Hsla,

    pub danger: Hsla,
    pub danger_hover: Hsla,
    pub danger_active: Hsla,
    pub danger_foreground: Hsla,
}

impl Global for Theme {}

impl Theme {
    /// The light palette.
    pub fn light() -> Self {
        Self {
            mode: ThemeMode::Light,
            font_family: default_font_family(),
            radius: gpui::px(6.),

            background: hex(0xffffff),
            surface: hex(0xf8fafc),
            foreground: hex(0x0f172a),
            muted_foreground: hex(0x64748b),
            border: hex(0xe2e8f0),

            primary: hex(0x2563eb),
            primary_hover: hex(0x3b82f6),
            primary_active: hex(0x1d4ed8),
            primary_foreground: hex(0xffffff),

            secondary: hex(0xf1f5f9),
            secondary_hover: hex(0xe2e8f0),
            secondary_active: hex(0xcbd5e1),
            secondary_foreground: hex(0x0f172a),

            danger: hex(0xdc2626),
            danger_hover: hex(0xef4444),
            danger_active: hex(0xb91c1c),
            danger_foreground: hex(0xffffff),
        }
    }

    /// The dark palette.
    pub fn dark() -> Self {
        Self {
            mode: ThemeMode::Dark,
            font_family: default_font_family(),
            radius: gpui::px(6.),

            background: hex(0x020617),
            surface: hex(0x0f172a),
            foreground: hex(0xf8fafc),
            muted_foreground: hex(0x94a3b8),
            border: hex(0x1e293b),

            primary: hex(0x3b82f6),
            primary_hover: hex(0x60a5fa),
            primary_active: hex(0x2563eb),
            primary_foreground: hex(0xffffff),

            secondary: hex(0x1e293b),
            secondary_hover: hex(0x334155),
            secondary_active: hex(0x475569),
            secondary_foreground: hex(0xf8fafc),

            danger: hex(0xdc2626),
            danger_hover: hex(0xef4444),
            danger_active: hex(0xb91c1c),
            danger_foreground: hex(0xffffff),
        }
    }

    /// Returns the palette for `mode`.
    pub fn for_mode(mode: ThemeMode) -> Self {
        match mode {
            ThemeMode::Light => Self::light(),
            ThemeMode::Dark => Self::dark(),
        }
    }

    /// Returns the active theme.
    ///
    /// # Panics
    ///
    /// Panics if [`crate::init`] has not been called.
    pub fn global(cx: &App) -> &Self {
        cx.global::<Self>()
    }

    /// Replaces the active theme and redraws every window.
    pub fn change(mode: ThemeMode, cx: &mut App) {
        cx.set_global(Self::for_mode(mode));
        cx.refresh_windows();
    }
}

fn hex(rgb: u32) -> Hsla {
    gpui::rgb(rgb).into()
}

fn default_font_family() -> &'static str {
    if cfg!(target_os = "windows") {
        "Segoe UI"
    } else if cfg!(target_os = "macos") {
        ".SystemUIFont"
    } else {
        "Inter"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn for_mode_returns_matching_palette() {
        assert_eq!(Theme::for_mode(ThemeMode::Light).mode, ThemeMode::Light);
        assert_eq!(Theme::for_mode(ThemeMode::Dark).mode, ThemeMode::Dark);
    }

    #[test]
    fn palettes_differ() {
        assert_ne!(
            Theme::light().background,
            Theme::dark().background,
            "light and dark themes must not share a background, or switching is invisible"
        );
    }
}
