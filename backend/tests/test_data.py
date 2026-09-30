import numpy as np

from ml.data.weatherbench2 import ByteLedger, _decode_cf


def test_byte_ledger_persists_and_caps(tmp_path):
    p = tmp_path / "ledger.json"
    led = ByteLedger(p, cap_bytes=1000)
    led.add("hres", 600)
    assert ByteLedger(p, 1000).total == 600  # resumed from disk
    assert led.would_exceed(401) and not led.would_exceed(400)
    # a sibling ledger (another downloader process) shares the same cap
    ByteLedger(tmp_path / "_ledger_other.json", 1000).add("imd", 300)
    led2 = ByteLedger(tmp_path / "_ledger.json", 1000)
    led2.add("hres", 0)
    assert led2.total == 300 and led2.would_exceed(701)


def test_decode_cf_times_and_leads():
    t = _decode_cf(
        np.array([0, 24]), {"units": "hours since 2020-06-01", "calendar": "proleptic_gregorian"}
    )
    assert str(t[1])[:10] == "2020-06-02"
    lead = _decode_cf(np.array([0, 21600000000000]), {"units": "nanoseconds"})
    assert lead.tolist() == [0.0, 6.0]


def test_synthetic_rows_are_flagged():
    from ml.data.synthetic import generate

    df = generate(years=(2020,), lead_days=(1,))
    assert df["is_synthetic"].all() and (df["source"] == "SYNTHETIC").all()
