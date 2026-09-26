from fastapi.testclient import TestClient

from labapi.main import app

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ping():
    assert client.get("/v1/ping").json() == {"pong": "labapi"}


def test_echo_get_reflects_request():
    r = client.get("/v1/echo", params={"a": "1"})
    body = r.json()
    assert body["method"] == "GET"
    assert body["path"] == "/v1/echo"
    assert body["query"] == {"a": "1"}


def test_echo_post_body():
    r = client.post("/v1/echo", json={"message": "hi"})
    assert r.json()["body"] == '{"message":"hi"}'


def test_echo_client_ip_from_x_real_ip():
    r = client.get("/v1/echo", headers={"X-Real-IP": "203.0.113.7"})
    assert r.json()["client_ip"] == "203.0.113.7"


def test_unknown_path_is_404():
    assert client.get("/nope").status_code == 404
