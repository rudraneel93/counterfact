#!/usr/bin/env python3
"""Check Counterfact's public record yourself, without trusting Counterfact.

Standard library only. Works on any Python 3.9+.

    python counterfact_verify.py receipt r1a2b3c4d5e6     # one receipt, its chain up to the Bitcoin anchor
    python counterfact_verify.py chain                     # the whole record, entry 1 to the latest
    python counterfact_verify.py anchor 2026-11-12         # one daily anchor: text, chain hash, .ots proof

How the record works
--------------------
Every entry stores its JSON body as an exact string and is chained to the entry before it:

    body_hash = sha256(body)
    hash      = sha256(f"{seq}|{kind}|{at}|{prev}|{body_hash}")        # prev = hash of entry seq-1

Changing or deleting any old entry breaks every hash after it. Once a day the latest hash is written into
a short text file whose sha256 is timestamped on Bitcoin with OpenTimestamps. This script recomputes all
of that. For the final step (that the timestamp is in a Bitcoin block) it hands the proof to the official
OpenTimestamps client (`pip install opentimestamps-client`), which checks it against Bitcoin block headers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("COUNTERFACT_API", "https://mastyf-support--counterfact-api-api.us-east.modal.run")
GENESIS = "0" * 64
OTS_MAGIC = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"
PAGE = 100                                            # entries per request (the API allows up to 500; 100 keeps each request short)


def sha256(s) -> str:
    return hashlib.sha256(s.encode() if isinstance(s, str) else s).hexdigest()


def entry_hash(e: dict) -> str:
    return sha256(f"{e['seq']}|{e['kind']}|{e['at']}|{e['prev']}|{e['body_hash']}")


def check_entry(e: dict) -> list[str]:
    """Problems with one entry on its own (empty list = fine)."""
    out = []
    if sha256(e["body"]) != e["body_hash"]:
        out.append(f"entry #{e['seq']}: body does not match body_hash (the content was changed)")
    if entry_hash(e) != e["hash"]:
        out.append(f"entry #{e['seq']}: hash does not match its fields")
    return out


def check_links(entries: list[dict], prev_hash: str | None = None) -> list[str]:
    """entries: consecutive, increasing seq. prev_hash: hash of the entry just before the first one."""
    out = []
    for i, e in enumerate(entries):
        out += check_entry(e)
        want = entries[i - 1]["hash"] if i else prev_hash
        if i and e["seq"] != entries[i - 1]["seq"] + 1:
            out.append(f"gap: entry #{entries[i - 1]['seq']} is followed by #{e['seq']}")
        if want is not None and e["prev"] != want:
            out.append(f"entry #{e['seq']}: does not link to entry #{e['seq'] - 1}")
    return out


def check_ots(ots: bytes, text: str) -> list[str]:
    """The .ots proof must be about exactly this anchor text."""
    head = len(OTS_MAGIC)
    if not ots.startswith(OTS_MAGIC):
        return ["the .ots file is not an OpenTimestamps proof"]
    if ots[head + 1:head + 2] != b"\x08":
        return ["the .ots proof does not use sha256"]
    if ots[head + 2:head + 34] != hashlib.sha256(text.encode()).digest():
        return ["the .ots proof is for a different file than this anchor text"]
    return []


# ------------------------------------------------------------------ network
def get(path: str, raw: bool = False):
    rq = urllib.request.Request(API + path, headers={"User-Agent": "counterfact-verify/1.0"})
    try:
        for attempt in range(3):
            try:
                with urllib.request.urlopen(rq, timeout=120) as r:
                    data = r.read()
                break
            except (TimeoutError, urllib.error.URLError) as ex:
                if isinstance(ex, urllib.error.HTTPError) or attempt == 2:
                    raise
    except urllib.error.HTTPError as ex:
        try:
            msg = json.loads(ex.read()).get("detail", "")
        except Exception:
            msg = ""
        sys.exit(f"API error {ex.code} for {path}: {msg}")
    except (TimeoutError, urllib.error.URLError) as ex:
        sys.exit(f"Couldn't reach the API for {path}: {ex}")
    return data if raw else json.loads(data)


def fetch_range(start: int, end: int) -> list[dict]:
    out = []
    for a in range(start, end + 1, PAGE):
        if end - start >= PAGE:
            print(f"  fetching entries {a} to {min(end, a + PAGE - 1)} of {end}…", file=sys.stderr)
        out += get(f"/v1/ledger/range?start={a}&end={min(end, a + PAGE - 1)}")["entries"]
    return out


def prev_of(seq: int) -> str:
    return GENESIS if seq <= 1 else get(f"/v1/ledger/entry/{seq - 1}")["hash"]


# ------------------------------------------------------------------ commands
def verify_anchor(day: str, save_dir: str = ".") -> tuple[list[str], dict]:
    a = get(f"/v1/ledger/anchor/{urllib.parse.quote(day)}")
    probs = []
    if sha256(a["text"]) != a["file_sha256"]:
        probs.append("anchor text does not match its sha256")
    if f"latest hash: {a['hash']}" not in a["text"] or f"entries: 1 to {a['seq']}" not in a["text"]:
        probs.append("anchor text does not name the hash and entry it claims")
    if get(f"/v1/ledger/entry/{a['seq']}")["hash"] != a["hash"]:
        probs.append(f"entry #{a['seq']} in the record does not have the anchored hash (the record was rewritten)")
    ots = get(f"/v1/ledger/anchor/{urllib.parse.quote(day)}?file=ots", raw=True)
    probs += check_ots(ots, a["text"])
    txt = os.path.join(save_dir, f"anchor-{day}.txt")
    with open(txt, "w", encoding="utf-8", newline="") as f:
        f.write(a["text"])
    with open(txt + ".ots", "wb") as f:
        f.write(ots)
    a["files"] = (txt, txt + ".ots")
    return probs, a


def bitcoin_step(ots_path: str):
    ots = shutil.which("ots")
    if not ots:
        print(f"  Last step, on Bitcoin itself: pip install opentimestamps-client, then\n"
              f"    ots upgrade {ots_path} && ots verify {ots_path}\n"
              f"  (a fresh anchor shows 'pending' for a few hours until its Bitcoin block is mined)")
        return
    subprocess.run([ots, "upgrade", ots_path], check=False)
    r = subprocess.run([ots, "verify", ots_path], capture_output=True, text=True)
    print("  ots verify:", (r.stdout + r.stderr).strip().replace("\n", "\n    "))


def cmd_receipt(rid: str):
    j = get(f"/v1/receipt/{urllib.parse.quote(rid)}")
    e, day = j["entry"], j.get("anchored_in")
    print(f"Receipt {rid}: entry #{e['seq']} ({e['kind']}), recorded {e['at']}")
    print(" ", json.dumps(json.loads(e["body"]), ensure_ascii=False)[:600])
    probs = check_entry(e)
    if not day:
        probs += check_links([e], prev_of(e["seq"]))
        report(probs, f"entry #{e['seq']} is intact and linked. It is not anchored on Bitcoin yet (anchors are made daily).")
        return
    probs_a, a = verify_anchor(day)
    entries = fetch_range(e["seq"], a["seq"])
    probs += check_links(entries, prev_of(e["seq"])) + probs_a
    if entries and entries[-1]["hash"] != a["hash"]:
        probs.append("the chain from this entry does not reach the anchored hash")
    report(probs, f"entry #{e['seq']} is intact, and every entry from it to #{a['seq']} links up to the hash anchored on {day}.")
    bitcoin_step(a["files"][1])


def cmd_chain(start: int, end: int | None):
    head = get("/v1/ledger?limit=1")["head"]
    end = min(end or head["seq"], head["seq"])
    if end < 1:
        sys.exit("The record is empty.")
    entries = fetch_range(start, end)
    probs = check_links(entries, prev_of(start))
    if len(entries) != end - start + 1:
        probs.append(f"expected {end - start + 1} entries, got {len(entries)}")
    if end == head["seq"] and entries and entries[-1]["hash"] != head["hash"]:
        probs.append("the latest entry does not match the published head")
    report(probs, f"all {len(entries)} entries (#{start} to #{end}) are intact and linked.")


def cmd_anchor(day: str):
    probs, a = verify_anchor(day)
    report(probs, f"the {day} anchor covers entries 1 to #{a['seq']}; its text, hash and proof match. Saved {a['files'][0]} and .ots.")
    bitcoin_step(a["files"][1])


def report(probs: list[str], ok_msg: str):
    if probs:
        print("FAILED:")
        for p in probs:
            print("  -", p)
        sys.exit(1)
    print("OK:", ok_msg)


def main(argv=None):
    p = argparse.ArgumentParser(description="Check Counterfact's public record yourself.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("receipt", help="check one receipt and its chain up to the Bitcoin anchor")
    s.add_argument("id")
    s = sub.add_parser("chain", help="check a range of the record (default: all of it)")
    s.add_argument("--from", dest="start", type=int, default=1)
    s.add_argument("--to", dest="end", type=int, default=None)
    s = sub.add_parser("anchor", help="check one daily Bitcoin anchor")
    s.add_argument("day", help="YYYY-MM-DD")
    a = p.parse_args(argv)
    if a.cmd == "receipt":
        cmd_receipt(a.id)
    elif a.cmd == "chain":
        cmd_chain(max(1, a.start), a.end)
    else:
        cmd_anchor(a.day)


if __name__ == "__main__":
    main()
