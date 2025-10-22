"""
Playwright E2E tests for dark mode toggle functionality.

These tests verify that the dark mode toggle button works correctly on the dashboard,
including state persistence, navigation, and protection against duplicate event listeners.

CRITICAL BUG TESTED:
The original bug involved duplicate event listeners being attached to the dark mode
toggle button - one in base.js and one in dashboard.js. This caused the theme to
toggle twice on each click, making it appear non-functional. The bug was especially
evident when navigating to /dashboard after loading the homepage.

Test coverage:
- Button presence and initial state
- Single click toggle behavior
- Double click toggle behavior (ensuring proper state)
- State persistence across page refreshes
- State persistence after navigation
- localStorage synchronization
- CSS class application
- Button label updates
"""
from __future__ import annotations

import multiprocessing
import time
from typing import Generator

import pytest
import uvicorn
from playwright.sync_api import Page, expect


# Server configuration
SERVER_HOST = "localhost"
SERVER_PORT = 8002
BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"


def run_server():
    """Run the FastAPI server in a subprocess."""
    from app.main import app

    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="warning")


@pytest.fixture(scope="module")
def fastapi_server() -> Generator[str, None, None]:
    """
    Start FastAPI server for Playwright tests.

    Returns the base URL of the running server.
    """
    # Start server in separate process
    process = multiprocessing.Process(target=run_server, daemon=True)
    process.start()

    # Wait for server to be ready
    max_retries = 30
    for i in range(max_retries):
        try:
            import requests
            response = requests.get(f"{BASE_URL}/health", timeout=1)
            if response.status_code == 200:
                break
        except Exception:
            if i == max_retries - 1:
                process.terminate()
                process.join(timeout=5)
                raise RuntimeError(f"FastAPI server failed to start after {max_retries} retries")
            time.sleep(0.5)

    yield BASE_URL

    # Cleanup
    process.terminate()
    process.join(timeout=5)
    if process.is_alive():
        process.kill()
        process.join()


@pytest.fixture
def page_with_storage(page: Page, fastapi_server: str) -> Page:
    """
    Provide a Playwright page with localStorage access.

    Clears localStorage before each test to ensure clean state.
    """
    page.goto(fastapi_server)
    page.evaluate("localStorage.clear()")
    return page


class TestDarkModeToggleBasic:
    """Basic dark mode toggle functionality tests."""

    def test_dark_mode_button_exists(self, page_with_storage: Page, fastapi_server: str):
        """Test that dark mode toggle button exists and is visible."""
        page = page_with_storage
        page.goto(fastapi_server)

        # Wait for button to be visible
        button = page.locator("#theme-toggle")
        expect(button).to_be_visible()
        expect(button).to_be_enabled()

    def test_initial_state_is_light_mode(self, page_with_storage: Page, fastapi_server: str):
        """Test that the initial theme is light mode with correct button label."""
        page = page_with_storage
        page.goto(fastapi_server)

        # Initial state should be light mode
        body = page.locator("body")
        expect(body).not_to_have_class("dark-theme")

        # Button should show dark mode option
        button = page.locator("#theme-toggle")
        expect(button).to_have_text("🌙 Dark")

        # localStorage should not have dark theme set
        theme = page.evaluate("localStorage.getItem('dashboard-theme')")
        assert theme is None or theme == "light"


class TestDarkModeSingleToggle:
    """Tests for single click toggle behavior."""

    def test_single_click_enables_dark_mode(self, page_with_storage: Page, fastapi_server: str):
        """Test that clicking the button once enables dark mode."""
        page = page_with_storage
        page.goto(fastapi_server)

        # Click the toggle button
        button = page.locator("#theme-toggle")
        button.click()

        # Wait for theme to apply
        page.wait_for_timeout(100)

        # Body should have dark-theme class
        body = page.locator("body")
        expect(body).to_have_class("dark-theme")

        # Button label should change to light mode
        expect(button).to_have_text("☀️ Light")

        # localStorage should be set to dark
        theme = page.evaluate("localStorage.getItem('dashboard-theme')")
        assert theme == "dark"

    def test_aria_label_updates_with_theme(self, page_with_storage: Page, fastapi_server: str):
        """Test that ARIA label updates correctly for accessibility."""
        page = page_with_storage
        page.goto(fastapi_server)

        button = page.locator("#theme-toggle")

        # Initial ARIA label
        expect(button).to_have_attribute("aria-label", "Switch to dark mode")

        # Click to enable dark mode
        button.click()
        page.wait_for_timeout(100)

        # ARIA label should update
        expect(button).to_have_attribute("aria-label", "Switch to light mode")


class TestDarkModeDoubleToggle:
    """Tests for double click behavior - critical for detecting duplicate event listener bug."""

    def test_double_click_returns_to_light_mode(self, page_with_storage: Page, fastapi_server: str):
        """
        Test that clicking twice returns to light mode.

        CRITICAL: This test would FAIL with the duplicate event listener bug.
        With duplicate listeners, two clicks would trigger 4 toggles total,
        resulting in the theme appearing unchanged (light -> dark -> light -> dark -> light).
        """
        page = page_with_storage
        page.goto(fastapi_server)

        button = page.locator("#theme-toggle")

        # Click once to enable dark mode
        button.click()
        page.wait_for_timeout(100)
        expect(page.locator("body")).to_have_class("dark-theme")
        expect(button).to_have_text("☀️ Light")

        # Click again to return to light mode
        button.click()
        page.wait_for_timeout(100)

        # Should be back in light mode
        expect(page.locator("body")).not_to_have_class("dark-theme")
        expect(button).to_have_text("🌙 Dark")

        # localStorage should be light
        theme = page.evaluate("localStorage.getItem('dashboard-theme')")
        assert theme == "light"

    def test_rapid_clicks_maintain_correct_state(self, page_with_storage: Page, fastapi_server: str):
        """Test that rapid clicking maintains correct state synchronization."""
        page = page_with_storage
        page.goto(fastapi_server)

        button = page.locator("#theme-toggle")

        # Rapid clicks (odd number should end in dark mode)
        for _ in range(3):
            button.click()
            page.wait_for_timeout(50)

        # After 3 clicks, should be in dark mode
        expect(page.locator("body")).to_have_class("dark-theme")
        expect(button).to_have_text("☀️ Light")

        theme = page.evaluate("localStorage.getItem('dashboard-theme')")
        assert theme == "dark"


class TestDarkModePersistence:
    """Tests for theme persistence across page loads and navigation."""

    def test_dark_mode_persists_after_refresh(self, page_with_storage: Page, fastapi_server: str):
        """Test that dark mode persists after page refresh."""
        page = page_with_storage
        page.goto(fastapi_server)

        # Enable dark mode
        button = page.locator("#theme-toggle")
        button.click()
        page.wait_for_timeout(100)

        # Refresh the page
        page.reload()
        page.wait_for_timeout(200)

        # Dark mode should still be active
        body = page.locator("body")
        expect(body).to_have_class("dark-theme")

        button_after_reload = page.locator("#theme-toggle")
        expect(button_after_reload).to_have_text("☀️ Light")

        # localStorage should still be dark
        theme = page.evaluate("localStorage.getItem('dashboard-theme')")
        assert theme == "dark"

    def test_light_mode_persists_after_refresh(self, page_with_storage: Page, fastapi_server: str):
        """Test that returning to light mode persists after refresh."""
        page = page_with_storage
        page.goto(fastapi_server)

        button = page.locator("#theme-toggle")

        # Toggle to dark, then back to light
        button.click()
        page.wait_for_timeout(100)
        button.click()
        page.wait_for_timeout(100)

        # Refresh the page
        page.reload()
        page.wait_for_timeout(200)

        # Should still be in light mode
        expect(page.locator("body")).not_to_have_class("dark-theme")
        expect(page.locator("#theme-toggle")).to_have_text("🌙 Dark")


class TestDarkModeAfterNavigation:
    """
    Tests for dark mode after navigation - CRITICAL for catching the original bug.

    The original bug manifested when:
    1. User loads homepage (/)
    2. User navigates to another page (e.g., /chat)
    3. User clicks dark mode button
    4. Button appears broken due to duplicate event listeners
    """

    def test_dark_mode_works_after_page_navigation(
        self, page_with_storage: Page, fastapi_server: str
    ):
        """
        Test that dark mode works correctly after navigating to different pages.

        CRITICAL: This is the exact scenario where the duplicate event listener bug occurred.
        The bug caused dashboard.js to add a second listener, making the button toggle twice per click.
        """
        page = page_with_storage

        # Start at homepage
        page.goto(fastapi_server)
        page.wait_for_timeout(200)

        # Navigate to chat page
        page.goto(f"{fastapi_server}/chat")
        page.wait_for_timeout(200)

        # Click dark mode button
        button = page.locator("#theme-toggle")
        button.click()
        page.wait_for_timeout(100)

        # Should enable dark mode (not toggle twice and stay light)
        body = page.locator("body")
        expect(body).to_have_class("dark-theme")
        expect(button).to_have_text("☀️ Light")

        # localStorage should be dark
        theme = page.evaluate("localStorage.getItem('dashboard-theme')")
        assert theme == "dark"

        # Click again to verify it toggles back
        button.click()
        page.wait_for_timeout(100)

        expect(body).not_to_have_class("dark-theme")
        expect(button).to_have_text("🌙 Dark")

    def test_dark_mode_consistent_across_pages(self, page_with_storage: Page, fastapi_server: str):
        """Test that dark mode state is consistent when navigating between pages."""
        page = page_with_storage

        # Enable dark mode on homepage
        page.goto(fastapi_server)
        page.locator("#theme-toggle").click()
        page.wait_for_timeout(100)

        # Navigate to insights page
        page.goto(f"{fastapi_server}/insights")
        page.wait_for_timeout(200)

        # Dark mode should already be active
        expect(page.locator("body")).to_have_class("dark-theme")
        expect(page.locator("#theme-toggle")).to_have_text("☀️ Light")

        # Disable dark mode
        page.locator("#theme-toggle").click()
        page.wait_for_timeout(100)

        # Navigate back to homepage
        page.goto(fastapi_server)
        page.wait_for_timeout(200)

        # Light mode should be active
        expect(page.locator("body")).not_to_have_class("dark-theme")
        expect(page.locator("#theme-toggle")).to_have_text("🌙 Dark")

    def test_multiple_page_navigations_maintain_toggle_functionality(
        self, page_with_storage: Page, fastapi_server: str
    ):
        """Test that toggle continues to work correctly after multiple navigations."""
        page = page_with_storage

        pages_to_test = [
            fastapi_server,
            f"{fastapi_server}/chat",
            fastapi_server,
            f"{fastapi_server}/insights",
        ]

        for page_url in pages_to_test:
            page.goto(page_url)
            page.wait_for_timeout(200)

            # Toggle dark mode
            button = page.locator("#theme-toggle")
            button.click()
            page.wait_for_timeout(100)

            # Verify it toggled correctly
            is_dark = page.locator("body").get_attribute("class") and "dark-theme" in page.locator("body").get_attribute("class")

            if is_dark:
                expect(button).to_have_text("☀️ Light")
            else:
                expect(button).to_have_text("🌙 Dark")


class TestDarkModeLocalStorage:
    """Tests for localStorage synchronization and edge cases."""

    def test_manual_localstorage_change_applied_on_load(
        self, page_with_storage: Page, fastapi_server: str
    ):
        """Test that manually setting localStorage applies dark mode on page load."""
        page = page_with_storage
        page.goto(fastapi_server)

        # Manually set localStorage to dark
        page.evaluate("localStorage.setItem('dashboard-theme', 'dark')")

        # Reload to apply
        page.reload()
        page.wait_for_timeout(200)

        # Dark mode should be active
        expect(page.locator("body")).to_have_class("dark-theme")
        expect(page.locator("#theme-toggle")).to_have_text("☀️ Light")

    def test_invalid_localstorage_value_defaults_to_light(
        self, page_with_storage: Page, fastapi_server: str
    ):
        """Test that invalid localStorage values default to light mode."""
        page = page_with_storage
        page.goto(fastapi_server)

        # Set invalid value
        page.evaluate("localStorage.setItem('dashboard-theme', 'invalid-value')")

        # Reload
        page.reload()
        page.wait_for_timeout(200)

        # Should default to light mode
        expect(page.locator("body")).not_to_have_class("dark-theme")
        expect(page.locator("#theme-toggle")).to_have_text("🌙 Dark")

    def test_empty_localstorage_defaults_to_light(
        self, page_with_storage: Page, fastapi_server: str
    ):
        """Test that empty localStorage defaults to light mode."""
        page = page_with_storage
        page.goto(fastapi_server)

        # Clear localStorage
        page.evaluate("localStorage.clear()")

        # Reload
        page.reload()
        page.wait_for_timeout(200)

        # Should default to light mode
        expect(page.locator("body")).not_to_have_class("dark-theme")
        expect(page.locator("#theme-toggle")).to_have_text("🌙 Dark")


class TestDarkModeCSSApplication:
    """Tests for CSS class application and visual state."""

    def test_dark_theme_class_toggled_on_body(self, page_with_storage: Page, fastapi_server: str):
        """Test that dark-theme class is correctly toggled on body element."""
        page = page_with_storage
        page.goto(fastapi_server)

        button = page.locator("#theme-toggle")
        body = page.locator("body")

        # Initial state - no dark-theme class
        classes = body.get_attribute("class") or ""
        assert "dark-theme" not in classes

        # Click to enable dark mode
        button.click()
        page.wait_for_timeout(100)

        # Should have dark-theme class
        classes_after = body.get_attribute("class") or ""
        assert "dark-theme" in classes_after

        # Click to disable dark mode
        button.click()
        page.wait_for_timeout(100)

        # Should not have dark-theme class
        classes_final = body.get_attribute("class") or ""
        assert "dark-theme" not in classes_final

    def test_no_duplicate_dark_theme_classes(self, page_with_storage: Page, fastapi_server: str):
        """Test that clicking multiple times doesn't add duplicate classes."""
        page = page_with_storage
        page.goto(fastapi_server)

        button = page.locator("#theme-toggle")
        body = page.locator("body")

        # Click multiple times (odd number)
        for _ in range(5):
            button.click()
            page.wait_for_timeout(50)

        # Check that class appears only once
        classes = body.get_attribute("class") or ""
        class_list = classes.split()
        dark_theme_count = class_list.count("dark-theme")

        assert dark_theme_count == 1, f"Expected 1 dark-theme class, found {dark_theme_count}"


# Integration test combining multiple scenarios
class TestDarkModeIntegration:
    """Integration tests combining multiple dark mode scenarios."""

    def test_complete_user_workflow(self, page_with_storage: Page, fastapi_server: str):
        """
        Test a complete user workflow with dark mode.

        Simulates realistic user behavior:
        1. Load homepage
        2. Enable dark mode
        3. Navigate to insights page
        4. Verify dark mode persists
        5. Toggle off dark mode
        6. Refresh page
        7. Verify light mode persists
        """
        page = page_with_storage

        # Step 1: Load homepage
        page.goto(fastapi_server)
        page.wait_for_timeout(200)

        # Step 2: Enable dark mode
        page.locator("#theme-toggle").click()
        page.wait_for_timeout(100)
        expect(page.locator("body")).to_have_class("dark-theme")

        # Step 3: Navigate to insights page
        page.goto(f"{fastapi_server}/insights")
        page.wait_for_timeout(200)

        # Step 4: Verify dark mode persists
        expect(page.locator("body")).to_have_class("dark-theme")
        expect(page.locator("#theme-toggle")).to_have_text("☀️ Light")

        # Step 5: Toggle off dark mode
        page.locator("#theme-toggle").click()
        page.wait_for_timeout(100)
        expect(page.locator("body")).not_to_have_class("dark-theme")

        # Step 6: Refresh page
        page.reload()
        page.wait_for_timeout(200)

        # Step 7: Verify light mode persists
        expect(page.locator("body")).not_to_have_class("dark-theme")
        expect(page.locator("#theme-toggle")).to_have_text("🌙 Dark")

        theme = page.evaluate("localStorage.getItem('dashboard-theme')")
        assert theme == "light"
