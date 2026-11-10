# Independent benchmark: DoTime dot-Identifiability-v1 (v1.2.0)

1. `stepA.py` (in an environment with `pip install 'dotime[models,evaluation]'`) samples 800 episodes with seed 0 and saves the arrays. It also stores DoTime's own forecast for reference, but we don't compare against it, because it answers a different question.
2. `stepB.py <episodes.npy> <out.json> [model.pt]` runs Counterfact on each episode. Inputs: the outcome and the intervened series. It produces the raw per-step 90% range at the query step and prints coverage and error by structure.

- `ident_800_results_v2.json`: open model (this repo, v2).
- `ident_800_results.json`: production model (v4).
- `summary.json`: per-structure summary.

The `cf_treat` fields are what we report. The `cf_treat_clean` fields also give the model untouched series as comparisons. Those series were picked using the simulator's ground truth, so we don't report them.
