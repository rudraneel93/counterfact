# counterfact

**Did your change really work?** Measure the real effect of a price change, campaign, launch or policy on any time series. You get an honest likely range, and a plain "can't tell yet" when the data can't support a claim.

```bash
pip install counterfact            # add [pandas] and [plot] for DataFrames and charts
```

```python
import pandas as pd
from counterfact import Client

cf = Client(api_key="YOUR_KEY")    # or set COUNTERFACT_API_KEY
df = pd.read_csv("weekly_sales.csv")
r = cf.analyze(df, metric="sales", change_at="2025-10-06", time_col="week",
               comparisons=["sales_other_region", "category_sales"])
print(r)
# sales, change at 2025-10-06: WORKED
#   effect per period: +40.9 (+9.5%)   likely range: +18.6 to +63.2
#   checks: fake change dates flagged 0 of 3, verdict stable when dropping a comparison 3 of 3
print(r.explanation)   # plain-language summary
r.plot()               # needs matplotlib
```

## Run it offline with the open model

No API key, and no data leaves your computer. The first run downloads the open research model ([Rudraneel93/counterfact-v2](https://huggingface.co/Rudraneel93/counterfact-v2), 35 MB, free for non-commercial use) from Hugging Face.

```bash
pip install "counterfact[local]"
```

```python
from counterfact import Local
r = Local().analyze(df, metric="sales", change_at="2025-10-06", time_col="week")
print(r)
```

The hosted `Client` uses the newest production model and adds robustness checks and plain-language explanations.

## What you get back
- `verdict`: "worked", "hurt" or "can't tell yet"
- `effect` per period, `effect_percent`, `likely_range` (holds about 9 times in 10), `total_effect`
- `quick_before_after`: the naive comparison, for contrast
- `robustness`: fake-change-date checks and leave-one-comparison-out checks
- `counterfactual`: what would most likely have happened without the change, period by period

## Keys
- **Counterfact Pro** (₹1,999/month) includes 2,000 API calls: [counterfact-site.vercel.app/#pricing](https://counterfact-site.vercel.app/#pricing). Your Pro access code is your API key. `cf.usage()` shows calls left.
- **RapidAPI:** subscribe at [rapidapi.com/RudraneelDas/api/counterfact](https://rapidapi.com/RudraneelDas/api/counterfact) (free tier with 50 calls a month, pay as you go, or monthly plans), then `Client(rapidapi_key="...")`. Billing is through RapidAPI.

## How it works
Counterfact is a transformer pretrained on millions of synthetic worlds where the true cause and effect is known, and calibrated on 1,200 real Indian and US data windows. An open research version is on Hugging Face: [Rudraneel93/counterfact-v2](https://huggingface.co/Rudraneel93/counterfact-v2).

## Licence
This client is MIT licensed. Use of the API is subject to the Counterfact terms.
