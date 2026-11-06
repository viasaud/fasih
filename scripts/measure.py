#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure every candidate feature on paired human and AI Arabic text.

This is how the rules in SKILL.md were chosen. Rerun it on any corpus you may use.

    python3 scripts/measure.py --alhd ALHD.csv --sources SANAD ANAD --split dev
    python3 scripts/measure.py --alhd ALHD.csv --sources SANAD ANAD --split holdout
    python3 scripts/measure.py --alhd ALHD.csv --show tr_bishakl --n 20

--alhd expects the ALHD columns: text, generator, source, document_id. Documents are
paired on (source, document_id) and split in half by a hash of that pair, so rules are
chosen on one half and reported on the other.

Reported for each feature:
  H, AI     rate per 1000 Arabic words (pooled over documents)
  R         AI rate / human rate
  CI        95% bootstrap interval for R, resampling document pairs
  by source R inside each source: a direction that flips between sources is not stable
  delta     paired Cliff's delta: (pairs where AI>human - pairs where AI<human) / pairs
"""
import argparse
import csv
import json
import random
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from arabic import COMPILED, SENTENCE_START, doc_features, protected_text, split_sents, paragraph_blocks

csv.field_size_limit(10 ** 9)


def load_pairs(path, sources, generator=None, min_words=120):
    docs = {}
    # utf-8-sig and the NUL filter: ALHD_Main.csv has a byte-order mark and stray NUL bytes.
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        for row in csv.DictReader(line.replace("\0", "") for line in f):
            if sources and row["source"] not in sources:
                continue
            key = (row["source"], row["document_id"])
            side = "human" if row["generator"] == "HUMAN" else "ai"
            if side == "ai" and generator and row["generator"] != generator:
                continue
            docs.setdefault(key, {})[side] = row["text"]
    pairs = [(k, v["human"], v["ai"]) for k, v in docs.items()
             if "human" in v and "ai" in v]
    return pairs


def in_split(key, split):
    if split == "all":
        return True
    bucket = zlib.crc32(f"{key[0]}|{key[1]}".encode()) % 2
    return bucket == (0 if split == "dev" else 1)


def rate_ratio(ai_hits, ai_words, h_hits, h_words):
    a = ai_hits / ai_words if ai_words else 0
    h = h_hits / h_words if h_words else 0
    return a / h if h else float("inf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alhd", required=True)
    ap.add_argument("--sources", nargs="*", default=["SANAD", "ANAD"])
    ap.add_argument("--generator", default=None)
    ap.add_argument("--split", choices=["dev", "holdout", "all"], default="dev")
    ap.add_argument("--limit", type=int, default=0, help="use at most this many document pairs")
    ap.add_argument("--min-words", type=int, default=120)
    ap.add_argument("--boot", type=int, default=400)
    ap.add_argument("--show", help="print matches for one feature instead of measuring")
    ap.add_argument("--side", choices=["human", "ai"], default="ai")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--json", help="write results to this JSON file")
    ap.add_argument("--composite", help="comma-separated features: share of documents above density cut-offs")
    args = ap.parse_args()

    pairs = [p for p in load_pairs(args.alhd, set(args.sources), args.generator)
             if in_split(p[0], args.split)]
    if args.limit and len(pairs) > args.limit:
        # Stable sample: the same documents are used for every generator.
        pairs.sort(key=lambda p: zlib.crc32(f"sample|{p[0][0]}|{p[0][1]}".encode()))
        pairs = pairs[:args.limit]

    if args.show:
        rng = random.Random(7)
        rng.shuffle(pairs)
        pat = COMPILED[args.show]
        shown = 0
        for key, h, a in pairs:
            text = h if args.side == "human" else a
            prose = protected_text(text)
            targets = split_sents(prose) if args.show in SENTENCE_START else [prose]
            for t in targets:
                for m in pat.finditer(t):
                    s = max(0, m.start() - 25)
                    print(f"{key[0]}:{key[1]}  …{t[s:m.end() + 30]}…".replace("\n", " "))
                    shown += 1
                    break
                if shown >= args.n:
                    return
        return

    rows = []
    for key, h, a in pairs:
        fh, fa = doc_features(h), doc_features(a)
        if fh["words"] < args.min_words or fa["words"] < args.min_words:
            continue
        rows.append((key[0], fh, fa))
    n = len(rows)
    print(f"{n} document pairs (min {args.min_words} words each), split={args.split}, "
          f"sources={args.sources}")
    hw = sum(r[1]["words"] for r in rows)
    aw = sum(r[2]["words"] for r in rows)
    print(f"human {hw} words, AI {aw} words\n")

    sources = sorted({r[0] for r in rows})
    rng = random.Random(42)
    idx_samples = [rng.choices(range(n), k=n) for _ in range(args.boot)]

    out = {}
    print(f"{'feature':<20}{'H/1k':>8}{'AI/1k':>8}{'R':>7}{'CI low':>8}{'CI hi':>8}"
          + "".join(f"{s:>8}" for s in sources) + f"{'delta':>8}{'H docs':>8}{'AI docs':>8}")
    print("-" * 100)
    for k in COMPILED:
        hh = [r[1]["counts"][k] for r in rows]
        ah = [r[2]["counts"][k] for r in rows]
        hws = [r[1]["words"] for r in rows]
        aws = [r[2]["words"] for r in rows]
        R = rate_ratio(sum(ah), aw, sum(hh), hw)
        boots = []
        for sample in idx_samples:
            boots.append(rate_ratio(sum(ah[i] for i in sample), sum(aws[i] for i in sample),
                                    sum(hh[i] for i in sample), sum(hws[i] for i in sample)))
        boots.sort()
        lo, hi = boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]
        by = {}
        for s in sources:
            ii = [i for i, r in enumerate(rows) if r[0] == s]
            by[s] = rate_ratio(sum(ah[i] for i in ii), sum(aws[i] for i in ii),
                               sum(hh[i] for i in ii), sum(hws[i] for i in ii))
        delta = 0
        for i in range(n):
            da, dh = ah[i] / aws[i], hh[i] / hws[i]
            delta += (da > dh) - (da < dh)
        delta /= n
        hdocs = sum(1 for v in hh if v) / n * 100
        adocs = sum(1 for v in ah if v) / n * 100
        out[k] = dict(human=sum(hh) / hw * 1000, ai=sum(ah) / aw * 1000, R=R, lo=lo, hi=hi,
                      by_source=by, delta=delta, human_docs=hdocs, ai_docs=adocs,
                      human_hits=sum(hh), ai_hits=sum(ah))
        fmt = lambda x: "inf" if x == float("inf") else f"{x:.2f}"
        print(f"{k:<20}{sum(hh) / hw * 1000:>8.2f}{sum(ah) / aw * 1000:>8.2f}{fmt(R):>7}"
              f"{fmt(lo):>8}{fmt(hi):>8}" + "".join(f"{fmt(by[s]):>8}" for s in sources)
              + f"{delta:>8.2f}{hdocs:>7.0f}%{adocs:>7.0f}%")

    if args.composite:
        keys = args.composite.split(",")
        def per_k(f):
            return sum(f["counts"][k] for k in keys) / f["words"] * 1000
        hv = sorted(per_k(r[1]) for r in rows)
        av = sorted(per_k(r[2]) for r in rows)
        higher = sum((per_k(r[2]) > per_k(r[1])) - (per_k(r[2]) < per_k(r[1])) for r in rows) / n
        for cut in (0.0, 2.0, 5.0, 10.0):
            print(f"composite: docs above {cut:>4}/1k  human {sum(v > cut for v in hv) / n * 100:5.1f}%"
                  f"   AI {sum(v > cut for v in av) / n * 100:5.1f}%")
        print(f"composite: median/1k human {hv[n // 2]:.2f}  AI {av[n // 2]:.2f}  paired delta {higher:.2f}")
        out["_composite"] = dict(human_median=hv[n // 2], ai_median=av[n // 2], delta=higher,
                                 over={str(c): [sum(v > c for v in hv) / n * 100, sum(v > c for v in av) / n * 100]
                                       for c in (0.0, 2.0, 5.0, 10.0)})

    print("\nstructure (median per document, paired delta)")
    print(f"{'feature':<20}{'H':>9}{'AI':>9}{'delta':>8}")
    print("-" * 46)
    for k in rows[0][1]["struct"]:
        ok = [(r[1]["struct"][k], r[2]["struct"][k]) for r in rows
              if r[1]["struct"][k] is not None and r[2]["struct"][k] is not None]
        if not ok:
            continue
        hs = sorted(v[0] for v in ok)
        ass = sorted(v[1] for v in ok)
        delta = sum((a > h) - (a < h) for h, a in ok) / len(ok)
        out[k] = dict(human=hs[len(hs) // 2], ai=ass[len(ass) // 2], delta=delta, n=len(ok))
        print(f"{k:<20}{hs[len(hs) // 2]:>9.3f}{ass[len(ass) // 2]:>9.3f}{delta:>8.2f}")

    if args.json:
        Path(args.json).write_text(json.dumps({"pairs": n, "human_words": hw, "ai_words": aw,
                                               "split": args.split, "features": out},
                                              ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
