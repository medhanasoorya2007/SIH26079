import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import store as st

pytestmark = pytest.mark.skipif(
    not st.available_sources(), reason="no v2 exported artifacts/sample"
)
client = TestClient(app)


@pytest.fixture(scope="module")
def meta():
    return client.get("/meta").json()


def test_health_meta_dates(meta):
    assert client.get("/health").json()["status"] == "ok"
    assert meta["schema_version"] >= 2 and meta["lead_days"] and meta["latest_date"]
    dates = client.get("/dates").json()
    assert dates["latest"] in {d["date"] for d in dates["dates"]}


def test_regions_and_geometry():
    regs = client.get("/regions").json()
    assert len(regs) >= 30 and {"id", "lat", "lon", "name"} <= set(regs[0])
    geo = client.get("/geo/subdivisions").json()
    assert geo["type"] == "FeatureCollection" and len(geo["features"]) == len(regs)


def test_confidence_map_ranked_with_lead_summary(meta):
    r = client.get("/confidence", params={"lead": meta["lead_days"][0]}).json()
    probs = [x["bust_prob"] for x in r["regions"]]
    assert probs == sorted(probs, reverse=True) and all(0 <= p <= 1 for p in probs)
    assert {x["risk"] for x in r["regions"]} <= {"Low", "Medium", "High"}
    assert len(r["lead_summary"]) == len(meta["lead_days"])
    assert r["is_synthetic"] == meta["is_synthetic"]


def test_region_detail_v2_fields(meta):
    rid = client.get("/confidence", params={"lead": 1}).json()["regions"][0]["id"]
    d = client.get(f"/region/{rid}").json()
    assert [x["lead_day"] for x in d["leads"]] == meta["lead_days"]
    lead = d["leads"][0]
    for key in (
        "families",
        "family_sentence",
        "reasons",
        "pathway",
        "analogs",
        "confidently_wrong",
        "spread_says",
        "reliability",
        "likely_driver",
    ):
        assert key in lead
    pcts = [f["pct"] for f in lead["families"]]
    assert abs(sum(pcts) - 100) < 1.0 or sum(pcts) == 0
    assert "caused" not in lead["family_sentence"].lower()
    assert "similar past cases" in lead["analogs"]["text"]
    assert isinstance(d["risk_window"], list)


def test_evidence_endpoints():
    m = client.get("/metrics").json()
    assert "BustGuard" in m["overall"] and len(m["methods"]) >= 3  # model + both baselines
    assert "recall_low_spread_busts" in m["confidently_wrong"]["BustGuard"]
    sc = client.get("/scorecard").json()
    assert sc["cells"] and "improvement" in sc["cells"][0]
    cl = client.get("/costloss", params={"user": "farmer"}).json()
    assert cl["preset"]["alpha"] > 0 and "BustGuard" in cl["curves"]
    assert client.get("/costloss", params={"user": "nobody"}).status_code == 404
    bs = client.get("/blindspots").json()
    assert all(i["risk"] == "High" for i in bs["items"])


def test_replay_and_bad_inputs():
    events = client.get("/replay").json()
    if events:
        e = client.get(f"/replay/{events[0]['id']}").json()
        step = e["days"][0]["regions"][0]["steps"][0]
        assert {"model_prob", "spread_says", "model_risk"} <= set(step)
    assert client.get("/region/atlantis").status_code == 404
    assert client.get("/confidence", params={"date": "1900-01-01"}).status_code == 404
    assert client.get("/confidence", params={"lead": 11}).status_code == 422
    assert client.get("/confidence", params={"var": "tmax"}).status_code == 404


def test_saved_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "_saved_path", lambda: tmp_path / "saved.json")
    item = client.post(
        "/saved", json={"title": "check Konkan", "date": "2022-07-01", "lead": 3}
    ).json()
    assert client.get("/saved").json()[0]["id"] == item["id"]
    assert client.delete(f"/saved/{item['id']}").status_code == 204
    assert client.get("/saved").json() == []
