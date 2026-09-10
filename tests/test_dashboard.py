from fastapi.testclient import TestClient

from app.main import app, create_app
from app.settings import Settings

client = TestClient(app)


def test_dashboard_is_served_at_root():
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Bright Smile Dental · Dr. Elena Voss" in response.text


def test_dashboard_includes_required_regions():
    response = client.get("/")
    html = response.text

    assert 'data-panel="voice-call"' in html
    assert 'data-panel="schedule"' in html
    assert 'data-panel="failure-lab"' in html
    assert 'data-panel="timeline"' in html
    assert 'data-panel="reliability-result"' in html


def test_dashboard_establishes_scenario_and_integration_path():
    response = client.get("/")
    html = response.text

    assert "Fictional customer scenario" in html
    assert "Dr. Elena Voss" in html
    assert "Integration path" in html
    assert "Failure Lab" in html
    assert "2 API attempts · 1 appointment · duplicate prevented" in html


def test_dashboard_embeds_live_demo_config():
    response = client.get("/")

    assert 'id="dashboard-config"' in response.text
    assert '"liveDemoEnabled": false' in response.text


def test_dashboard_reflects_live_demo_enabled():
    enabled_app = create_app(Settings(live_demo_enabled=True))
    enabled_client = TestClient(enabled_app)

    response = enabled_client.get("/")

    assert '"liveDemoEnabled": true' in response.text


def test_dashboard_static_assets_are_served():
    for asset in ("styles.css", "dashboard.js"):
        response = client.get(f"/static/{asset}")

        assert response.status_code == 200


def test_dashboard_state_views_are_defined():
    response = client.get("/")
    html = response.text

    for state in ("empty", "loading", "ready", "error"):
        assert f'data-view="{state}"' in html


def test_dashboard_includes_accessibility_affordances():
    response = client.get("/")
    html = response.text

    assert 'class="skip-link"' in html
    assert 'aria-live="polite"' in html
    assert 'role="switch"' in html
    assert "prefers-reduced-motion" in client.get("/static/styles.css").text


def test_dashboard_schedule_and_failure_lab_have_live_hooks():
    html = client.get("/").text
    script = client.get("/static/dashboard.js").text

    assert 'id="schedule-grid"' in html
    assert 'id="schedule-error-message"' in html
    assert 'id="reset-schedule-button"' in html
    assert 'id="failure-lab-switch"' in html
    assert 'id="failure-lab-error-message"' in html
    assert 'id="failure-lab-help"' in html
    assert "/api/schedule" in script
    assert "/api/failure-lab" in script
    assert "/api/demo/reset" in script
    assert "busy" in script
    assert "Traceback" not in script
