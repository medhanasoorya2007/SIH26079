import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import store as st

pytestmark = pytest.mark.skipif(not st.available_sources(), reason="no exported artifacts/sample")
client = TestClient(app)


def test_health_and_meta():
    assert client.get("/health").json()["status"] == "ok"
    meta = client.get("/meta").json()
    assert meta["lead_days"] and meta["latest_date"]


def test_regions():
    regs = client.get("/regions").json()
    assert len(regs) >= 60 and {"id", "lat", "lon"} <= set(regs[0])


def test_confidence_map_is_ranked_and_bounded():
    meta = client.get("/meta").json()
    r = client.get("/confidence", params={"lead": meta["lead_days"][0]}).json()
    probs = [x["bust_prob"] for x in r["regions"]]
    assert probs == sorted(probs, reverse=True)
    assert all(0 <= p <= 1 for p in probs)
    assert r["error_prone"][0] == r["regions"][0]["id"]
    assert r["is_synthetic"] == meta["is_synthetic"]


def test_region_detail_has_all_leads_reasons_and_analogs():
    meta = client.get("/meta").json()
    rid = client.get("/confidence", params={"lead": meta["lead_days"][0]}).json()["error_prone"][0]
    d = client.get(f"/region/{rid}").json()
    assert [x["lead_day"] for x in d["leads"]] == meta["lead_days"]
    assert any(x["reasons"] for x in d["leads"])
    assert all(len(x["analogs"]) <= 5 for x in d["leads"])


def test_bad_inputs():
    assert client.get("/region/atlantis").status_code == 404
    assert client.get("/confidence", params={"date": "1900-01-01"}).status_code == 404
    assert client.get("/confidence", params={"lead": 11}).status_code == 422


def test_metrics_and_replay():
    m = client.get("/metrics").json()
    assert "BustGuard" in next(iter(m["labels"].values()))["overall"]
    events = client.get("/replay").json()
    if events:
        e = client.get(f"/replay/{events[0]['id']}").json()
        assert e["per_lead"] and len(e["region_names"]) == e["n_regions"]


def test_saved_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "_saved_path", lambda: tmp_path / "saved.json")
    item = client.post(
        "/saved", json={"title": "check Konkan", "date": "2022-07-01", "lead": 3}
    ).json()
    assert client.get("/saved").json()[0]["id"] == item["id"]
    assert client.delete(f"/saved/{item['id']}").status_code == 204
    assert client.get("/saved").json() == []
