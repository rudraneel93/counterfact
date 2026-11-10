import json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from counterfact import Client, CounterfactError

SUMMARY = {"metric": "sales", "change_at": "W81", "verdict": "worked", "effect_per_period": 40.9, "effect_percent": 9.5,
           "likely_range_per_period": [18.6, 63.2], "total_effect_over_period": 982.0, "chance_effect_is_positive": 0.99,
           "quick_before_after": {"difference": 52.1}, "comparisons_used": ["b"],
           "robustness": {"fake_dates_flagged": "0 of 3", "verdict_stable_when_dropping": "n/a"}}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        if self.headers.get("x-api-key") != "good":
            self.send_response(403); self.end_headers(); self.wfile.write(b'{"detail":"That access code isn\'t valid."}'); return
        assert body["metric"] == "sales" and body["index"][0] == "W1" and "week" not in body["series"]
        self.send_response(200); self.end_headers()
        self.wfile.write(json.dumps({"summary": SUMMARY, "explanation": "It worked.", "counterfactual": {}}).encode())


@pytest.fixture
def server():
    s = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}"
    s.shutdown()


def test_analyze_dict_and_errors(server):
    data = {"week": [f"W{i}" for i in range(1, 21)], "sales": list(range(20)), "b": list(range(20))}
    r = Client(api_key="good", base_url=server).analyze(data, metric="sales", change_at="W15", time_col="week")
    assert r.verdict == "worked" and r.likely_range == (18.6, 63.2) and "WORKED" in str(r)
    with pytest.raises(CounterfactError) as e:
        Client(api_key="bad", base_url=server).analyze(data, metric="sales", change_at="W15", time_col="week")
    assert e.value.status == 403 and "isn't valid" in e.value.message


def test_requires_key(monkeypatch):
    monkeypatch.delenv("COUNTERFACT_API_KEY", raising=False); monkeypatch.delenv("RAPIDAPI_KEY", raising=False)
    with pytest.raises(CounterfactError):
        Client()
