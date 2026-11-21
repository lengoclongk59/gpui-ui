# cli-anything-gpui-ui: Test Plan and Results

## Part 1: Test plan

### Test inventory

| File | Kind | Planned tests |
| --- | --- | --- |
| `test_core.py` | unit, synthetic data, no `story` needed | ~45 |
| `test_full_e2e.py` | E2E against the real `story` app + installed-CLI subprocess tests | ~25 |

`fake_story.py` is a test double of the automation server (same JSON Lines
protocol, in-process thread) used only by the unit tests, so client, CLI and
preview logic can be tested without a GPU window. The E2E tests never use it.

### Unit test plan (`test_core.py`)

- **`core/state.py`** (~6): element filtering by kind, lookup by id, the
  not-found error listing known ids, `summarize` counts per kind, table row
  formatting (checked `-`/`on`/`off`, bounds).
- **`core/checks.py`** (~9): `check_element` passing, failing per field
  (kind, label, disabled, checked), ignoring `None` expectations, unknown id
  raising; `parse_expected` for numbers, booleans, quoted and bare strings;
  `check_gallery` pass / fail / unknown key; `check_theme`.
- **`core/session.py`** (~6): save/load round trip, missing file -> `None`,
  `clear` -> `None`, missing keys rejected, a shorter save leaves no stale bytes
  (truncate inside the lock), `$CLI_ANYTHING_GPUI_UI_SESSION` override.
- **`core/png.py`** (~5): size, pixel values through every filter type (0-4),
  RGB and RGBA, mean color, non-PNG and out-of-range errors.
- **`utils/gpui_ui_backend.py`** (~9): repo discovery (explicit, env, invalid),
  `find_story` (explicit missing, env), parsing the `listening` line from a log,
  `pid_alive` for this process and a dead pid, `AutomationClient` success,
  `ok:false` -> `AutomationError`, unreachable port -> `BackendError`,
  relative output paths resolved to absolute.
- **`core/preview.py`** (~4): recipe list, `elements` capture writes a valid
  `preview-bundle/v1` manifest with one hero plus one image per element,
  unchanged state reuses the bundle, `latest` returns it.
- **CLI via Click's `CliRunner`** (~8): no session -> clear error and exit 1,
  `inspect state --json`, `act click --times`, `check` pass (exit 0) and fail
  (exit 1, failures in JSON), `theme toggle`, `screenshot element` verification,
  `app status` without a session.

### E2E test plan (`test_full_e2e.py`)

All E2E tests start the real `story --automation` (built from this repository)
on a free port with an isolated session file, and stop it afterwards. If
`story` is not built the tests fail with build instructions; they never skip.

- **Backend protocol** against the real app: `ping` version, initial state
  (all 12 test ids, sorted, bounds inside the window).
- **Behavior**: three clicks on `primary` count 3; clicking `disabled` does
  not count; `notifications` toggles off and on with `checked` following;
  `switch-disabled` stays on; `set_theme` switches and the toggle button label
  follows.
- **Rendering (real output files)**: window screenshot is a PNG whose size
  matches the reported size; `primary` crop is blue; a dark-theme window is
  darker on average than a light-theme one; hovering `danger` changes its
  pixels; every artifact path is printed for manual inspection.
- **Preview bundle**: `elements` recipe writes `manifest.json`,
  `summary.json` and 13 PNGs that all decode; a second capture is reused.
- **Errors**: unknown id lists the known ids.
- **CLI subprocess** (`TestCLISubprocess`, through `_resolve_cli`, no `cwd`):
  `--help`, `--version`, `app start --json`, `act click`, `check` exit codes,
  `screenshot element` producing a real PNG, `preview capture --json`,
  `app stop` and `app status` afterwards.

### Realistic workflow scenarios

1. **Component regression pass**
   - *Simulates*: an agent verifying a component change before committing.
   - *Operations*: `app start` -> click every interactive element -> `check`
     each expected value -> `screenshot element` for each -> `app stop`.
   - *Verified*: every check exits 0; every PNG decodes with non-zero size.
2. **Theme visual check**
   - *Simulates*: reviewing a palette change in both themes.
   - *Operations*: screenshot window in light -> `theme set dark` -> screenshot
     again -> `check theme dark`.
   - *Verified*: dark mean luminance is clearly lower than light.
3. **Agent debugging loop**
   - *Simulates*: an agent asserting a wrong expectation and self-correcting.
   - *Operations*: `check element primary --label Wrong --json` -> read the
     structured failure -> `check element primary --label Primary`.
   - *Verified*: first exits 1 with the actual value in `failures`, second
     exits 0.
4. **Preview publishing**
   - *Simulates*: publishing visual state for a human reviewer.
   - *Operations*: `preview capture --recipe elements --json` twice.
   - *Verified*: one bundle with 13 images; second call reports `cached: true`.

## Part 2: Test results

Run on 2026-11-21, Windows 11, Python 3.12, against the real `story` gallery
(GPUI, DirectX) and the installed `cli-anything-gpui-ui` command
(`CLI_ANYTHING_FORCE_INSTALLED=1`; the subprocess tests resolved
`C:\Users\Admin\.local\bin\cli-anything-gpui-ui.EXE`).

Command: `CLI_ANYTHING_FORCE_INSTALLED=1 py -3 -m pytest -v --tb=no` (from `agent-harness/`).

```text
============================= test session starts =============================
platform win32 -- Python 3.12.0, pytest-9.0.3, pluggy-1.6.0
hypothesis profile 'default'
rootdir: C:\RustProjects\gpui-ui\agent-harness
configfile: pytest.ini
testpaths: cli_anything/gpui_ui/tests
plugins: xonsh-0.24.2, anyio-4.13.0, hypothesis-6.155.2, asyncio-1.4.0
collecting ... collected 78 items
cli_anything/gpui_ui/tests/test_core.py::TestState::test_elements_filters_by_kind PASSED [  1%]
cli_anything/gpui_ui/tests/test_core.py::TestState::test_find_element PASSED [  2%]
cli_anything/gpui_ui/tests/test_core.py::TestState::test_find_element_lists_known_ids PASSED [  3%]
cli_anything/gpui_ui/tests/test_core.py::TestState::test_summarize_counts_kinds PASSED [  5%]
cli_anything/gpui_ui/tests/test_core.py::TestState::test_element_row_formats_checked PASSED [  6%]
cli_anything/gpui_ui/tests/test_core.py::TestState::test_element_row_formats_bounds PASSED [  7%]
cli_anything/gpui_ui/tests/test_core.py::TestChecks::test_element_passes PASSED [  8%]
cli_anything/gpui_ui/tests/test_core.py::TestChecks::test_element_fails_per_field[kind-switch] PASSED [ 10%]
cli_anything/gpui_ui/tests/test_core.py::TestChecks::test_element_fails_per_field[label-Other] PASSED [ 11%]
cli_anything/gpui_ui/tests/test_core.py::TestChecks::test_element_fails_per_field[disabled-True] PASSED [ 12%]
cli_anything/gpui_ui/tests/test_core.py::TestChecks::test_element_fails_per_field[checked-False] PASSED [ 14%]
cli_anything/gpui_ui/tests/test_core.py::TestChecks::test_element_ignores_unset_expectations PASSED [ 15%]
cli_anything/gpui_ui/tests/test_core.py::TestChecks::test_element_unknown_id_raises PASSED [ 16%]
cli_anything/gpui_ui/tests/test_core.py::TestChecks::test_parse_expected[3-3] PASSED [ 17%]
cli_anything/gpui_ui/tests/test_core.py::TestChecks::test_parse_expected[true-True] PASSED [ 19%]
cli_anything/gpui_ui/tests/test_core.py::TestChecks::test_parse_expected["on"-on] PASSED [ 20%]
cli_anything/gpui_ui/tests/test_core.py::TestChecks::test_parse_expected[on-on] PASSED [ 21%]
cli_anything/gpui_ui/tests/test_core.py::TestChecks::test_gallery_pass_and_fail PASSED [ 23%]
cli_anything/gpui_ui/tests/test_core.py::TestChecks::test_gallery_unknown_key PASSED [ 24%]
cli_anything/gpui_ui/tests/test_core.py::TestChecks::test_theme PASSED   [ 25%]
cli_anything/gpui_ui/tests/test_core.py::TestSession::test_round_trip PASSED [ 26%]
cli_anything/gpui_ui/tests/test_core.py::TestSession::test_missing_file_is_none PASSED [ 28%]
cli_anything/gpui_ui/tests/test_core.py::TestSession::test_clear PASSED  [ 29%]
cli_anything/gpui_ui/tests/test_core.py::TestSession::test_missing_keys_rejected PASSED [ 30%]
cli_anything/gpui_ui/tests/test_core.py::TestSession::test_shorter_save_leaves_no_stale_bytes PASSED [ 32%]
cli_anything/gpui_ui/tests/test_core.py::TestSession::test_env_override PASSED [ 33%]
cli_anything/gpui_ui/tests/test_core.py::TestPng::test_size PASSED       [ 34%]
cli_anything/gpui_ui/tests/test_core.py::TestPng::test_pixel_through_every_filter[0] PASSED [ 35%]
cli_anything/gpui_ui/tests/test_core.py::TestPng::test_pixel_through_every_filter[1] PASSED [ 37%]
cli_anything/gpui_ui/tests/test_core.py::TestPng::test_pixel_through_every_filter[2] PASSED [ 38%]
cli_anything/gpui_ui/tests/test_core.py::TestPng::test_pixel_through_every_filter[3] PASSED [ 39%]
cli_anything/gpui_ui/tests/test_core.py::TestPng::test_pixel_through_every_filter[4] PASSED [ 41%]
cli_anything/gpui_ui/tests/test_core.py::TestPng::test_mean_color PASSED [ 42%]
cli_anything/gpui_ui/tests/test_core.py::TestPng::test_not_png PASSED    [ 43%]
cli_anything/gpui_ui/tests/test_core.py::TestPng::test_pixel_out_of_range PASSED [ 44%]
cli_anything/gpui_ui/tests/test_core.py::TestBackend::test_find_repo_from_package_location PASSED [ 46%]
cli_anything/gpui_ui/tests/test_core.py::TestBackend::test_find_repo_env PASSED [ 47%]
cli_anything/gpui_ui/tests/test_core.py::TestBackend::test_find_repo_explicit_invalid_falls_back PASSED [ 48%]
cli_anything/gpui_ui/tests/test_core.py::TestBackend::test_find_story_explicit_missing PASSED [ 50%]
cli_anything/gpui_ui/tests/test_core.py::TestBackend::test_find_story_env PASSED [ 51%]
cli_anything/gpui_ui/tests/test_core.py::TestBackend::test_read_listening_port PASSED [ 52%]
cli_anything/gpui_ui/tests/test_core.py::TestBackend::test_pid_alive PASSED [ 53%]
cli_anything/gpui_ui/tests/test_core.py::TestBackend::test_client_success_and_error PASSED [ 55%]
cli_anything/gpui_ui/tests/test_core.py::TestBackend::test_client_unreachable PASSED [ 56%]
cli_anything/gpui_ui/tests/test_core.py::TestBackend::test_absolute_output_path PASSED [ 57%]
cli_anything/gpui_ui/tests/test_core.py::TestPreview::test_recipes PASSED [ 58%]
cli_anything/gpui_ui/tests/test_core.py::TestPreview::test_capture_elements_bundle PASSED [ 60%]
cli_anything/gpui_ui/tests/test_core.py::TestPreview::test_unchanged_state_reuses_bundle PASSED [ 61%]
cli_anything/gpui_ui/tests/test_core.py::TestPreview::test_latest PASSED [ 62%]
cli_anything/gpui_ui/tests/test_core.py::TestCli::test_no_session_is_a_clear_error PASSED [ 64%]
cli_anything/gpui_ui/tests/test_core.py::TestCli::test_status_without_session PASSED [ 65%]
cli_anything/gpui_ui/tests/test_core.py::TestCli::test_inspect_state_json PASSED [ 66%]
cli_anything/gpui_ui/tests/test_core.py::TestCli::test_click_times PASSED [ 67%]
cli_anything/gpui_ui/tests/test_core.py::TestCli::test_check_pass_and_fail_exit_codes PASSED [ 69%]
cli_anything/gpui_ui/tests/test_core.py::TestCli::test_check_switch_flags PASSED [ 70%]
cli_anything/gpui_ui/tests/test_core.py::TestCli::test_theme_toggle PASSED [ 71%]
cli_anything/gpui_ui/tests/test_core.py::TestCli::test_screenshot_element_is_verified PASSED [ 73%]
cli_anything/gpui_ui/tests/test_core.py::TestCli::test_unknown_element_error PASSED [ 74%]
cli_anything/gpui_ui/tests/test_core.py::TestCli::test_repl_with_piped_input PASSED [ 75%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestProtocol::test_ping PASSED [ 76%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestProtocol::test_initial_state_lists_every_component PASSED [ 78%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestProtocol::test_unknown_id_lists_known_ids PASSED [ 79%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestBehavior::test_primary_counts_clicks PASSED [ 80%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestBehavior::test_disabled_button_ignores_clicks PASSED [ 82%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestBehavior::test_switch_toggles_and_reports_checked PASSED [ 83%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestBehavior::test_disabled_switch_stays_on PASSED [ 84%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestBehavior::test_theme_switch_updates_toggle_label PASSED [ 85%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestRendering::test_window_screenshot PASSED [ 87%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestRendering::test_primary_crop_is_blue PASSED [ 88%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestRendering::test_dark_theme_is_darker PASSED [ 89%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestRendering::test_hover_changes_pixels PASSED [ 91%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestPreview::test_elements_bundle_and_reuse PASSED [ 92%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestCLISubprocess::test_help_and_version PASSED [ 93%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestCLISubprocess::test_component_regression_workflow PASSED [ 94%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestCLISubprocess::test_agent_debugging_loop PASSED [ 96%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestCLISubprocess::test_theme_and_preview PASSED [ 97%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestCLISubprocess::test_start_twice_is_refused PASSED [ 98%]
cli_anything/gpui_ui/tests/test_full_e2e.py::TestCLISubprocess::test_commands_without_app_fail_clearly PASSED [100%]
============================= 78 passed in 25.27s =============================
```

### Summary

| Suite | Tests | Passed | Failed |
| --- | --- | --- | --- |
| `test_core.py` (unit) | 59 | 59 | 0 |
| `test_full_e2e.py` (real app + installed CLI) | 19 | 19 | 0 |
| **Total** | **78** | **78 (100%)** | **0** |

Execution time: 25.27 s, most of it starting the real gallery (one
module-scoped instance plus one per CLI workflow test).

### Coverage notes

- Every command group is exercised through the installed command except `app
  build` (minutes of cargo work; `story` is built before the run).
- The REPL is tested with piped input (`CliRunner`), which uses the plain
  `input()` fallback. The prompt_toolkit path needs a real Windows console
  and is not covered by automated tests.
- `preview latest` is covered in unit tests and through the CLI workflow test;
  `preview recipes` and `preview capture --force` only in unit tests.
- Rendering checks are pixel-level but coarse (dominant color, mean luminance,
  hover delta); there is no golden-image comparison yet.
- Tests need a desktop session: GPUI opens a real window. They are not
  expected to run on a headless CI runner.
