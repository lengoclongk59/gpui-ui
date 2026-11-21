//! Test ids for gallery elements, the GPUI counterpart of `data-testid`.
//!
//! [`probe`] wraps an element without changing its behavior and, when a
//! [`ProbeRegistry`] is installed, records the element's on-screen bounds and
//! description every frame. The automation server reads the registry to find
//! where to click and what each element currently shows. Component crates stay
//! untouched: the gallery, which owns every controlled value, describes them.

use std::collections::BTreeMap;

use gpui::App;
use gpui::Bounds;
use gpui::Div;
use gpui::Global;
use gpui::Pixels;
use gpui::SharedString;
use gpui::prelude::*;

/// What the gallery knows about a probed element.
#[derive(Clone, Debug, PartialEq)]
pub struct ProbeInfo {
    /// The component type, such as `"button"` or `"switch"`.
    pub kind: &'static str,
    pub label: SharedString,
    pub disabled: bool,
    /// The on/off value of toggle-like components; `None` for the others.
    pub checked: Option<bool>,
}

impl ProbeInfo {
    pub fn new(kind: &'static str, label: impl Into<SharedString>) -> Self {
        Self {
            kind,
            label: label.into(),
            disabled: false,
            checked: None,
        }
    }

    pub fn disabled(mut self, disabled: bool) -> Self {
        self.disabled = disabled;
        self
    }

    pub fn checked(mut self, checked: bool) -> Self {
        self.checked = Some(checked);
        self
    }
}

/// A probed element as of the last painted frame.
#[derive(Clone, Debug, PartialEq)]
pub struct ProbeEntry {
    pub info: ProbeInfo,
    /// Bounds in logical pixels, relative to the window's content area.
    pub bounds: Bounds<Pixels>,
}

/// Every probed element of the last frame, keyed by test id.
///
/// Only installed in automation mode, so normal runs record nothing.
#[derive(Default)]
pub struct ProbeRegistry {
    entries: BTreeMap<SharedString, ProbeEntry>,
}

impl Global for ProbeRegistry {}

impl ProbeRegistry {
    /// Forgets the previous frame. Call it at the start of the root render so
    /// elements that are no longer shown disappear from the registry.
    pub fn begin_frame(cx: &mut App) {
        if cx.has_global::<Self>() {
            cx.global_mut::<Self>().entries.clear();
        }
    }

    pub fn get(&self, id: &str) -> Option<&ProbeEntry> {
        self.entries.get(id)
    }

    /// Iterates entries in test-id order.
    pub fn entries(&self) -> impl Iterator<Item = (&SharedString, &ProbeEntry)> {
        self.entries.iter()
    }

    /// Lists the known test ids, for error messages.
    pub fn ids(&self) -> Vec<&str> {
        self.entries.keys().map(SharedString::as_ref).collect()
    }

    fn record(&mut self, id: SharedString, info: ProbeInfo, bounds: Bounds<Pixels>) {
        let previous = self.entries.insert(id.clone(), ProbeEntry { info, bounds });
        debug_assert!(
            previous.is_none(),
            "test id `{id}` is used by two elements in one frame; test ids must be unique"
        );
    }
}

/// Wraps `element` so automation can find it by `id`.
pub fn probe(id: impl Into<SharedString>, info: ProbeInfo, element: impl IntoElement) -> Div {
    let id: SharedString = id.into();
    // The canvas covers the wrapper exactly and has no hitbox, so it measures
    // the element without intercepting the clicks meant for it.
    let recorder = gpui::canvas(
        move |bounds, _window, cx| {
            if cx.has_global::<ProbeRegistry>() {
                cx.global_mut::<ProbeRegistry>().record(id, info, bounds);
            }
        },
        |_, _, _, _| {},
    )
    .absolute()
    .top_0()
    .left_0()
    .size_full();

    gpui::div()
        .relative()
        .flex_none()
        .child(element)
        .child(recorder)
}
