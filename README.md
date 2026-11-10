# Counterfact

**Did your change actually work?** Counterfact estimates what a number (sales, sign-ups, a sector index, enrolment) would most likely have done *without* a change, such as a price cut, campaign or policy, and gives the difference with a likely range. It is a pretrained model, so nothing is fitted to your data: you send your series and get an answer in seconds.

Every result can come with a **receipt** in a public, tamper-evident record that is timestamped on Bitcoin daily. This repository holds everything you need to use Counterfact and to **check its record without trusting us**.

[Website](https://counterfact-site.vercel.app) · [Public record](https://counterfact-site.vercel.app/verify) · [Open model on Hugging Face](https://huggingface.co/Rudraneel93/counterfact-v2) · [PyPI](https://pypi.org/project/counterfact/) · [API](https://rapidapi.com/RudraneelDas/api/counterfact)

## What's here

| Folder | What it is |
|---|---|
| [`verify/`](verify) | A stand-alone checker for the public record (Python standard library only). Recomputes every hash, walks the chain to the daily Bitcoin anchor, then hands the proof to the OpenTimestamps client. |
| [`python/`](python) | The `counterfact` Python package: a client for the API, plus `Local()`, which runs the open model on your own machine. |
| [`spreadsheets/`](spreadsheets) | `=CF_EFFECT()` for Google Sheets and `=CF.EFFECT()` for Excel. |
| [`teaching/`](teaching) | A 60–90 minute classroom lab: score before-vs-after, difference-in-differences and Counterfact on 300 simulated worlds where the true effect is known. |
| [`benchmarks/dotime/`](benchmarks/dotime) | Scripts and raw results for our run on DoTime's independent `dot-Identifiability-v1` suite (800 episodes). |

## Quick start

```bash
pip install counterfact            # API client, no dependencies
pip install "counterfact[local]"   # + run the open model locally (torch, ~35 MB download)
```

```python
import pandas as pd
from counterfact import Local
df = pd.read_csv("weekly_orders.csv")          # columns: week, orders, region_b, region_c
r = Local().analyze(df, metric="orders", change_at="2026-03-02", time_col="week",
                    comparisons=["region_b", "region_c"])
print(r.verdict, r.effect, r.likely_range)
```

## Check the public record yourself

```bash
python verify/counterfact_verify.py receipt r1a2b3c4d5e6   # one receipt, chained to its Bitcoin anchor
python verify/counterfact_verify.py chain                   # every entry, 1 to the latest
python verify/counterfact_verify.py anchor 2026-11-12       # one daily anchor and its .ots proof
```

Each entry stores its JSON body as an exact string and is chained to the one before:

```
body_hash = sha256(body)
hash      = sha256(f"{seq}|{kind}|{at}|{prev}|{body_hash}")
```

Changing, deleting or back-dating any entry breaks every hash after it. Once a day the latest hash goes into a short text file whose sha256 is timestamped on Bitcoin with [OpenTimestamps](https://opentimestamps.org). Customer data never goes in the record, only a sha256 fingerprint of it.

What's recorded:
- every market-board event, written down **when it is detected, before its effect is known**, then its result;
- random "nothing happened" days measured the same way, so the false-alarm rate is public;
- every paid report, API result, pre-registered change and Claim Check.

## How well it works, including where it doesn't

Measured on 1,200 real Indian and US windows (with leave-one-panel-out calibration):
- **The 90% range held about 90% of the time**, with about 10% false alarms on placebo dates.
- **Power depends on effect size and noise.** It detects 93% of effects of 2+ standard deviations but only 46% of effects between 0.5 and 1. On the noisiest third of series, detection falls to 48% (79% on the smoothest third). Small effects on noisy data often come back as "can't tell", which is the correct answer when the data can't separate them.
- **On DoTime's `dot-Identifiability-v1`** (800 episodes, 9 causal structures), with only the outcome and treated series as input:
  - the open model's 90% range covered the true effect 93% of the time;
  - it got the sign right in 82.7% of episodes;
  - a naive before/after comparison got the sign right in 83%.

  DoTime forecasts *before* an intervention, while Counterfact measures *after* it, so this is not a head-to-head on the same task. See [`benchmarks/dotime`](benchmarks/dotime).

## Licences

- Code in this repository: **MIT** (see `LICENSE`).
- Open model weights (`counterfact-v2` on Hugging Face): **CC BY-NC 4.0**. Free for research and teaching; for commercial use, use the API.
- Teaching dataset (`counterfact-worlds`): CC BY 4.0.

Questions, bugs, or a result you think is wrong: open an issue or email rudraneel93@gmail.com.
