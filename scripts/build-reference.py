#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge measure.py --json results into references/measured.json.

    python3 scripts/build-reference.py --dir results/ --out references/measured.json

Expects {dev,holdout}_{generator}.json in --dir. detect.py and report.py read the output,
so every number shown to a user comes from a measurement, not from a hand-typed table.
"""
import argparse
import json
from pathlib import Path

GENERATORS = ["GPT-3.5-T", "GEMINI-2.5-F", "COMMAND-R"]


def clean(x):
    if isinstance(x, float):
        return None if x == float("inf") else round(x, 3)
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    d = Path(args.dir)
    runs = {s: {g: json.loads((d / f"{s}_{g}.json").read_text(encoding="utf-8")) for g in GENERATORS}
            for s in ("dev", "holdout")}
    out = {"source": "ALHD v1.0, ALHD_Main.csv, SANAD and ANAD news. DOI 10.5281/zenodo.17249602",
           "generators": GENERATORS,
           "pairs": {g: runs["holdout"][g]["pairs"] for g in GENERATORS},
           "human_words": {g: runs["holdout"][g]["human_words"] for g in GENERATORS},
           "ai_words": {g: runs["holdout"][g]["ai_words"] for g in GENERATORS},
           "features": {}, "composite": {}}
    for k in runs["holdout"][GENERATORS[0]]["features"]:
        if k == "_composite":
            for g in GENERATORS:
                out["composite"][g] = clean(runs["holdout"][g]["features"][k])
            continue
        row = {"human": clean(runs["holdout"][GENERATORS[0]]["features"][k]["human"]), "by_model": {}}
        for g in GENERATORS:
            h = runs["holdout"][g]["features"][k]
            cell = {key: clean(h[key]) for key in ("R", "lo", "hi", "delta", "ai") if key in h}
            cell["dev_R"] = clean(runs["dev"][g]["features"][k].get("R"))
            cell["by_source"] = clean(h.get("by_source"))
            row["by_model"][g] = cell
        out["features"][k] = row
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out['features'])} features -> {args.out}")


if __name__ == "__main__":
    main()
