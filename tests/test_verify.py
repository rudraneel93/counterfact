"""Offline tests for the verifier: build a small record, then tamper with it in every way that matters."""
import copy, hashlib, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "verify"))
import counterfact_verify as V


def make_chain(n=5):
    out, prev = [], V.GENESIS
    for i in range(1, n + 1):
        body = json.dumps({"verdict": "worked", "i": i}, sort_keys=True, separators=(",", ":"))
        e = {"seq": i, "kind": "receipt.report", "at": f"2026-11-1{i % 10}T00:00:00Z", "prev": prev,
             "body": body, "body_hash": hashlib.sha256(body.encode()).hexdigest()}
        e["hash"] = hashlib.sha256(f"{i}|{e['kind']}|{e['at']}|{prev}|{e['body_hash']}".encode()).hexdigest()
        out.append(e)
        prev = e["hash"]
    return out


def test_intact_chain_passes():
    assert V.check_links(make_chain(), V.GENESIS) == []


def test_edited_body_is_caught():
    c = make_chain(); c[2]["body"] = c[2]["body"].replace("worked", "hurt")
    assert any("body does not match" in p for p in V.check_links(c, V.GENESIS))


def test_rehashed_edit_breaks_the_next_link():
    c = make_chain(); e = c[2]
    e["body"] = e["body"].replace("worked", "hurt"); e["body_hash"] = V.sha256(e["body"]); e["hash"] = V.entry_hash(e)
    probs = V.check_links(c, V.GENESIS)
    assert probs == ["entry #4: does not link to entry #3"]


def test_deleted_entry_is_caught():
    c = make_chain(); del c[2]
    assert any("gap" in p for p in V.check_links(c, V.GENESIS))


def test_ots_must_match_anchor_text():
    text = "Counterfact public record\ndate: 2026-11-12\n"
    good = V.OTS_MAGIC + b"\x01\x08" + hashlib.sha256(text.encode()).digest() + b"\xf0proof"
    assert V.check_ots(good, text) == []
    assert V.check_ots(good, text + "x")
    assert V.check_ots(b"junk", text)
