#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Before-and-after report for the writer: measures, pattern list and marked-up text.

    python3 scripts/detect.py original.md --json > before.json
    python3 scripts/detect.py edited.md --json > after.json
    python3 scripts/report.py original.md edited.md before.json after.json \\
        [--semantic labelled.json] [--out report.md] [--format md|html]

Code is in English. The report text is Arabic on purpose: its reader is the writer, not an
agent. Differences are marked word by word, because marking inside a word would split
joined Arabic letters and render them in the wrong shapes.
"""
import argparse
import difflib
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from arabic import word_count
from detect import RULES, load_measured, ref_string

LEVEL_TITLES = {
    "A": "A تعديل آلي تقريبًا (يراجعها النموذج قبل اقتراحها)",
    "B": "B يقترح تعديلها (يراجعها النموذج واحدة واحدة)",
    "F": "F عادة نموذج بعينه (أولوية أدنى، ولا تدل على كاتب بعينه)",
    "U": "U لم تُقس (للمراجعة فقط)",
    "X": "X مرفوضة (لا تعدلها: أُبقيت لمنع التعديل الخاطئ)",
}
HUMAN_REF = "بشر {:.2f}/ألف كلمة"

STRUCT = [("sent_mean", "متوسط طول الجملة"), ("sent_cv", "تفاوت طول الجمل"), ("para_cv", "تفاوت طول الفقرات"),
          ("mtld", "تنوع المفردات")]

SEMANTIC_GROUPS = {"rename": "إعادة التسمية بالمرادفات", "cohesion": "الربط بين الفقرات",
                   "colon": "تصنيف النقطتين", "iso3": "ثلاث جمل متطابقة البناء"}
FLAGGED = {"تغييران", "ثلاثة فأكثر", "أداة بلا علاقة", "نتيجة معلنة", "تطابق عال"}
LINK = "اتصال واضح"

SEMANTIC_NOTE = ("معايير هذه الطبقة لم تُختبر على العربية، فهي ملاحظات "
                 "قابلة للمراجعة، وليست نتائج مقيسة. انظر references/semantic-criteria.md.")
CAVEAT = ("النسب من أخبار عربية أعادت النماذج صياغتها (GPT-3.5 وGemini 2.5 Flash وCommand R). "
          "وهي تصف الاتجاه، ولا تفحص نصك إحصائيًّا، ولا تحدد من كتبه. انظر references/research.md.")

CSS = """
body{font-family:"Noto Naskh Arabic","Geeza Pro","Segoe UI",Tahoma,sans-serif;max-width:800px;margin:40px auto;
line-height:2;font-size:17px;padding:0 20px;color:#222;background:#fff}
h1{font-size:24px}h2{font-size:20px;border-bottom:2px solid #ccc;padding-bottom:6px;margin-top:2.2em}
h3{font-size:17px;margin-bottom:.4em}
table{border-collapse:collapse;width:100%;font-size:15px;margin:.6em 0 1.4em;display:block;overflow-x:auto}
th,td{border:1px solid #ddd;padding:5px 10px;text-align:right;vertical-align:top}
th{background:#f5f5f5}
del{color:#999;text-decoration:line-through}
ins{color:#b71c1c;text-decoration:none;font-weight:600}
.small{color:#666;font-size:14px}
p{margin:0 0 1.1em}
@media (prefers-color-scheme:dark){body{background:#1b1b1b;color:#e6e6e6}th{background:#2a2a2a}
th,td{border-color:#444}del{color:#888}ins{color:#ff8a80}.small{color:#aaa}}
"""


def arrow(a, b):
    if a is None or b is None or a == b:
        return "←"
    return "▼" if b < a else "▲"


def fmt(v):
    return "—" if v is None else v


def metric_rows(d0, d1, measured):
    rows = []
    for level, key, _, name, _ in RULES:
        if level not in "ABF":
            continue
        v0, v1 = d0["density"].get(key), d1["density"].get(key)
        if not v0 and not v1:
            continue
        rows.append((f"{level} · {name}", fmt(v0), fmt(v1), arrow(v0, v1), ref_string(measured, key, HUMAN_REF)))
    for key, name in STRUCT:
        v0, v1 = d0["structure"].get(key), d1["structure"].get(key)
        ref = ""
        if measured and key in measured["features"]:
            f = measured["features"][key]
            ais = " / ".join(f"{f['by_model'][g]['ai']:.2f}" for g in measured["generators"])
            ref = f"وسيط البشر {f['human']:.2f} | GPT / Gemini / Command: {ais}"
        rows.append((f"C · {name}", fmt(v0), fmt(v1), arrow(v0, v1), ref))
    return rows


HEAD = ("المؤشر (لكل ألف كلمة)", "قبل", "بعد", "التغير", "المرجع")
TABLE_NOTE = "▼ انخفض، ▲ ارتفع، ← لم يتغير. لا يُطلب من مؤشرات C بلوغ قيمة بعينها."


def hit_groups(d):
    for level in "ABFUX":
        items = [(k, name) for lv, k, _, name, _ in RULES if lv == level and d["hits"].get(k)]
        if items:
            yield level, items


def semantic_groups(sem):
    if not sem:
        return
    for key, title in SEMANTIC_GROUPS.items():
        items = [c for c in sem.get(key, []) if c.get("label")]
        if not items:
            continue
        counts = {}
        for c in items:
            counts[c["label"]] = counts.get(c["label"], 0) + 1
        note = ""
        if key == "cohesion":
            best = cur = 0
            for c in items:
                cur = cur + 1 if c["label"] == LINK else 0
                best = max(best, cur)
            note = f"أطول سلسلة ربط: {best} حدود."
        flagged = []
        for c in [c for c in items if c["label"] in FLAGGED][:15]:
            text = c.get("para") or " ← ".join(filter(None, [c.get("prev_tail"), c.get("next_head")])) \
                or c.get("sentence") or " / ".join(c.get("sents") or [])
            flagged.append((c["label"], c.get("confidence", ""), c.get("file", ""), c.get("line", ""),
                            text[:170], c.get("reason", "")[:140]))
        yield title, len(items), counts, note, flagged


def para_split(text):
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def tokens(s):
    return re.findall(r"\s+|[^\s]+", s)


def inline_diff(a, b, escape):
    ta, tb = tokens(a), tokens(b)
    # Merge changes separated only by a space, so a rewritten phrase reads as one change.
    ops = []
    for op in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        tag, i1, i2, j1, j2 = op
        gap = tag == "equal" and not "".join(ta[i1:i2]).strip()
        if ops and ops[-1][0] != "equal" and (tag != "equal" or gap):
            ops[-1] = ("replace", ops[-1][1], i2, ops[-1][3], j2)
        else:
            ops.append(op)
    out = []
    for tag, i1, i2, j1, j2 in ops:
        x, y = "".join(ta[i1:i2]), "".join(tb[j1:j2])
        if tag == "equal":
            out.append(escape(x))
        else:
            if x.strip():
                out.append(f"<del>{escape(x)}</del>")
            if y.strip():
                out.append(f"<ins>{escape(y)}</ins>")
            if not x.strip() and not y.strip():
                out.append(escape(y))
    return "".join(out)


def diff_paras(t0, t1, escape):
    p0, p1 = para_split(t0), para_split(t1)
    body = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, p0, p1, autojunk=False).get_opcodes():
        if tag == "equal":
            body.extend(escape(p) for p in p0[i1:i2])
        elif tag == "delete":
            body.extend(f"<del>{escape(p)}</del>" for p in p0[i1:i2])
        elif tag == "insert":
            body.extend(f"<ins>{escape(p)}</ins>" for p in p1[j1:j2])
        else:
            for pa, pb in zip(p0[i1:i2], p1[j1:j2]):
                body.append(inline_diff(pa, pb, escape))
            body.extend(f"<del>{escape(p)}</del>" for p in p0[i1 + (j2 - j1):i2])
            body.extend(f"<ins>{escape(p)}</ins>" for p in p1[j1 + (i2 - i1):j2])
    return body


def build_md(t0, t1, d0, d1, sem, n0, n1, measured):
    lines = ['<div dir="rtl">', "", "# تقرير المقارنة", "", f"{n0} ← {n1}", "", CAVEAT, "",
             "## ١. المؤشرات قبل وبعد", "", "| " + " | ".join(HEAD) + " |", "|---|---|---|---|---|"]
    for r in metric_rows(d0, d1, measured):
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    lines += ["", TABLE_NOTE, ""]
    if sem:
        lines += ["## ٢. الطبقة الدلالية", "", SEMANTIC_NOTE, ""]
        for title, n, counts, note, flagged in semantic_groups(sem):
            stats = "، ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda x: -x[1]))
            lines += [f"### {title} ({n} مرشحًا: {stats})", ""]
            if note:
                lines += [note, ""]
            for label, conf, f, no, text, reason in flagged:
                lines.append(f"- **{label}** (الثقة: {conf}) `{f}:{no}` {text}" + (f" — السبب: {reason}" if reason else ""))
            lines.append("")
    lines += ["## ٣. الأنماط قبل التعديل", ""]
    for level, items in hit_groups(d0):
        lines += [f"### {LEVEL_TITLES[level]}", ""]
        for k, name in items:
            lines += [f"**{name}**: {len(d0['hits'][k])} موضع", ""]
            lines += [f"- `{h['file']}:{h['line']}` {h['excerpt']}" for h in d0["hits"][k][:20]]
            lines.append("")
    lines += ["## ٤. النص بعد التعديل", "", "<del>المشطوب</del> هو الأصل، و<ins>المميز</ins> هو الجديد.", ""]
    lines.append("\n\n".join(diff_paras(t0, t1, lambda s: s)))
    lines += ["", "</div>", ""]
    return "\n".join(lines)


def build_html(t0, t1, d0, d1, sem, n0, n1, measured):
    e = lambda s: html.escape(str(s), quote=False)
    parts = ['<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             f"<title>تقرير المقارنة</title><style>{CSS}</style></head><body>",
             "<h1>تقرير المقارنة</h1>", f'<p class="small">{e(n0)} ← {e(n1)}</p>',
             f'<p class="small">{e(CAVEAT)}</p>', "<h2>١. المؤشرات قبل وبعد</h2>",
             "<table><tr>" + "".join(f"<th>{e(h)}</th>" for h in HEAD) + "</tr>"]
    for r in metric_rows(d0, d1, measured):
        parts.append("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>")
    parts += ["</table>", f'<p class="small">{e(TABLE_NOTE)}</p>']
    if sem:
        parts += ["<h2>٢. الطبقة الدلالية</h2>", f'<p class="small">{e(SEMANTIC_NOTE)}</p>']
        for title, n, counts, note, flagged in semantic_groups(sem):
            stats = "، ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda x: -x[1]))
            parts.append(f"<h3>{e(title)} <span class='small'>{n} مرشحًا: {e(stats)}</span></h3>")
            if note:
                parts.append(f"<p>{e(note)}</p>")
            for label, conf, f, no, text, reason in flagged:
                parts.append(f"<p class='small'><strong>{e(label)}</strong> (الثقة: {e(conf)}) {e(f)}:{no} {e(text)}"
                             + (f"<br>السبب: {e(reason)}" if reason else "") + "</p>")
    parts.append("<h2>٣. الأنماط قبل التعديل</h2>")
    for level, items in hit_groups(d0):
        parts.append(f"<h3>{e(LEVEL_TITLES[level])}</h3>")
        for k, name in items:
            parts.append(f"<p><strong>{e(name)}</strong>: {len(d0['hits'][k])} موضع</p>")
            for h in d0["hits"][k][:20]:
                parts.append(f"<p class='small'>{e(h['file'])}:{h['line']} {e(h['excerpt'])}</p>")
    parts += ["<h2>٤. النص بعد التعديل</h2>", "<p class='small'><del>المشطوب</del> هو الأصل، و<ins>المميز</ins> هو الجديد.</p>"]
    parts += [f"<p>{p}</p>" for p in diff_paras(t0, t1, e)]
    parts.append("</body></html>")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("json_before")
    ap.add_argument("json_after")
    ap.add_argument("--semantic")
    ap.add_argument("--format", choices=["md", "html"], default="md")
    ap.add_argument("--out")
    args = ap.parse_args()
    t0 = Path(args.before).read_text(encoding="utf-8", errors="ignore")
    t1 = Path(args.after).read_text(encoding="utf-8", errors="ignore")
    d0 = json.loads(Path(args.json_before).read_text(encoding="utf-8"))
    d1 = json.loads(Path(args.json_after).read_text(encoding="utf-8"))
    sem = json.loads(Path(args.semantic).read_text(encoding="utf-8")) if args.semantic else None
    measured = load_measured()
    out = args.out or f"report.{args.format}"
    build = build_md if args.format == "md" else build_html
    Path(out).write_text(build(t0, t1, d0, d1, sem, args.before, args.after, measured), encoding="utf-8")
    print(f"Report -> {out} (before {word_count(t0)} words, after {word_count(t1)}, "
          f"change {word_count(t1) - word_count(t0):+d})")


if __name__ == "__main__":
    main()
