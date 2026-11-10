import numpy as np
import pytest

pytest.importorskip("torch")
hub = pytest.importorskip("huggingface_hub")
MODEL = __import__("os").environ.get("COUNTERFACT_MODEL_DIR", "")   # a local copy of the HF repo; skipped if unset


def test_local_analyze(monkeypatch):
    import os
    if not MODEL or not os.path.isdir(MODEL):
        pytest.skip("local model copy not present")
    monkeypatch.setattr(hub, "snapshot_download", lambda repo, revision=None: MODEL)
    from counterfact import Local
    rng = np.random.default_rng(0)
    m = 100 + np.cumsum(rng.normal(0, 1, 90))
    data = {"week": [f"w{i}" for i in range(90)], "b": list(m + rng.normal(0, 1, 90)), "c": list(1.2 * m + rng.normal(0, 1, 90))}
    y = m + 5 + rng.normal(0, 1, 90); y[70:] += 8
    data["sales"] = list(y)
    r = Local().analyze(data, metric="sales", change_at="w70", time_col="week")
    assert r.verdict == "worked" and r.likely_range[0] < 8 < r.likely_range[1] + 4
    print(r)
