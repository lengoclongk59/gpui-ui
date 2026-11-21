//! An on/off toggle, the GPUI counterpart of a web
//! `<input type="checkbox" role="switch">`.

use gpui::App;
use gpui::ElementId;
use gpui::SharedString;
use gpui::Window;
use gpui::prelude::*;

use crate::theme::Theme;

type ChangeHandler = Box<dyn Fn(&bool, &mut Window, &mut App) + 'static>;

/// A controlled switch: it shows `checked` and reports the requested new
/// value through [`Switch::on_change`]. The owner stores the value and passes
/// it back on the next render, like a controlled React input.
#[derive(IntoElement)]
pub struct Switch {
    id: ElementId,
    checked: bool,
    disabled: bool,
    label: Option<SharedString>,
    on_change: Option<ChangeHandler>,
}

impl Switch {
    /// Creates a switch. `id` must be unique among its siblings.
    pub fn new(id: impl Into<ElementId>) -> Self {
        Self {
            id: id.into(),
            checked: false,
            disabled: false,
            label: None,
            on_change: None,
        }
    }

    pub fn checked(mut self, checked: bool) -> Self {
        self.checked = checked;
        self
    }

    pub fn disabled(mut self, disabled: bool) -> Self {
        self.disabled = disabled;
        self
    }

    /// Text shown to the right of the track; clicking it toggles too.
    pub fn label(mut self, label: impl Into<SharedString>) -> Self {
        self.label = Some(label.into());
        self
    }

    /// Called with the new value when the user toggles the switch.
    pub fn on_change(mut self, handler: impl Fn(&bool, &mut Window, &mut App) + 'static) -> Self {
        self.on_change = Some(Box::new(handler));
        self
    }
}

impl RenderOnce for Switch {
    fn render(self, _window: &mut Window, cx: &mut App) -> impl IntoElement {
        let theme = Theme::global(cx);
        let track_color = if self.checked {
            theme.primary
        } else {
            theme.secondary_active
        };
        let foreground = theme.foreground;
        let enabled = !self.disabled;
        let checked = self.checked;

        // TODO: animate the thumb with `with_animation` instead of jumping.
        let track = gpui::div()
            .flex()
            .flex_none()
            .items_center()
            .w(gpui::px(36.))
            .h(gpui::px(20.))
            .p(gpui::px(2.))
            .rounded_full()
            .bg(track_color)
            .when(checked, |this| this.justify_end())
            .child(
                gpui::div()
                    .size(gpui::px(16.))
                    .rounded_full()
                    .bg(gpui::white())
                    .shadow_sm(),
            );

        gpui::div()
            .id(self.id)
            .flex()
            .items_center()
            .gap_2()
            .text_sm()
            .text_color(foreground)
            .child(track)
            .when_some(self.label, |this, label| this.child(label))
            .when(self.disabled, |this| this.opacity(0.5).cursor_not_allowed())
            .when(enabled, |this| this.cursor_pointer())
            .when_some(self.on_change.filter(|_| enabled), |this, handler| {
                this.on_click(move |_, window, cx| handler(&!checked, window, cx))
            })
    }
}
