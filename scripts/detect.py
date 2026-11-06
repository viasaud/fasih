#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check Arabic text for the measured patterns. Reports only; never edits.

    python3 scripts/detect.py <file or folder> [--json] [--max-hits 5]
    python3 scripts/detect.py <file> --candidates [--out candidates.json]

Levels:
    A  near-mechanical: fixed phrase, up in all three models; review, then propose
    B  propose after review: up in all three models, needs rewording
    F  one model's habit, or unstable result: lower priority; never infer the author
    C  whole-text measures: report only, never edit sentence by sentence
    U  not measurable with this data: mention as unmeasured
    X  rejected: humans use it as much or more; never edit for this reason

All figures come from references/measured.json. See references/research.md for their limits.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from arabic import (COMPILED, FENCE, HEADING, LIST_LINE, SENT_END, SENTENCE_START, TABLE_LINE, WORD,
                    cv, iso_hits, mask_protected, mtld, norm, norm_map, paragraph_blocks, signature,
                    split_sents, vocalised_ratio, word_count)

EXTS = {".md", ".txt"}
MIN_WORDS = 150
MEASURED_PATH = Path(__file__).parent.parent / "references" / "measured.json"

# (level, key, English name, Arabic name for the writer's report, advice)
RULES = [
    ("A", "sign_also", "additive connector at sentence start", "روابط الإضافة في أول الجملة",
     "Start with و, or drop the connector if the addition is clear. Rule 1"),
    ("A", "tr_bil_idafa", "بالإضافة إلى", "«بالإضافة إلى»",
     "In lists, و is enough. Rule 1"),
    ("B", "neg_formula", "ليس مجرد / ليس فقط", "«ليس مجرد» و«ليس فقط»",
     "State what it is directly; keep everything both sides said. Rule 2"),
    ("B", "neg_la_ya8tasir", "لا يقتصر… بل", "«لا يقتصر… بل»",
     "Name both sides together. Rule 2"),
    ("B", "tr_haythu_comma", "، حيث as a connector", "«، حيث» رابطًا بين جملتين",
     "Use a full stop, و, or إذ for a reason. Keep place meaning, من حيث, بحيث. Rule 3"),
    ("B", "tr_mimma", "مما", "«مما» في آخر الجملة",
     "Result: state it (فأدت إلى). Added interpretation: flag if unsourced. Skip comparisons (أكثر مما). Rule 4"),
    ("B", "sign_however", "contrast connector at sentence start", "روابط المقابلة في أول الجملة",
     "Real contrast: لكنّ. Otherwise و. Rule 5"),
    ("B", "sign_kama", "كما at sentence start", "«كما» في أول الجملة",
     "Lower priority: act only when repeated; و usually works. Rule 5"),
    ("B", "lex_grandiose", "grand adjectives", "ألفاظ التفخيم",
     "Delete if they add no meaning; never invent detail. Keep terms like التنمية المستدامة. Rule 6"),
    ("B", "lex_challenge", "التحديات", "«التحديات»",
     "Name the problem if the text states it; otherwise keep and flag. Rule 6"),
    ("B", "lex_effective", "فعّال / الفعالية", "«فعّال» و«الفعالية»",
     "Delete if no measure or comparison; فعالية can mean an event. Rule 6"),

    ("F", "tr_rughm_illa", "رغم… إلا أن", "«رغم… إلا أن»", "Not in Command. Option: رغم… فإن. Rule 7"),
    ("F", "neg_laysa_bal", "general ليس… بل", "«ليس… بل» عامة", "Weak in GPT; sound Arabic style. Rarely edit. Rule 7"),
    ("F", "tr_tamma", "تمّ / يتمّ", "«تمّ» و«يتمّ»", "GPT only; below humans in Gemini and Command. Option: passive verb. Rule 7"),
    ("F", "tr_yu3tabar", "يعتبر", "«يعتبر»", "GPT only. Option: يُعدّ or a nominal sentence. Rule 7"),
    ("F", "tr_bishakl", "بشكل كبير and similar", "«بشكل كبير» وأخواتها", "Up in GPT and Gemini, down in Command. Option: كثيرًا. Rule 7"),
    ("F", "filler_fi_zill", "في ظل", "«في ظل»", "Varies by model and source. Rule 7"),
    ("F", "tr_yal3ab_dawr", "يلعب دورًا", "«يلعب دورًا»", "Down in Command. Option: يؤدي دورًا. Rule 7"),
    ("F", "close_start", "closing opener", "افتتاح الخاتمة", "باختصار, في الختام: clear in GPT only. Rule 7"),
    ("F", "filler_noteworthy", "تجدر الإشارة and similar", "«تجدر الإشارة» وأخواتها", "Up in GPT, down in Gemini. State it directly. Rule 7"),
    ("F", "filler_cliche", "stock phrases", "العبارات الجاهزة", "Rare; the two data halves disagree. Rule 7"),
    ("F", "lex_boost", "تعزيز / تحسين / تطوير", "«تعزيز» و«تحسين» و«تطوير»", "Weak in Command. Rule 7"),
    ("F", "tr_qad_past", "قد before a past verb", "«قد» قبل الماضي", "Small, uneven; correct Arabic. Rarely edit. Rule 7"),
    ("F", "tr_min_qibal", "من قبل for the agent", "«من قبل» لبيان الفاعل", "GPT only. Option: name the agent. Rule 7"),

    ("U", "filler_era", "era openers", "افتتاحيات العصر", "No evidence in rewrites; free writing unmeasured."),
    ("U", "filler_no_doubt", "لا شك", "«لا شك»", "Mixed result; free writing unmeasured."),
    ("U", "cue_colon", "announcing colon", "نقطتان بعد عبارة إعلان", "Very rare in news; free writing unmeasured."),

    ("X", "tr_min_ajl", "من أجل", "«من أجل»", "More human in all three. Do not edit."),
    ("X", "contrast_yudhkar", "يذكر أن", "«يذكر أن»", "More human in all three. Do not edit."),
    ("X", "tr_ibara_3an", "عبارة عن", "«عبارة عن»", "More human in all three. Do not edit for this reason."),
    ("X", "tr_qama_bi", "قام بـ", "«قام بـ»", "Not higher in any model. Do not edit for this reason."),
    ("X", "tr_min_khilal", "من خلال", "«من خلال»", "Not generally higher. Do not edit for this reason."),
    ("X", "tr_topic_shell", "بالنسبة لـ / فيما يتعلق بـ", "«بالنسبة لـ» و«فيما يتعلق بـ»", "Not generally higher. Do not edit for this reason."),
    ("X", "restate", "هذا يعني", "«هذا يعني»", "Not higher in any model. Do not edit."),
    ("X", "tr_wa_dhalika", "وذلك", "«وذلك»", "Humans equal or more. Do not edit."),
    ("X", "sign_ordinals", "أولًا / ثانيًا", "«أولًا» و«ثانيًا»", "No stable difference. Do not edit."),
]

# Counted and reported, never edited by themselves. Humans use most of these more.
PUNCT = [("p_colon", "colon"), ("p_paren", "brackets"), ("p_emdash", "long dash"),
         ("p_semicolon", "semicolon"), ("p_comma", "comma"), ("p_question", "question mark")]

LEVEL_TITLES = {
    "A": "A near-mechanical: review, then propose",
    "B": "B propose after reviewing each one",
    "F": "F one model's habit: lower priority, never infer the author",
    "U": "U unmeasured: mention only",
    "X": "X rejected: do not edit",
}


def load_measured():
    try:
        return json.loads(MEASURED_PATH.read_text(encoding="utf-8"))
    except OSError:
        return None


def ref_string(measured, key, human="human {:.2f}/1k"):
    """Human rate and each model's ratio, for example: human 0.42/1k | GPT ×4.03 | Gemini ×2.09 | Command ×2.91"""
    if not measured or key not in measured["features"]:
        return ""
    row = measured["features"][key]
    short = {"GPT-3.5-T": "GPT", "GEMINI-2.5-F": "Gemini", "COMMAND-R": "Command"}
    cells = []
    for g, name in short.items():
        r = row["by_model"][g].get("R")
        cells.append(f"{name} ×{r:.2f}" if r is not None else f"{name} —")
    return human.format(row["human"]) + " | " + " | ".join(cells)


def prose_lines(text):
    """Yield (line number, original line) for prose paragraphs only."""
    lines = text.splitlines()
    for kind, body, first in paragraph_blocks(text):
        if kind != "prose":
            continue
        for offset in range(len(body.split("\n"))):
            no = first + offset
            yield no, lines[no - 1]


def find_hits(fname, text):
    hits = {k: [] for _, k, *_ in RULES}
    for no, line in prose_lines(text):
        masked = mask_protected(line)
        n, idx = norm_map(masked)
        if not n.strip():
            continue

        def excerpt(a, b):
            start = idx[max(0, a - 22)] if idx else 0
            end = idx[min(len(idx) - 1, b + 22)] + 1 if idx else len(line)
            return line[start:end].strip()

        # Sentence start offsets, for the rules that apply only there.
        starts = [0] + [m.end() for m in SENT_END.finditer(n)]
        for _, key, *_ in RULES:
            pat = COMPILED[key]
            if key in SENTENCE_START:
                for i, s in enumerate(starts):
                    e = starts[i + 1] if i + 1 < len(starts) else len(n)
                    m = pat.search(n[s:e])
                    if m:
                        hits[key].append({"file": fname, "line": no, "excerpt": excerpt(s + m.start(), s + m.end())})
            else:
                for m in pat.finditer(n):
                    hits[key].append({"file": fname, "line": no, "excerpt": excerpt(m.start(), m.end())})
    return hits


def measure_docs(docs):
    total = n_para = n_head = 0
    hits = {k: [] for _, k, *_ in RULES}
    punct = {k: 0 for k, _ in PUNCT}
    sent_lens, para_lens, sect_lens, toks = [], [], [], []
    iso2 = iso3 = 0
    protected_chars = 0
    for fname, text in docs:
        for k, v in find_hits(fname, text).items():
            hits[k].extend(v)
        sect = 0
        for kind, body, _ in paragraph_blocks(text):
            if kind == "heading":
                n_head += 1
                if sect:
                    sect_lens.append(sect)
                sect = 0
                continue
            if kind != "prose":
                continue
            clean = norm("\n".join(mask_protected(l) for l in body.split("\n")))
            protected_chars += sum(1 for l in body.split("\n") if not mask_protected(l).strip() and l.strip())
            w = word_count(clean)
            if not w:
                continue
            n_para += 1
            total += w
            sect += w
            para_lens.append(w)
            toks.extend(WORD.findall(clean))
            sent_lens.extend(word_count(s) for s in split_sents(clean))
            iso2 += len(iso_hits(clean, 2))
            iso3 += len(iso_hits(clean, 3))
            for k, _ in PUNCT:
                punct[k] += len(COMPILED[k].findall(clean))
        if sect:
            sect_lens.append(sect)
    kw = total / 1000 or 1
    return {
        "meta": {"files": len(docs), "words": total, "paragraphs": n_para, "headings": n_head,
                 "protected_lines": protected_chars},
        "density": {k: round(len(v) / kw, 3) for k, v in hits.items()},
        "hits": hits,
        "punctuation": {k: round(v / kw, 3) for k, v in punct.items()},
        "structure": {
            "sent_mean": round(sum(sent_lens) / len(sent_lens), 2) if sent_lens else None,
            "sent_cv": round(cv(sent_lens), 3) if cv(sent_lens) is not None else None,
            "para_cv": round(cv(para_lens), 3) if cv(para_lens) is not None else None,
            "section_cv": round(cv(sect_lens), 3) if len(sect_lens) >= 3 else None,
            "headings_per_k": round(n_head / kw, 3),
            "iso2_per100p": round(iso2 / n_para * 100, 2) if n_para else None,
            "iso3_per100p": round(iso3 / n_para * 100, 2) if n_para else None,
            "mtld": mtld(toks),
        },
    }


# ---------------- semantic candidates ----------------

NOISE = re.compile(r"\]\(|\||^!")
CAPS = {"rename": 60, "cohesion": 60, "colon": 80, "iso3": 60}


def plain(block):
    if NOISE.search(block[:200]) and "](" not in block:
        return ""
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", block)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    return re.sub(r"[*`_#>]", "", t).strip()


def extract_candidates(docs):
    rename, cohesion, colon, iso3 = [], [], [], []
    for fname, text in docs:
        blocks = []
        for kind, body, no in paragraph_blocks(text):
            if kind != "prose" or vocalised_ratio(body) > 0.30:
                continue
            t = plain(body)
            if word_count(t) >= 8:
                blocks.append((t, no))
        for t, no in blocks:
            if word_count(t) >= 25:
                rename.append({"type": "rename", "file": fname, "line": no, "para": t})
        for i in range(len(blocks) - 1):
            a, b = blocks[i][0], blocks[i + 1][0]
            tail = split_sents(a) or [a[-90:]]
            head = split_sents(b) or [b[:90]]
            cohesion.append({"type": "cohesion", "file": fname, "line": blocks[i + 1][1],
                             "prev_tail": tail[-1], "next_head": head[0]})
        for no, line in prose_lines(text):
            masked = mask_protected(line)
            for m in re.finditer(r"([^:،.؟!\n]{3,70})[:：]\s*(.{2,120})", masked):
                if m.group(1)[-1:].isdigit():  # clock times and ratios
                    continue
                colon.append({"type": "colon", "file": fname, "line": no,
                              "colon_before": m.group(1).strip(), "colon_after": m.group(2)[:100],
                              "sentence": line.strip()[:180]})
        for kind, body, no in paragraph_blocks(text):
            if kind == "prose":
                clean = "\n".join(mask_protected(l) for l in body.split("\n"))
                for run in iso_hits(clean, 3):
                    iso3.append({"type": "iso3", "file": fname, "line": no, "sents": run})
    all_c = {"rename": rename, "cohesion": cohesion, "colon": colon, "iso3": iso3}
    meta = {f"n_{k}": len(v) for k, v in all_c.items()}
    truncated = {k: c for k, c in CAPS.items() if len(all_c[k]) > c}
    for k, c in truncated.items():
        step = len(all_c[k]) / c
        all_c[k] = [all_c[k][int(i * step)] for i in range(c)]
    meta["truncated"] = truncated or False
    meta["n_candidates"] = sum(len(v) for v in all_c.values())
    return dict(meta=meta, **all_c)


# ---------------- report ----------------

def fmt_report(r, max_hits, measured):
    m = r["meta"]
    out = [f"Files {m['files']} | words {m['words']} | paragraphs {m['paragraphs']} | headings {m['headings']}"
           + (f" | protected lines skipped {m['protected_lines']}" if m["protected_lines"] else ""),
           "Density is per 1000 Arabic words. Ratios: model/human, measured on rewritten news. Limits: references/research.md.", ""]
    for level in "ABFUX":
        rows = [(k, name, adv) for lv, k, name, _, adv in RULES if lv == level and r["hits"][k]]
        if not rows:
            continue
        out.append(f"[{LEVEL_TITLES[level]}]")
        for k, name, adv in rows:
            out.append(f"{name}: hits {len(r['hits'][k])}, {r['density'][k]}/1k | {ref_string(measured, k)}")
            out.append(f"  -> {adv}")
            for h in r["hits"][k][:max_hits]:
                out.append(f"  {h['file']}:{h['line']} {h['excerpt']}")
        out.append("")
    out.append("[C whole-text: report only; never engineer variation]")
    s = r["structure"]
    labels = [("sent_mean", "mean sentence length"), ("sent_cv", "sentence-length CV"), ("para_cv", "paragraph-length CV"),
              ("mtld", "vocabulary diversity (MTLD)"), ("iso2_per100p", "same-shape sentence pairs per 100 paragraphs")]
    for k, name in labels:
        if s.get(k) is None:
            continue
        line = f"{name}: {s[k]}"
        if measured and k in measured["features"]:
            f = measured["features"][k]
            ais = "/".join(f"{f['by_model'][g]['ai']:.2f}" for g in measured["generators"])
            line += f" (human median {f['human']:.2f}; GPT/Gemini/Command {ais})"
        out.append(line)
    out.append("")
    out.append("[punctuation: information only; do not remove or add]")
    for k, name in PUNCT:
        line = f"{name}: {r['punctuation'][k]}/1k"
        if measured and k in measured["features"]:
            line += f" (human {measured['features'][k]['human']:.2f})"
        out.append(line)
    out.append("")
    out.append("This describes the text, not its author: some human articles carry these patterns too.")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Check Arabic text for the measured patterns")
    ap.add_argument("target")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-hits", type=int, default=5)
    ap.add_argument("--candidates", action="store_true", help="extract semantic-layer candidates")
    ap.add_argument("--out", help="candidates output file")
    args = ap.parse_args()

    p = Path(args.target)
    if not p.exists():
        print(f"Path not found: {p}", file=sys.stderr)
        sys.exit(1)
    if p.is_file():
        docs = [(p.name, p.read_text(encoding="utf-8", errors="ignore"))]
    else:
        docs = [(str(f.relative_to(p)), f.read_text(encoding="utf-8", errors="ignore"))
                for f in sorted(p.rglob("*")) if f.suffix.lower() in EXTS and f.is_file()]
    if not docs:
        print("No .md or .txt files found", file=sys.stderr)
        sys.exit(1)

    if args.candidates:
        c = extract_candidates(docs)
        payload = json.dumps(c, ensure_ascii=False, indent=1)
        if args.out:
            Path(args.out).write_text(payload, encoding="utf-8")
            mm = c["meta"]
            print(f"{mm['n_candidates']} candidates -> {args.out} (rename {mm['n_rename']} / cohesion {mm['n_cohesion']}"
                  f" / colon {mm['n_colon']} / iso3 {mm['n_iso3']})")
        else:
            print(payload)
        return

    r = measure_docs(docs)
    if r["meta"]["words"] < MIN_WORDS:
        # Warn only: an edited text may fall below the limit, and the recheck must still run.
        print(f"Warning: under {MIN_WORDS} words, so densities are unstable. Rely on hit counts.",
              file=sys.stderr)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(fmt_report(r, args.max_hits, load_measured()))


if __name__ == "__main__":
    main()
