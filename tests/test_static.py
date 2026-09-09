from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_static_assets_are_served():
    response = client.get("/static/.gitkeep")

    assert response.status_code == 200
