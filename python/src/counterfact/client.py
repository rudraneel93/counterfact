"""Thin client for the Counterfact API (standard library only; pandas and matplotlib optional)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

DEFAULT_URL = "https://mastyf-support--counterfact-api-api.us-east.modal.run"
RAPIDAPI_HOST = "counterfact.p.rapidapi.com"


class CounterfactError(Exception):
    """Raised when the API refuses a request (bad input, missing or used-up key, ...)."""

    def __init__(self, status: int, message: str):
        super().__init__(f"[{status}] {message}")
        self.status, self.message = status, message


@dataclass
class Result:
    """The answer for one change. Effects are per period, in the metric's own units."""
    metric: str
    change_at: str
    verdict: str                       # "worked" | "hurt" | "can't tell yet"
    effect: float                      # per period
    effect_percent: float | None
    likely_range: tuple[float, float]  # holds about 9 times in 10
    total_effect: float
    chance_positive: float
    quick_before_after: dict
    robustness: dict
    comparisons_used: list[str]
    explanation: str
    counterfactual: dict
    raw: dict = field(repr=False, default_factory=dict)

    @classmethod
    def from_api(cls, d: dict) -> "Result":
        s = d["summary"]
        return cls(metric=s["metric"], change_at=s["change_at"], verdict=s["verdict"],
                   effect=s["effect_per_period"], effect_percent=s["effect_percent"],
                   likely_range=tuple(s["likely_range_per_period"]), total_effect=s["total_effect_over_period"],
                   chance_positive=s["chance_effect_is_positive"], quick_before_after=s["quick_before_after"],
                   robustness=s["robustness"], comparisons_used=s["comparisons_used"],
                   explanation=d.get("explanation", ""), counterfactual=d.get("counterfactual", {}), raw=d)

    def __str__(self) -> str:
        pct = f" ({self.effect_percent:+.1f}%)" if self.effect_percent is not None else ""
        lo, hi = self.likely_range
        out = (f"{self.metric}, change at {self.change_at}: {self.verdict.upper()}\n"
               f"  effect per period: {self.effect:+,.3g}{pct}   likely range: {lo:+,.3g} to {hi:+,.3g}")
        if self.robustness:
            out += (f"\n  checks: fake change dates flagged {self.robustness.get('fake_dates_flagged')}, "
                    f"verdict stable when dropping a comparison {self.robustness.get('verdict_stable_when_dropping')}")
        return out

    def to_dict(self) -> dict:
        return self.raw

    def plot(self, ax=None):
        """Plot what happened vs what would have happened anyway (needs matplotlib)."""
        import matplotlib.pyplot as plt
        cf = self.counterfactual
        ax = ax or plt.subplots(figsize=(9, 4))[1]
        x = list(range(len(cf["observed"])))
        ax.plot(x, cf["observed"], color="#0891b2", lw=2, label="What happened")
        ax.plot(x, cf["median"], "--", color="#7c5cff", lw=2, label="What would have happened anyway")
        ax.fill_between(x, cf["lo90"], cf["hi90"], color="#7c5cff", alpha=0.18, label="Likely range")
        step = max(1, len(x) // 8)
        ax.set_xticks(x[::step], [str(v) for v in cf["index"][::step]], rotation=30, fontsize=8)
        ax.set_title(f"{self.metric} after the change at {self.change_at}: {self.verdict}")
        ax.legend(fontsize=8)
        return ax


class Client:
    """Counterfact API client.

    Client(api_key=...)            a Counterfact Pro key (or set COUNTERFACT_API_KEY)
    Client(rapidapi_key=...)       a RapidAPI key (or set RAPIDAPI_KEY), billed through RapidAPI
    """

    def __init__(self, api_key: str | None = None, rapidapi_key: str | None = None,
                 base_url: str | None = None, timeout: float = 120.0):
        self.api_key = api_key or os.environ.get("COUNTERFACT_API_KEY")
        self.rapidapi_key = rapidapi_key or os.environ.get("RAPIDAPI_KEY")
        if self.rapidapi_key and not base_url:
            base_url = f"https://{RAPIDAPI_HOST}"
        self.base_url = (base_url or os.environ.get("COUNTERFACT_URL") or DEFAULT_URL).rstrip("/")
        self.timeout = timeout
        if not (self.api_key or self.rapidapi_key):
            raise CounterfactError(401, "No key. Pass api_key=... (Counterfact Pro) or rapidapi_key=..., "
                                        "or set COUNTERFACT_API_KEY. Get a key at https://counterfact-site.vercel.app/#pricing")

    def _headers(self) -> dict:
        h = {"content-type": "application/json", "user-agent": "counterfact-python/0.1.1"}
        if self.rapidapi_key:
            h.update({"x-rapidapi-key": self.rapidapi_key, "x-rapidapi-host": RAPIDAPI_HOST})
        else:
            h["x-api-key"] = self.api_key
        return h

    def _call(self, method: str, path: str, body: Any = None) -> dict:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base_url + path, data=data, method=method, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read())
                msg = body.get("detail") or body.get("message") or e.reason   # our API uses "detail", RapidAPI "message"
            except Exception:
                msg = str(e.reason)
            if e.code == 403 and "not subscribed" in str(msg).lower():
                msg = f"{msg} Subscribe to a plan (the free Basic plan works) on Counterfact's RapidAPI page."
            raise CounterfactError(e.code, str(msg)) from None

    def analyze(self, data, metric: str, change_at, comparisons: list[str] | None = None,
                time_col: str | None = None, changed_column: str = "") -> Result:
        """Measure the effect of a change on `metric`.

        data:        a pandas DataFrame (rows in time order) or a dict {name: list of numbers}
        change_at:   first period after the change: a value from `time_col`, or a 1-based row number
        comparisons: columns the change could NOT have affected (default: every other numeric column)
        time_col:    optional column with dates or period labels
        """
        index = None
        if hasattr(data, "to_dict") and hasattr(data, "columns"):        # pandas DataFrame
            df = data
            if time_col:
                index = [str(v) for v in df[time_col].tolist()]
            series = {str(c): [float(v) for v in df[c].tolist()] for c in df.columns
                      if c != time_col and str(df[c].dtype)[:3] in ("int", "flo", "uin")}
        else:
            series = {str(k): [float(v) for v in vals] for k, vals in dict(data).items() if k != time_col}
            if time_col and time_col in dict(data):
                index = [str(v) for v in dict(data)[time_col]]
        if metric not in series:
            raise CounterfactError(400, f"No numeric column named {metric!r}. Available: {', '.join(series)}")
        body = {"series": series, "metric": metric, "change_at": str(change_at),
                "comparisons": comparisons, "changed_column": changed_column, "index": index}
        return Result.from_api(self._call("POST", "/v2/analyze", body))

    def usage(self) -> dict:
        """Plan, expiry and API calls left on a Counterfact Pro key."""
        return self._call("GET", "/v2/usage")
