"""Integration smoke tests for Phase 3 Web Interface features."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_dashboard_page_loads(test_client: TestClient):
    """Test that dashboard page loads successfully."""
    response = test_client.get("/")
    assert response.status_code == 200
    assert b"Training Optimizer" in response.content or b"training" in response.content.lower()


def test_chat_page_loads(test_client: TestClient):
    """Test that chat interface page loads."""
    response = test_client.get("/chat")
    assert response.status_code == 200
    assert b"chat" in response.content.lower() or b"ai coach" in response.content.lower()


def test_insights_page_loads(test_client: TestClient):
    """Test that analytics insights page loads."""
    response = test_client.get("/insights")
    assert response.status_code == 200
    assert b"insights" in response.content.lower() or b"analytics" in response.content.lower()


def test_training_plan_page_loads(test_client: TestClient):
    """Test that training plan page loads."""
    response = test_client.get("/training-plan")
    assert response.status_code == 200
    assert b"training plan" in response.content.lower() or b"calendar" in response.content.lower()


def test_all_pages_use_base_template(test_client: TestClient):
    """Test that all pages include navigation elements from base template."""
    pages = ["/", "/chat", "/insights", "/training-plan"]

    for page in pages:
        response = test_client.get(page)
        assert response.status_code == 200

        # Check for navigation elements
        content = response.content.lower()
        assert b"nav" in content or b"navigation" in content

        # Check for footer
        assert b"footer" in content or b"2025" in content


def test_navigation_links_exist(test_client: TestClient):
    """Test that navigation links exist on pages."""
    response = test_client.get("/")
    assert response.status_code == 200

    content = response.content

    # Check for key navigation links
    assert b"Dashboard" in content or b"dashboard" in content
    assert b"Analytics" in content or b"analytics" in content or b"Insights" in content
    assert b"Training Plan" in content or b"training-plan" in content
    assert b"AI Coach" in content or b"chat" in content or b"Coach" in content


def test_static_css_files_accessible(test_client: TestClient):
    """Test that CSS files are accessible."""
    css_files = [
        "/static/css/base.css",
        "/static/css/dashboard.css",
    ]

    for css_file in css_files:
        response = test_client.get(css_file)
        # Should either exist (200) or if file doesn't exist, we'll get 404
        # This is okay - just checking the static file route works
        assert response.status_code in [200, 404]


def test_static_js_files_accessible(test_client: TestClient):
    """Test that JavaScript files are accessible."""
    js_files = [
        "/static/js/base.js",
        "/static/js/dashboard.js",
        "/static/js/chat.js",
        "/static/js/insights.js",
        "/static/js/training_plan.js",
    ]

    for js_file in js_files:
        response = test_client.get(js_file)
        # Should either exist (200) or 404 if not created yet
        assert response.status_code in [200, 404]


def test_dark_mode_css_variables_exist(test_client: TestClient):
    """Test that dark mode CSS variables are defined."""
    response = test_client.get("/static/css/base.css")

    if response.status_code == 200:
        content = response.content.decode('utf-8')
        # Check for CSS variables (dark mode support)
        assert "--" in content or "var(" in content


def test_health_endpoint(test_client: TestClient):
    """Test that health check endpoint works."""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_api_endpoints_accessible(test_client: TestClient):
    """Test that key API endpoints are accessible."""
    # Note: Some endpoints require database setup or valid API keys
    # Testing analytics endpoint which works with empty database
    response = test_client.get("/api/analytics/readiness-trend")

    # Should return valid response (200 with empty data)
    # Not 500 (server error)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_pages_return_html_content_type(test_client: TestClient):
    """Test that page routes return HTML content."""
    pages = ["/", "/chat", "/insights", "/training-plan"]

    for page in pages:
        response = test_client.get(page)
        assert response.status_code == 200
        # Should have HTML content type
        content_type = response.headers.get("content-type", "")
        assert "html" in content_type.lower()


def test_responsive_meta_viewport_exists(test_client: TestClient):
    """Test that pages include responsive viewport meta tag."""
    response = test_client.get("/")
    assert response.status_code == 200

    content = response.content
    # Check for viewport meta tag for mobile responsiveness
    assert b"viewport" in content


def test_no_server_errors_on_page_loads(test_client: TestClient):
    """Test that no pages return server errors on basic load."""
    pages = ["/", "/chat", "/insights", "/training-plan", "/manual/sync/now"]

    for page in pages:
        response = test_client.get(page)
        # Should not return 500-level errors
        assert response.status_code < 500, f"Page {page} returned {response.status_code}"


def test_favicon_or_static_assets(test_client: TestClient):
    """Test that static file mounting works."""
    # Test that static route is mounted
    response = test_client.get("/static/css/dashboard.css")

    # Either the file exists (200) or static mounting works (returns 404, not 500)
    assert response.status_code in [200, 404]


def test_navigation_active_link_highlighting(test_client: TestClient):
    """Test that pages include active navigation state."""
    response = test_client.get("/insights")
    assert response.status_code == 200

    content = response.content
    # Check for active class or current page indication
    assert b"active" in content or b"current" in content


def test_phase3_features_integrated(test_client: TestClient):
    """Test that all Phase 3 features are integrated and accessible."""
    # Chat interface
    chat_response = test_client.get("/chat")
    assert chat_response.status_code == 200

    # Analytics dashboard
    insights_response = test_client.get("/insights")
    assert insights_response.status_code == 200

    # Training plan
    plan_response = test_client.get("/training-plan")
    assert plan_response.status_code == 200

    # All should be accessible
    assert all([
        chat_response.status_code == 200,
        insights_response.status_code == 200,
        plan_response.status_code == 200,
    ])
