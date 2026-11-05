from __future__ import annotations

import io
from datetime import date, timedelta

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def csv_file(rows: list[str]) -> dict[str, tuple[str, io.BytesIO, str]]:
    text = "date,order_id,product,quantity,unit_price\n" + "\n".join(rows) + "\n"
    return {"file": ("sales.csv", io.BytesIO(text.encode()), "text/csv")}


def make_days(day_count: int) -> list[str]:
    start = date(2026, 1, 1)
    return [
        f"{(start + timedelta(days=i)).isoformat()},ORD-{i:03d},Widget,{1 + i % 3},{100 + i}"
        for i in range(day_count)
    ]


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_calculates_kpis_and_fills_missing_day() -> None:
    rows = [
        "2026-01-01,0001,Mouse,2,100.50",
        "2026-01-01,0001,Keyboard,1,200",
        "2026-01-03,0002,Mouse,1,100.50",
    ]
    response = client.post("/analyze", files=csv_file(rows))
    assert response.status_code == 200
    payload = response.json()
    assert payload["kpis"] == {
        "total_revenue": 501.5,
        "total_orders": 2,
        "average_order_value": 250.75,
        "units_sold": 4,
    }
    assert payload["daily_revenue"][1] == {"date": "2026-01-02", "revenue": 0.0}
    assert payload["forecast"]["available"] is False
    assert payload["calendar_days"] == 3


def test_forecast_uses_seven_day_holdout_and_starts_after_last_date() -> None:
    response = client.post("/analyze", files=csv_file(make_days(35)))
    assert response.status_code == 200
    payload = response.json()
    forecast = payload["forecast"]
    assert forecast["available"] is True
    assert forecast["label"] == "Basic trend forecast"
    assert forecast["evaluation"]["holdout_days"] == 7
    assert len(forecast["predictions"]) == 7
    assert forecast["predictions"][0]["date"] == "2026-02-05"
    assert all(item["predicted_revenue"] >= 0 for item in forecast["predictions"])


def test_validation_reports_example_rows() -> None:
    rows = [
        "2026-01-01,ORD-1,Mouse,0,100",
        "not-a-date,,Keyboard,2,NaN",
    ]
    response = client.post("/analyze", files=csv_file(rows))
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["message"].startswith("The CSV could not be validated")
    assert any(item.get("example_rows") for item in detail["errors"])


def test_rejects_order_id_used_on_multiple_dates() -> None:
    rows = [
        "2026-01-01,ORD-1,Mouse,1,100",
        "2026-01-02,ORD-1,Keyboard,1,200",
    ]
    response = client.post("/analyze", files=csv_file(rows))
    assert response.status_code == 422
    assert "same date" in str(response.json()["detail"])


def test_rejects_non_csv_extension() -> None:
    response = client.post(
        "/analyze",
        files={"file": ("sales.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 415


def test_missing_api_key_does_not_affect_analysis(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    analysis = client.post("/analyze", files=csv_file(make_days(30)))
    assert analysis.status_code == 200
    analysis_id = analysis.json()["analysis_id"]

    insight = client.post("/insights", json={"analysis_id": analysis_id})
    assert insight.status_code == 503
    assert "not configured" in insight.json()["detail"]


def test_unknown_analysis_id_is_rejected() -> None:
    response = client.post("/insights", json={"analysis_id": "does-not-exist"})
    assert response.status_code == 404

