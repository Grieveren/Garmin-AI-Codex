# Dark Mode UI Tests - README

## Overview

This document describes the comprehensive Playwright E2E test suite for the dark mode toggle functionality in the Garmin AI Codex dashboard.

## Test File

- **Location**: `/tests/test_dark_mode_ui.py`
- **Framework**: Playwright with pytest
- **Browser**: Chromium (can be extended to Firefox, WebKit)

## What Bug Was Fixed?

The original bug involved **duplicate event listeners** being attached to the dark mode toggle button:
- `base.js` attached one event listener
- `dashboard.js` attached a second event listener

This caused the theme to toggle **twice on each click**, making the button appear non-functional. The bug was especially evident when:
1. User loads the homepage (`/`)
2. User navigates to another page (e.g., `/chat`)
3. User clicks the dark mode button
4. Button appears broken (toggles twice = no visible change)

## Solution

The fix removed the duplicate event listener code from `dashboard.js`, keeping only the implementation in `base.js`. This ensures:
- Only one event listener is attached regardless of page navigation
- Theme toggles correctly on each click
- State remains consistent across pages

## Test Coverage

### Test Classes

#### 1. `TestDarkModeToggleBasic`
- Button exists and is visible
- Initial state is light mode with correct label ("🌙 Dark")
- localStorage starts empty or set to "light"

#### 2. `TestDarkModeSingleToggle`
- Single click enables dark mode
- Body gets `dark-theme` class
- Button label changes to "☀️ Light"
- localStorage is set to "dark"
- ARIA label updates for accessibility

#### 3. `TestDarkModeDoubleToggle` ⚠️ **CRITICAL FOR BUG DETECTION**
- **`test_double_click_returns_to_light_mode`**: Would FAIL with duplicate listeners
  - With bug: 2 clicks = 4 toggles = appears unchanged
  - Without bug: 2 clicks = 2 toggles = returns to light mode
- **`test_rapid_clicks_maintain_correct_state`**: Verifies state synchronization with rapid clicking

#### 4. `TestDarkModePersistence`
- Dark mode persists after page refresh
- Light mode persists after toggling back and refreshing
- localStorage synchronization maintained

#### 5. `TestDarkModeAfterNavigation` ⚠️ **CRITICAL FOR BUG DETECTION**
- **`test_dark_mode_works_after_page_navigation`**: The exact scenario where the bug occurred
  - Navigate from `/` to `/chat`
  - Click dark mode button
  - Verifies theme toggles correctly (not twice)
- **`test_dark_mode_consistent_across_pages`**: Theme state consistent across navigation
- **`test_multiple_page_navigations_maintain_toggle_functionality`**: Toggle works after multiple navigations

#### 6. `TestDarkModeLocalStorage`
- Manual localStorage changes apply on load
- Invalid localStorage values default to light mode
- Empty localStorage defaults to light mode

#### 7. `TestDarkModeCSSApplication`
- `dark-theme` class correctly toggled on body element
- No duplicate classes added with multiple clicks

#### 8. `TestDarkModeIntegration`
- Complete user workflow simulation:
  1. Load homepage
  2. Enable dark mode
  3. Navigate to another page
  4. Verify dark mode persists
  5. Toggle off dark mode
  6. Refresh page
  7. Verify light mode persists

## Running Tests

### Install Dependencies

```bash
# Install Playwright and pytest plugin
pip install pytest-playwright playwright

# Install browsers
playwright install chromium
```

### Run All Tests

```bash
# Run all dark mode tests with verbose output
pytest tests/test_dark_mode_ui.py -v

# Run specific test class
pytest tests/test_dark_mode_ui.py::TestDarkModeDoubleToggle -v

# Run with detailed output on failure
pytest tests/test_dark_mode_ui.py -v --tb=long

# Run in headed mode (see browser)
pytest tests/test_dark_mode_ui.py --headed

# Run with multiple browsers
pytest tests/test_dark_mode_ui.py --browser chromium --browser firefox --browser webkit
```

### Run Specific Tests

```bash
# Run the critical bug-detection test
pytest tests/test_dark_mode_ui.py::TestDarkModeDoubleToggle::test_double_click_returns_to_light_mode -v

# Run navigation tests (where the bug was most evident)
pytest tests/test_dark_mode_ui.py::TestDarkModeAfterNavigation -v
```

## Test Results

**Current Status**: ✅ All 17 tests passing

```
tests/test_dark_mode_ui.py::TestDarkModeToggleBasic::test_dark_mode_button_exists[chromium] PASSED
tests/test_dark_mode_ui.py::TestDarkModeToggleBasic::test_initial_state_is_light_mode[chromium] PASSED
tests/test_dark_mode_ui.py::TestDarkModeSingleToggle::test_single_click_enables_dark_mode[chromium] PASSED
tests/test_dark_mode_ui.py::TestDarkModeSingleToggle::test_aria_label_updates_with_theme[chromium] PASSED
tests/test_dark_mode_ui.py::TestDarkModeDoubleToggle::test_double_click_returns_to_light_mode[chromium] PASSED ⚠️ CRITICAL
tests/test_dark_mode_ui.py::TestDarkModeDoubleToggle::test_rapid_clicks_maintain_correct_state[chromium] PASSED
tests/test_dark_mode_ui.py::TestDarkModePersistence::test_dark_mode_persists_after_refresh[chromium] PASSED
tests/test_dark_mode_ui.py::TestDarkModePersistence::test_light_mode_persists_after_refresh[chromium] PASSED
tests/test_dark_mode_ui.py::TestDarkModeAfterNavigation::test_dark_mode_works_after_page_navigation[chromium] PASSED ⚠️ CRITICAL
tests/test_dark_mode_ui.py::TestDarkModeAfterNavigation::test_dark_mode_consistent_across_pages[chromium] PASSED
tests/test_dark_mode_ui.py::TestDarkModeAfterNavigation::test_multiple_page_navigations_maintain_toggle_functionality[chromium] PASSED
tests/test_dark_mode_ui.py::TestDarkModeLocalStorage::test_manual_localstorage_change_applied_on_load[chromium] PASSED
tests/test_dark_mode_ui.py::TestDarkModeLocalStorage::test_invalid_localstorage_value_defaults_to_light[chromium] PASSED
tests/test_dark_mode_ui.py::TestDarkModeLocalStorage::test_empty_localstorage_defaults_to_light[chromium] PASSED
tests/test_dark_mode_ui.py::TestDarkModeCSSApplication::test_dark_theme_class_toggled_on_body[chromium] PASSED
tests/test_dark_mode_ui.py::TestDarkModeCSSApplication::test_no_duplicate_dark_theme_classes[chromium] PASSED
tests/test_dark_mode_ui.py::TestDarkModeIntegration::test_complete_user_workflow[chromium] PASSED
```

## Architecture

### Test Server Fixture

The tests use a module-scoped fixture that:
1. Starts FastAPI server on `localhost:8002`
2. Runs in a separate process (multiprocessing)
3. Waits for server health check before tests run
4. Automatically cleans up after all tests complete

```python
@pytest.fixture(scope="module")
def fastapi_server() -> Generator[str, None, None]:
    """Start FastAPI server for Playwright tests."""
    # Start server process
    # Wait for health check
    yield BASE_URL
    # Cleanup
```

### Page Storage Fixture

Each test gets a clean browser context with:
- Empty localStorage
- Fresh browser state
- Isolated from other tests

```python
@pytest.fixture
def page_with_storage(page: Page, fastapi_server: str) -> Page:
    """Provide a Playwright page with localStorage access."""
    page.goto(fastapi_server)
    page.evaluate("localStorage.clear()")
    return page
```

## Key Testing Techniques

### 1. Playwright Locators
```python
button = page.locator("#theme-toggle")
body = page.locator("body")
```

### 2. State Verification
```python
expect(body).to_have_class("dark-theme")
expect(button).to_have_text("☀️ Light")
```

### 3. localStorage Access
```python
theme = page.evaluate("localStorage.getItem('dashboard-theme')")
assert theme == "dark"
```

### 4. Accessibility Testing
```python
expect(button).to_have_attribute("aria-label", "Switch to dark mode")
```

### 5. Timing Control
```python
page.wait_for_timeout(100)  # Wait for DOM updates
```

## Test Development Best Practices

1. **Isolate Tests**: Each test should be independent and not rely on others
2. **Clean State**: Always start with empty localStorage via `page_with_storage` fixture
3. **Explicit Waits**: Use `wait_for_timeout()` for DOM updates after clicks
4. **Meaningful Names**: Test names describe what they verify (e.g., `test_double_click_returns_to_light_mode`)
5. **Critical Markers**: Tests marked ⚠️ CRITICAL would have caught the duplicate listener bug

## Continuous Integration

Add to CI/CD pipeline:

```yaml
# .github/workflows/test.yml
- name: Install Playwright
  run: |
    pip install pytest-playwright
    playwright install chromium

- name: Run UI Tests
  run: pytest tests/test_dark_mode_ui.py -v
```

## Troubleshooting

### Server Startup Issues
If tests fail with "server failed to start":
- Check port 8002 is available
- Verify FastAPI dependencies installed
- Check database migrations applied

### Timing Issues
If tests are flaky:
- Increase `wait_for_timeout()` values
- Use `expect().to_have_*()` assertions (built-in retry)
- Check network latency

### Browser Issues
If Chromium doesn't launch:
```bash
playwright install chromium --force
```

## Future Enhancements

1. **Cross-Browser Testing**: Run tests on Firefox and WebKit
2. **Visual Regression**: Take screenshots and compare CSS variable values
3. **Performance Testing**: Measure theme toggle response time
4. **Mobile Testing**: Test on mobile viewport sizes
5. **Language Toggle**: Test dark mode with German language
6. **Screenshot Artifacts**: Save screenshots on test failure for debugging

## Related Files

- **Implementation**: `/app/static/js/base.js` (dark mode logic)
- **Styles**: `/app/static/css/base.css` (dark theme CSS variables)
- **Template**: `/app/templates/base.html` (navbar with toggle button)
- **Bug Fix Commit**: Reference the commit that removed duplicate listeners from `dashboard.js`

## Contact

For questions or issues with these tests, refer to the main project documentation or open an issue.
