"""Builds counterfact_teaching_kit.ipynb: classroom exercises on worlds with known causal effects."""
import json, pathlib

cells = []
md = lambda s: cells.append({"cell_type": "markdown", "metadata": {}, "source": s.strip()})
code = lambda s: cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s.strip()})

md("""
# Did it work? A hands-on lab in causal inference for time series

**Counterfact teaching kit** · free for classrooms · about 60–90 minutes

In real life you never see what would have happened without a change, so you can't check whether an analysis got it right. In this lab you can: every "world" below was simulated **twice from the same random start**, once with a change and once without. The difference is the true effect.

You'll score three methods on the same 300 worlds:
1. **Before vs after**: the comparison most reports use
2. **Difference-in-differences** against comparison series
3. **Counterfact**: a pretrained model that predicts what would have happened anyway

and score each one on **error**, **coverage** (does its 90% range contain the truth 90% of the time?) and **false alarms** (does it claim an effect in worlds where there was none?).

Data: [Rudraneel93/counterfact-worlds](https://huggingface.co/datasets/Rudraneel93/counterfact-worlds) (CC BY 4.0). Model: [Rudraneel93/counterfact-v2](https://huggingface.co/Rudraneel93/counterfact-v2) (CC BY-NC 4.0, fine for teaching).
""")
code("""
!pip -q install "counterfact[local]" pandas pyarrow matplotlib huggingface_hub
""")
code("""
import numpy as np, pandas as pd, matplotlib.pyplot as plt
worlds = pd.read_parquet("hf://datasets/Rudraneel93/counterfact-worlds/test.parquet")
W = worlds.sample(300, random_state=0).reset_index(drop=True)
print(len(W), "worlds;", int(W.no_effect.sum()), "of them have NO effect")
W.head()
""")
md("""
## 1. Look at one world

`target` is what you'd observe. `counterfactual` is the twin world without the change: normally invisible. `t0` is the first period after the change.
""")
code("""
w = W.iloc[3]
y, cf, t0 = np.asarray(w.target), np.asarray(w.counterfactual), int(w.t0)
plt.figure(figsize=(9, 3))
plt.plot(y, label="what happened (target)")
plt.plot(range(t0, len(y)), cf[t0:], "--", label="without the change (hidden in real life)")
plt.axvline(t0 - .5, color="grey", ls=":")
plt.legend(); plt.title(f"true average effect after the change: {w.true_effect_mean:+.2f}"); plt.show()
""")
md("""
## 2. A scoring function

Every method returns `(estimate, low, high)`: its estimate of the average effect after `t0` and a 90% range. We compare effects in units of the target's typical size before the change, so worlds are comparable.
""")
code("""
def score(method, worlds=W):
    rows = []
    for _, w in worlds.iterrows():
        y = np.asarray(w.target, float); t0 = int(w.t0)
        X = np.vstack(w.covariates).astype(float) if len(w.covariates) else np.zeros((0, len(y)))
        est, lo, hi = method(y, X, t0)
        sd = y[:t0].std() or 1.0
        rows.append(dict(err=abs(est - w.true_effect_mean) / sd,
                         covered=lo <= w.true_effect_mean <= hi,
                         alarm=(lo > 0 or hi < 0), null=bool(w.no_effect)))
    r = pd.DataFrame(rows)
    return pd.Series({"error (sd units)": r.err.mean(), "coverage of 90% range": r.covered.mean(),
                      "false alarms (no-effect worlds)": r[r.null].alarm.mean()}).round(3)
""")
md("""
## 3. Method 1: before vs after

The average after the change minus the average of the 8 periods before it, with a textbook 90% range from the spread of the data.

**Exercise 3a.** Before running it, predict: will its 90% range hold 90% of the time? Why or why not?
""")
code("""
def before_after(y, X, t0, k=8):
    pre, post = y[max(0, t0 - k):t0], y[t0:]
    est = post.mean() - pre.mean()
    se = np.sqrt(pre.var(ddof=1) / len(pre) + post.var(ddof=1) / len(post))
    return est, est - 1.645 * se, est + 1.645 * se

score(before_after)
""")
md("""
**Exercise 3b.** Find a world where before vs after is badly wrong and plot it. What is it mistaking for the effect (trend, season, a shock)?
""")
code("""
# your code here
""")
md("""
## 4. Method 2: difference-in-differences

Compare the change in the target with the change in the comparison series over the same periods. Here we use the average of the (standardised) comparison series.

**Exercise 4a.** Complete `did` so it returns an estimate and a 90% range. Hint: the residual `y - comparison` before `t0` tells you how noisy the gap is.
""")
code("""
def did(y, X, t0):
    if len(X) == 0:
        return before_after(y, X, t0)
    mu, sd = X[:, :t0].mean(1, keepdims=True), X[:, :t0].std(1, keepdims=True) + 1e-9
    comp = ((X - mu) / sd).mean(0) * y[:t0].std() + y[:t0].mean()   # comparison on the target's scale
    gap = y - comp
    est = gap[t0:].mean() - gap[:t0].mean()
    # TODO: replace this naive range with one based on how much `gap` moves before t0
    se = gap[:t0].std(ddof=1) / np.sqrt(len(gap) - t0)
    return est, est - 1.645 * se, est + 1.645 * se

score(did)
""")
md("""
**Exercise 4b.** The comparison series in some worlds were *slightly affected by the change too* (spillover), as often happens in real life. How would spillover bias DiD? Which way?
""")
md("""
## 5. Method 3: Counterfact (pretrained, no fitting)

The model was trained on millions of worlds like these, so it has learned what "would have happened anyway" looks like. It predicts that path directly.

> Fair-test note: because it was trained on worlds *from the same simulator*, this test flatters it. Its real-data results (1,200 real Indian and US windows) are on the model card: coverage 90%, about 10% false alarms.
""")
code("""
from counterfact import Local
cf = Local()   # downloads the open model once (~35 MB)

def counterfact_method(y, X, t0):
    cols = {"y": y.tolist(), **{f"c{i}": x.tolist() for i, x in enumerate(X)}}
    r = cf.analyze(cols, metric="y", change_at=t0 + 1)          # change_at = 1-based row of the first period after
    lo, hi = r.likely_range
    return r.effect, lo, hi

score(counterfact_method, W.head(120))   # 120 worlds keeps it under a few minutes on a laptop
""")
md("""
## 6. Compare and discuss

**Exercise 6a.** Put the three scores in one table. Which method would you trust to tell a CEO "the price cut worked"? Which would you trust to say "it did nothing"?

**Exercise 6b.** Split the scores by `kind` (`impact` vs `do_treatment`) and by effect size (`true_effect_mean_sd_units`). Where does each method break?

**Exercise 6c (project).** Build your own method (synthetic control, a regression, a Bayesian structural time series) and score it with `score()`. Can you beat the false-alarm rate without losing coverage?

**For instructors:** worked solutions and free classroom access: email rudraneel93@gmail.com from your institution address. More at [counterfact-site.vercel.app/teach.html](https://counterfact-site.vercel.app/teach.html).
""")

nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
      "language_info": {"name": "python"}, "colab": {"provenance": []}}, "nbformat": 4, "nbformat_minor": 5}
out = pathlib.Path(__file__).parent / "counterfact_teaching_kit.ipynb"
out.write_text(json.dumps(nb, indent=1))
print("wrote", out)
