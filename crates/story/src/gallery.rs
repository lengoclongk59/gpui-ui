//! The gallery view: one section per component, every element behind a test id.

use gpui::AnyElement;
use gpui::Context;
use gpui::SharedString;
use gpui::Window;
use gpui::prelude::*;
use gpui_ui::button::Button;
use gpui_ui::button::ButtonSize;
use gpui_ui::button::ButtonVariant;
use gpui_ui::switch::Switch;
use gpui_ui::theme::Theme;
use gpui_ui::theme::ThemeMode;
use serde::Serialize;

use crate::probe::ProbeInfo;
use crate::probe::ProbeRegistry;
use crate::probe::probe;

/// The gallery's own state, as reported to automation clients.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub struct GallerySnapshot {
    /// How many times the `primary` button was clicked.
    pub clicks: usize,
    /// The value of the `notifications` switch.
    pub notifications: bool,
}

pub struct Gallery {
    clicks: usize,
    notifications: bool,
}

impl Gallery {
    pub fn new() -> Self {
        Self {
            clicks: 0,
            notifications: true,
        }
    }

    pub fn snapshot(&self) -> GallerySnapshot {
        GallerySnapshot {
            clicks: self.clicks,
            notifications: self.notifications,
        }
    }
}

impl Render for Gallery {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        ProbeRegistry::begin_frame(cx);
        let theme = Theme::global(cx).clone();
        let next_mode = match theme.mode {
            ThemeMode::Light => ThemeMode::Dark,
            ThemeMode::Dark => ThemeMode::Light,
        };
        let toggle_label = match next_mode {
            ThemeMode::Light => "Light mode",
            ThemeMode::Dark => "Dark mode",
        };

        let header = gpui::div()
            .flex()
            .items_center()
            .justify_between()
            .child(gpui::div().text_xl().child("gpui-ui gallery"))
            .child(probe(
                "toggle-theme",
                ProbeInfo::new("button", toggle_label),
                Button::new("toggle-theme")
                    .variant(ButtonVariant::Outline)
                    .label(toggle_label)
                    .on_click(move |_, _, cx| Theme::change(next_mode, cx)),
            ));

        let variants = row()
            .child(probe(
                "primary",
                ProbeInfo::new("button", "Primary"),
                Button::new("primary")
                    .variant(ButtonVariant::Primary)
                    .label("Primary")
                    .on_click(cx.listener(|this, _, _, cx| {
                        this.clicks += 1;
                        cx.notify();
                    })),
            ))
            .child(button_probe(
                "secondary",
                "Secondary",
                ButtonVariant::Secondary,
            ))
            .child(button_probe("outline", "Outline", ButtonVariant::Outline))
            .child(button_probe("ghost", "Ghost", ButtonVariant::Ghost))
            .child(button_probe("danger", "Danger", ButtonVariant::Danger))
            .child(probe(
                "disabled",
                ProbeInfo::new("button", "Disabled").disabled(true),
                Button::new("disabled")
                    .variant(ButtonVariant::Primary)
                    .label("Disabled")
                    .disabled(true)
                    .on_click(cx.listener(|this, _, _, cx| {
                        // Never runs: a disabled button must swallow clicks.
                        // Automation tests assert that `clicks` stays put.
                        this.clicks += 1;
                        cx.notify();
                    })),
            ));

        let sizes = row()
            .child(size_probe("small", "Small", ButtonSize::Small))
            .child(size_probe("medium", "Medium", ButtonSize::Medium))
            .child(size_probe("large", "Large", ButtonSize::Large));

        let switches = row()
            .child(probe(
                "notifications",
                ProbeInfo::new("switch", "Notifications").checked(self.notifications),
                Switch::new("notifications")
                    .label("Notifications")
                    .checked(self.notifications)
                    .on_change(cx.listener(|this, checked: &bool, _, cx| {
                        this.notifications = *checked;
                        cx.notify();
                    })),
            ))
            .child(probe(
                "switch-disabled",
                ProbeInfo::new("switch", "Disabled")
                    .checked(true)
                    .disabled(true),
                Switch::new("switch-disabled")
                    .label("Disabled")
                    .checked(true)
                    .disabled(true),
            ));

        gpui::div()
            .id("gallery")
            .size_full()
            .overflow_y_scroll()
            .flex()
            .flex_col()
            .gap_6()
            .p_8()
            .bg(theme.background)
            .text_color(theme.foreground)
            .font_family(theme.font_family)
            .child(header)
            .child(section(
                &theme,
                "Button",
                format!("Primary clicked {} times", self.clicks),
                gpui::div()
                    .flex()
                    .flex_col()
                    .gap_4()
                    .child(variants)
                    .child(sizes)
                    .into_any_element(),
            ))
            .child(section(
                &theme,
                "Switch",
                format!(
                    "Notifications are {}",
                    if self.notifications { "on" } else { "off" }
                ),
                switches.into_any_element(),
            ))
    }
}

/// A button without a click handler, for showing a variant.
fn button_probe(id: &'static str, label: &'static str, variant: ButtonVariant) -> gpui::Div {
    probe(
        id,
        ProbeInfo::new("button", label),
        Button::new(id).variant(variant).label(label),
    )
}

/// A secondary button without a click handler, for showing a size.
fn size_probe(id: &'static str, label: &'static str, size: ButtonSize) -> gpui::Div {
    probe(
        id,
        ProbeInfo::new("button", label),
        Button::new(id).size(size).label(label),
    )
}

fn row() -> gpui::Div {
    gpui::div().flex().flex_wrap().items_center().gap_3()
}

fn section(
    theme: &Theme,
    title: &str,
    description: impl Into<SharedString>,
    content: AnyElement,
) -> impl IntoElement {
    gpui::div()
        .flex()
        .flex_col()
        .gap_3()
        .p_6()
        .rounded(theme.radius)
        .border_1()
        .border_color(theme.border)
        .bg(theme.surface)
        .child(
            gpui::div()
                .text_lg()
                .child(SharedString::from(title.to_owned())),
        )
        .child(
            gpui::div()
                .text_sm()
                .text_color(theme.muted_foreground)
                .child(description.into()),
        )
        .child(content)
}
