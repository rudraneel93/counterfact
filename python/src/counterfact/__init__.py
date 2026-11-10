"""Counterfact: did your change really work?

    from counterfact import Client
    cf = Client()                       # reads COUNTERFACT_API_KEY
    r = cf.analyze(df, metric="sales", change_at="2025-10-06", time_col="week")
    print(r)                            # verdict, effect, likely range, checks

    from counterfact import Local       # pip install "counterfact[local]"
    r = Local().analyze(df, metric="sales", change_at="2025-10-06", time_col="week")   # runs the open model offline
"""
from .client import Client, CounterfactError, Result
from .local import Local

__all__ = ["Client", "Local", "Result", "CounterfactError"]
__version__ = "0.2.0"
