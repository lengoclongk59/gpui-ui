//! A clickable button, modeled on the web `<button>` styles of common design
//! systems (shadcn/ui, Ant Design).

use gpui::App;
use gpui::ClickEvent;
use gpui::ElementId;
use gpui::Hsla;
use gpui::Pixels;
use gpui::SharedString;
use gpui::Window;
use gpui::prelude::*;

use crate::theme::Theme;

type ClickHandler = Box<dyn Fn(&ClickEvent, &mut Window, &mut App) + 'static>;

/// The visual style of a [`Button`].
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub enum ButtonVariant {
    /// The main call to action.
    Primary,
    #[default]
    Secondary,
    /// A transparent button with a border.
    Outline,
    /// A transparent button without a border; shows a background on hover.
    Ghost,
    /// A destructive action.
    Danger,
}

/// The height and padding of a [`Button`].
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub enum ButtonSize {
    Small,
    #[default]
    Medium,
    Large,
}

#[derive(Clone, Copy)]
struct ButtonColors {
    background: Hsla,
    hover: Hsla,
    active: Hsla,
    foreground: Hsla,
    border: Hsla,
}

struct ButtonMetrics {
    height: Pixels,
    padding_x: Pixels,
    text_size: Pixels,
}

/// A button with a text label.
///
/// ```ignore
/// Button::new("save")
///     .label("Save")
///     .variant(ButtonVariant::Primary)
///     .on_click(|_, _, _| println!("saved"))
/// ```
#[derive(IntoElement)]
pub struct Button {
    id: ElementId,
    label: SharedString,
    variant: ButtonVariant,
    size: ButtonSize,
    disabled: bool,
    on_click: Option<ClickHandler>,
}

impl Button {
    /// Creates a button. `id` must be unique among its siblings: GPUI uses it
    /// to track hover and press state across frames.
    pub fn new(id: impl Into<ElementId>) -> Self {
        Self {
            id: id.into(),
            label: SharedString::default(),
            variant: ButtonVariant::default(),
            size: ButtonSize::default(),
            disabled: false,
            on_click: None,
        }
    }

    pub fn label(mut self, label: impl Into<SharedString>) -> Self {
        self.label = label.into();
        self
    }

    pub fn variant(mut self, variant: ButtonVariant) -> Self {
        self.variant = variant;
        self
    }

    pub fn size(mut self, size: ButtonSize) -> Self {
        self.size = size;
        self
    }

    /// Greys the button out and ignores clicks.
    pub fn disabled(mut self, disabled: bool) -> Self {
        self.disabled = disabled;
        self
    }

    pub fn on_click(
        mut self,
        handler: impl Fn(&ClickEvent, &mut Window, &mut App) + 'static,
    ) -> Self {
        self.on_click = Some(Box::new(handler));
        self
    }
}

impl ButtonVariant {
    fn colors(self, theme: &Theme) -> ButtonColors {
        let transparent = gpui::transparent_black();
        match self {
            Self::Primary => ButtonColors {
                background: theme.primary,
                hover: theme.primary_hover,
                active: theme.primary_active,
                foreground: theme.primary_foreground,
                border: theme.primary,
            },
            Self::Secondary => ButtonColors {
                background: theme.secondary,
                hover: theme.secondary_hover,
                active: theme.secondary_active,
                foreground: theme.secondary_foreground,
                border: theme.secondary,
            },
            Self::Outline => ButtonColors {
                background: transparent,
                hover: theme.secondary,
                active: theme.secondary_hover,
                foreground: theme.foreground,
                border: theme.border,
            },
            Self::Ghost => ButtonColors {
                background: transparent,
                hover: theme.secondary,
                active: theme.secondary_hover,
                foreground: theme.foreground,
                border: transparent,
            },
            Self::Danger => ButtonColors {
                background: theme.danger,
                hover: theme.danger_hover,
                active: theme.danger_active,
                foreground: theme.danger_foreground,
                border: theme.danger,
            },
        }
    }
}

impl ButtonSize {
    fn metrics(self) -> ButtonMetrics {
        match self {
            Self::Small => ButtonMetrics {
                height: gpui::px(28.),
                padding_x: gpui::px(10.),
                text_size: gpui::px(12.),
            },
            Self::Medium => ButtonMetrics {
                height: gpui::px(36.),
                padding_x: gpui::px(16.),
                text_size: gpui::px(14.),
            },
            Self::Large => ButtonMetrics {
                height: gpui::px(44.),
                padding_x: gpui::px(24.),
                text_size: gpui::px(16.),
            },
        }
    }
}

impl RenderOnce for Button {
    fn render(self, _window: &mut Window, cx: &mut App) -> impl IntoElement {
        let theme = Theme::global(cx);
        let colors = self.variant.colors(theme);
        let metrics = self.size.metrics();
        let radius = theme.radius;
        let enabled = !self.disabled;

        gpui::div()
            .id(self.id)
            .flex()
            .flex_none()
            .items_center()
            .justify_center()
            .h(metrics.height)
            .px(metrics.padding_x)
            .text_size(metrics.text_size)
            .rounded(radius)
            .border_1()
            .border_color(colors.border)
            .bg(colors.background)
            .text_color(colors.foreground)
            .child(self.label)
            .when(self.disabled, |this| this.opacity(0.5).cursor_not_allowed())
            .when(enabled, |this| {
                this.cursor_pointer()
                    .hover(move |style| style.bg(colors.hover))
                    .active(move |style| style.bg(colors.active))
            })
            .when_some(self.on_click.filter(|_| enabled), |this, handler| {
                this.on_click(move |event, window, cx| handler(event, window, cx))
            })
    }
}
