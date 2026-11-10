# counterfact_verify.py

Checks Counterfact's public record without trusting Counterfact. Python 3.9+, standard library only.

```bash
python counterfact_verify.py receipt <receipt id>   # e.g. from a report, a badge or a Claim Check page
python counterfact_verify.py chain [--from N] [--to M]
python counterfact_verify.py anchor YYYY-MM-DD
```

The script:
1. recomputes each entry's body and record hash;
2. checks every link from your entry up to the next daily anchor;
3. checks that the anchor text names that hash and that the `.ots` proof is for exactly that text.

The last step, confirming the proof is in a Bitcoin block, runs the official [OpenTimestamps](https://opentimestamps.org) client if it is installed (`pip install opentimestamps-client`). Otherwise the script prints the two commands to run. A fresh anchor shows "pending" for a few hours until its block is mined.

Set `COUNTERFACT_API` to check a mirror or a self-hosted copy.
