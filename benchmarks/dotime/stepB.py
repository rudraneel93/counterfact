"""python stepB.py episodes.npy results.json [model.pt]

Runs Counterfact on each DoTime episode. With no model path it downloads the open model
(huggingface.co/Rudraneel93/counterfact-v2, CC BY-NC 4.0); the published v2 results come from that.
"""
import sys, numpy as np, json, collections
from huggingface_hub import snapshot_download        # pip install torch numpy huggingface_hub
REPO = snapshot_download("Rudraneel93/counterfact-v2")
sys.path.insert(0, REPO)
from counterfact_open import load, estimate
M = load(sys.argv[3] if len(sys.argv) > 3 else f"{REPO}/model.pt")
rows = np.load(sys.argv[1], allow_pickle=True)
out = []
for r in rows:
    xo, xi, t0, j, k, q = r["x_obs"], r["x_int"], r["onset"], r["j"], r["treated"], r["q"]
    if j == k: continue
    y = xi[:, j]; tr = xi[:, k]
    others = [i for i in range(xi.shape[1]) if i not in (j, k)]
    clean = [i for i in others if np.allclose(xi[t0:, i], xo[t0:, i])]   # domain-knowledge proxy: series the change can't reach
    res = {"struct": r["struct"], "true": r["y_true"] - r["y_obs"], "dotime": r["dotime_pred"] - r["y_obs"],
           "naive": y[q] - y[max(0, t0 - 8):t0].mean(), "sd": float(np.std(np.diff(y[:t0]))) or 1.0}
    for name, cov in (("cf_treat", []), ("cf_treat_clean", clean)):
        try:
            e = estimate(M, y, t0, xi[:, cov].T if cov else None, tr)
            i = q - t0
            if i >= len(e.cf_median): raise ValueError("query beyond window")
            res[name] = y[q] - e.cf_median[i]
            res[name + "_lo"], res[name + "_hi"] = y[q] - e.cf_hi90[i], y[q] - e.cf_lo90[i]
        except Exception as ex:
            res[name] = None
    out.append(res)
json.dump(out, open(sys.argv[2], "w"))
def report(sel, label):
    print(f"\n== {label}: {len(sel)} episodes")
    T = np.array([x["true"] for x in sel]); sd = np.array([x["sd"] for x in sel]); m = np.abs(T) >= 0.1
    for name in ("naive", "dotime", "cf_treat", "cf_treat_clean"):
        ok = np.array([x.get(name) is not None for x in sel]); P = np.array([x.get(name) if x.get(name) is not None else np.nan for x in sel], float)
        acc = (np.sign(P[m & ok]) == np.sign(T[m & ok])).mean()
        mae = np.nanmean(np.abs(P - T)[ok] / sd[ok])
        line = f"{name:15s} direction acc {acc:.3f} (n={int((m&ok).sum())})  effect err (step-sd units) {mae:.2f}"
        if name.startswith("cf"):
            lo = np.array([x.get(name + "_lo", np.nan) or np.nan for x in sel], float); hi = np.array([x.get(name + "_hi", np.nan) or np.nan for x in sel], float)
            line += f"  90% coverage {np.mean((lo[ok] <= T[ok]) & (T[ok] <= hi[ok])):.2f}"
        print(line)
report(out, "all")
by = collections.defaultdict(list)
for x in out: by[x["struct"]].append(x)
for s, v in sorted(by.items()): report(v, s)
