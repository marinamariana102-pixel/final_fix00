from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.storage.session_store import store


WORKBOOK_PATH = Path(__file__).resolve().parents[1] / ".." / "INPUT" / "TIO2_Sprint_Intelligence_v5_final.xlsx"
WORKBOOK_PATH = WORKBOOK_PATH.resolve()


def _client() -> TestClient:
    store.clear_all()
    return TestClient(app)


def _upload_workbook(client: TestClient):
    with WORKBOOK_PATH.open("rb") as fh:
        response = client.post(
            "/api/upload",
            files={"file": (WORKBOOK_PATH.name, fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload["data"]["session_id"]


def test_session_snapshot_works_after_normal_upload():
    client = _client()
    session_id = _upload_workbook(client)

    response = client.get(f"/api/session-snapshot?session_id={session_id}")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["forecast"]


def test_session_snapshot_exposes_blocker_metrics():
    client = _client()
    session_id = _upload_workbook(client)

    response = client.get(f"/api/session-snapshot?session_id={session_id}")

    assert response.status_code == 200, response.text
    payload = response.json()
    blocker_metrics = payload["data"]["blocker_metrics"]

    assert blocker_metrics["total_blocker_count"] >= 0
    assert blocker_metrics["active_blocker_count"] >= 0
    assert blocker_metrics["resolved_blocker_count"] >= 0
    assert blocker_metrics["current_sprint_active_blocker_count"] >= 0


def test_sprint_health_works_after_normal_upload():
    client = _client()
    session_id = _upload_workbook(client)

    response = client.get(f"/api/sprint-health?session_id={session_id}")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True


def test_recovery_plans_work_after_normal_upload():
    client = _client()
    session_id = _upload_workbook(client)

    response = client.get(f"/api/recovery-plans?session_id={session_id}")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["plans"]


def test_demo_and_upload_produce_equivalent_analysis():
    client = _client()

    demo_response = client.post("/api/demo/load")
    assert demo_response.status_code == 200, demo_response.text
    demo_session_id = demo_response.json()["data"]["session_id"]

    upload_session_id = _upload_workbook(client)

    demo_pipeline = store.get_or_build_pipeline_result(demo_session_id)
    upload_pipeline = store.get_or_build_pipeline_result(upload_session_id)

    assert demo_pipeline.forecast.expected_finish_date == upload_pipeline.forecast.expected_finish_date
    assert demo_pipeline.monte_carlo.on_time_probability == upload_pipeline.monte_carlo.on_time_probability
    assert demo_pipeline.risk_result.overall_risk_score == upload_pipeline.risk_result.overall_risk_score
