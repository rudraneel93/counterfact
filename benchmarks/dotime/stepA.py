"""DoTime side: sample episodes from dot-Identifiability-v1, run Do-Over-Time-PFN, dump arrays for Counterfact."""
import sys, numpy as np, torch, random, time
from dotime.benchmarks import load_benchmark
from dotime import baselines
from dotime.evaluation import query_obs_levels
suite_name, cache, ckpt, n, out = sys.argv[1:6]
suite = load_benchmark(suite_name, cache_dir=cache)
eps = list(suite)
random.Random(0).shuffle(eps)
model = baselines.get("DoOverTimePFN", checkpoint=ckpt)
rows, t = [], time.time()
for e in eps:
    if len(rows) >= int(n): break
    iv = e.intervention
    if len(iv.targets) != 1 or e.query_target.numel() != 1: continue
    q, j = int(e.query_time_idx[0]), int(e.query_target[0])
    on = int(iv.times[0])
    if on < 16 or q < on or not torch.isfinite(e.x_int).all() or not torch.isfinite(e.x_obs).all(): continue
    pred = float(model.predict(e)[0])
    lvl = float(query_obs_levels(e)[0])
    rows.append(dict(x_obs=e.x_obs.numpy().astype(np.float64), x_int=e.x_int.numpy().astype(np.float64), onset=on,
                     treated=int(iv.targets[0]), q=q, j=j, y_true=float(e.y_true[0]), y_obs=lvl, dotime_pred=pred,
                     struct=e.structure or "", T=e.length))
    if len(rows) % 100 == 0: print(len(rows), f"{time.time()-t:.0f}s", flush=True)
np.save(out, np.array(rows, dtype=object), allow_pickle=True)
print("saved", len(rows))
