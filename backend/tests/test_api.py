from fastapi.testclient import TestClient

import main
from scenarios.mission01 import Mission01

client = TestClient(main.app)


def test_mission_list_has_both_missions_available():
    ms = client.get("/api/missions").json()
    by_id = {m["id"]: m for m in ms}
    assert by_id["mission01"]["status"] == "available"
    assert by_id["mission02"]["status"] == "available"
    for m in ms:
        assert {"title", "category", "difficulty", "minutes", "summary", "number"} <= set(m)


def test_mission_list_does_not_leak_root_cause():
    text = client.get("/api/missions").text
    assert Mission01.root_cause not in text
    assert "tomcat" not in text.lower() and "방화벽" not in text


def test_unknown_mission_cannot_start_a_session():
    r = client.post("/api/sessions", json={"mission_id": "mission99"})
    assert r.status_code == 404 and "준비" in r.json()["detail"]
