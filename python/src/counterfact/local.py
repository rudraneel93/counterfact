"""Run the open Counterfact model on your own machine: no API key, no data leaves your computer.

    pip install "counterfact[local]"
    from counterfact import Local
    cf = Local()                        # downloads the open model from Hugging Face once (35 MB), then cached
    r = cf.analyze(df, metric="sales", change_at="2025-10-06", time_col="week")

The open model is the research version (v2, CC BY-NC 4.0, non-commercial use). The hosted `Client`
uses the newest production model and adds robustness checks and plain-language explanations.
"""
from __future__ import annotations

import sys

from .client import CounterfactError, Result

REPO = "Rudraneel93/counterfact-v2"


class Local:
    def __init__(self, repo: str = REPO, revision: str | None = None, device: str = "cpu"):
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            raise ImportError('Local mode needs extra packages: pip install "counterfact[local]"') from None
        self.path = snapshot_download(repo, revision=revision)
        if self.path not in sys.path:
            sys.path.insert(0, self.path)
        from counterfact_open import estimate, load
        self._estimate = estimate
        self.model = load(f"{self.path}/model.pt", device=device)

    def analyze(self, data, metric: str, change_at, comparisons: list[str] | None = None,
                time_col: str | None = None) -> Result:
        """Same arguments as Client.analyze: change_at is a value from time_col or a 1-based row number."""
        import numpy as np
        if hasattr(data, "columns"):
            cols = {str(c): data[c].tolist() for c in data.columns}
        else:
            cols = {str(k): list(v) for k, v in dict(data).items()}
        index = [str(v) for v in cols[time_col]] if time_col else None
        num = {k: v for k, v in cols.items() if k != time_col and all(isinstance(x, (int, float)) for x in v)}
        if metric not in num:
            raise CounterfactError(400, f"No numeric column named {metric!r}. Available: {', '.join(num)}")
        if index and str(change_at) in index:
            t0 = index.index(str(change_at))
        else:
            try:
                t0 = int(change_at) - 1
            except (TypeError, ValueError):
                raise CounterfactError(400, f"change_at {change_at!r} is not in {time_col!r} and is not a row number") from None
        comps = comparisons if comparisons is not None else [k for k in num if k != metric]
        y = np.asarray(num[metric], float)
        X = np.asarray([num[c] for c in comps], float) if comps else None
        e = self._estimate(self.model, y, t0, X, cov_names=comps or None, index=index)
        real = e.effect_lo90 > 0 or e.effect_hi90 < 0
        verdict = ("worked" if e.effect_mean > 0 else "hurt") if real else "can't tell yet"
        pre = float(y[max(0, t0 - len(e.observed)):t0].mean())
        naive = float(np.mean(e.observed)) - pre
        return Result(metric=metric, change_at=str(change_at), verdict=verdict, effect=e.effect_mean,
                      effect_percent=None if e.relative_effect is None else 100 * e.relative_effect,
                      likely_range=(e.effect_lo90, e.effect_hi90), total_effect=e.cumulative_effect,
                      chance_positive=e.p_positive, quick_before_after={"effect_per_period": naive},
                      robustness={}, comparisons_used=list(e.used_covariates), explanation=e.summary(),
                      counterfactual={"index": e.post_index, "observed": e.observed, "median": e.cf_median,
                                      "lo90": e.cf_lo90, "hi90": e.cf_hi90},
                      raw={"engine": "local open model " + REPO})
