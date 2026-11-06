#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Arabic text engine shared by detect.py, measure.py and report.py.

Standard library only. Handles:
- normalisation (tashkeel, tatweel, alef and yeh variants) with a map back to the
  original characters, so excerpts are shown exactly as the author wrote them;
- word-based density (per 1000 Arabic words, not per 1000 characters);
- protected text: Quran brackets, quotation marks and heavily vocalised lines
  (scripture, hadith, poetry) are masked and never counted or edited.
"""
import re

_MARKS = set(chr(c) for c in range(0x064B, 0x0660)) | {"ٰ", "ـ"}
_FOLD = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ی": "ي", "ة": "ه", "ک": "ك",
    "٬": ",", "ـ": "",
})


def norm(s):
    """Fold spelling variants. Also applied to regex source, so rules stay readable."""
    return "".join(c for c in s if c not in _MARKS).translate(_FOLD)


def norm_map(s):
    """Return (normalised text, index list mapping each output char to its source index)."""
    out, idx = [], []
    for i, c in enumerate(s):
        if c in _MARKS:
            continue
        f = c.translate(_FOLD)
        if not f:
            continue
        out.append(f)
        idx.append(i)
    return "".join(out), idx


WORD = re.compile(r"[ء-ي]+")
# Sentence end: . ! ? ؟ ؛ … followed by space or end. Skips one-letter abbreviations (د. أ.)
# and decimals (3.5), which have no following space.
SENT_END = re.compile(r"(?<!\s[ء-ي])[.!?؟؛…]+(?=[\"»”')\]]*(?:\s|$))")


def words(s):
    return WORD.findall(norm(s))


def word_count(s):
    return len(words(s))


def split_sents(para):
    """Sentences of at least 3 Arabic words."""
    out = []
    for chunk in para.split("\n"):
        for s in SENT_END.split(chunk):
            s = s.strip()
            if word_count(s) >= 3:
                out.append(s)
    return out


# ---------------- protected text ----------------

_QURAN = re.compile(r"[﴿﴾]")
_QUOTED = re.compile(r"﴿[^﴾]*﴾|«[^»]*»|“[^”]*”|\"[^\"\n]*\"|\{[^{}\n]*\}")


def vocalised_ratio(s):
    letters = sum(1 for c in s if "ء" <= c <= "ي")
    marks = sum(1 for c in s if "ً" <= c <= "ْ")
    return marks / letters if letters else 0.0


def mask_protected(line):
    """Blank quotes and scripture, keeping positions. Returns a line of equal length.

    Lines where over 30% of letters carry a vowel mark are treated as scripture, hadith
    or poetry and blanked whole: ordinary prose is rarely vocalised that heavily.
    """
    if vocalised_ratio(line) > 0.30 or _QURAN.search(line) and vocalised_ratio(line) > 0.15:
        return " " * len(line)
    return _QUOTED.sub(lambda m: " " * len(m.group(0)), line)


# ---------------- markdown blocks ----------------

HEADING = re.compile(r"^#{1,6}\s")
BOLD_LINE = re.compile(r"^\*\*[^*]{2,80}\*\*:?$")
LIST_LINE = re.compile(r"^\s{0,3}(?:[-*+•]|[\d٠-٩]+[.)\-、])\s")
QUOTE_LINE = re.compile(r"^>")
FENCE = re.compile(r"^```")
TABLE_LINE = re.compile(r"^\|")


def paragraph_blocks(text):
    """Split on blank lines and classify. Returns [(kind, text, first_line_no)]."""
    blocks, cur, kind, start = [], [], None, None
    in_fence = False
    for no, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            if not cur:
                start = no
            in_fence = not in_fence
            cur.append(line)
            kind = kind or "code"
            continue
        if not in_fence and not line.strip():
            if cur:
                blocks.append((kind or "prose", "\n".join(cur), start))
                cur, kind, start = [], None, None
            continue
        if not cur:
            start = no
        cur.append(line)
        if in_fence:
            kind = kind or "code"
        elif HEADING.match(line):
            kind = "heading"
        elif QUOTE_LINE.match(line):
            kind = kind or "quote"
        elif TABLE_LINE.match(line):
            kind = kind or "table"
        elif LIST_LINE.match(line):
            kind = kind or "list"
        elif BOLD_LINE.match(line.strip()) and kind is None:
            kind = "heading"
    if cur:
        blocks.append((kind or "prose", "\n".join(cur), start))
    return blocks


# ---------------- statistics ----------------

def cv(vals):
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    if m == 0:
        return None
    return (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5 / m


def mtld(toks, threshold=0.72, min_len=10):
    """Moving-window lexical diversity estimate. Higher means fewer repeated words."""
    if len(toks) < min_len * 4:
        return None

    def factors(seq):
        n, types, count = 0.0, set(), 0
        for t in seq:
            count += 1
            types.add(t)
            if count >= min_len and len(types) / count <= threshold:
                n += 1
                types, count = set(), 0
        if count:
            n += (1 - len(types) / count) / (1 - threshold)
        return max(n, 1e-9)

    return round(len(toks) / 2 * (1 / factors(toks) + 1 / factors(toks[::-1])))


# ---------------- candidate features (hypotheses until measured) ----------------

B = r"(?<![\w])"          # start of word
E = r"(?![\w])"           # end of word
P = B + r"[وف]?"          # start of word, optional و/ف clitic
SE = r"[^.!?؟؛\n]"        # any char inside one sentence


def rx(src):
    return re.compile(norm(src))


# Each pattern runs on normalised, protected text. Keys are stable identifiers.
CANDIDATES = {
    # Negation then correction
    "neg_laysa_bal": P + r"(?:ليس|ليست|ليسوا|لسنا|لست|ليسا)" + E + SE + r"{1,90}?" + B + r"(?:بل|وانما|انما)" + E,
    "neg_formula": P + r"(?:ليس|ليست|ليسوا)\s+(?:فقط|فحسب|مجرد)" + E,
    "neg_la_ya8tasir": P + r"(?:لا|لم)\s+(?:يقتصر|تقتصر|يتوقف|تتوقف)" + E,
    "neg_lam_ya3ud": P + r"لم\s+(?:يعد|تعد|يعودوا)" + E,
    "neg_any_bal": B + r"(?:بل|وانما)" + E,

    # Announcing phrases
    "cue_colon": P + r"(?:باختصار|بايجاز|ببساطه|الخلاصه|خلاصه القول|زبده القول|النتيجه|السبب|الجواب|الاجابه|"
                 r"المشكله|الحقيقه|الفكره|الامر|الاهم|المفتاح|السر|الدرس|القاعده|الهدف|الغايه|المعني|اليك|"
                 r"الحل|النقطه)" + SE + r"{0,18}:",
    "cue_short": P + r"(?:بعباره اخري|بمعني اخر|ببساطه)" + E + r"\s*[،:]",
    "close_start": r"^[\s\W]*و?(?:في الختام|ختاما|باختصار|بايجاز|اجمالا|خلاصه القول|في النهايه|في نهايه المطاف|"
                   r"في المجمل|بشكل عام|عموما)" + E,
    "general_adv": P + r"(?:بشكل عام|بوجه عام|بصفه عامه)" + E,

    # Stock phrases
    "filler_no_doubt": P + r"(?:لا شك|لا ريب|مما لا شك فيه|من دون شك|بلا شك|لا جدال)" + E,
    "filler_noteworthy": P + r"(?:من الجدير|الجدير بالذكر|تجدر الاشاره|يجدر الذكر|يجدر بالذكر|ينبغي الاشاره|"
                         r"لا بد من الاشاره|لا يخفي)" + E,
    "filler_important": P + r"(?:من المهم|من الضروري|من الاهميه)" + E,
    "contrast_yudhkar": P + r"(?:يذكر ان|يشار الي ان)" + E,
    "filler_fi_zill": P + r"في\s+ظل" + E,
    "filler_era": P + r"في\s+(?:عالمنا|عالم اليوم|عصرنا|عصر ال|الاونه الاخيره|الوقت الحاضر|الوقت الراهن|"
                  r"وقتنا الحاضر|ايامنا)" + E.replace("(?![\\w])", ""),
    "filler_cliche": P + r"(?:اكثر من اي وقت مضي|لا غني عن|حجر الزاويه|سلاح ذو حدين|ركيزه اساسيه|عنصر اساسي|"
                     r"خطوه مهمه|خطوه هامه|دور محوري|دور حيوي|دور اساسي|دور مهم|دور هام|دور كبير)" + E,

    # Translated constructions
    "tr_tamma": P + r"(?:تم|تمت|يتم|تتم|سيتم|ستتم)" + E,
    "tr_qama_bi": P + r"(?:قام|قامت|قاموا|يقوم|تقوم|يقومون|سيقوم|ستقوم)\s+ب",
    "tr_min_qibal": B + r"من قبل\s+(?!(?:ان|في|عن|علي|او|ثم|لكن|و|من|الي|كما)" + E + r")[ء-ي]",
    "tr_yal3ab_dawr": P + r"(?:يلعب|تلعب|لعب|لعبت|يلعبون)\s+(?:[ء-ي]+\s+)?(?:دور|ادوار)",
    "tr_bishakl": B + r"و?(?:بشكل(?!\s+عام)|بصوره(?!\s+عامه)|بطريقه|باسلوب)\s+[ء-ي]+",
    "tr_min_khilal": P + r"من خلال" + E,
    "tr_haythu": B + r"(?<!من )(?<!الي )و?حيث" + E,
    "tr_haythu_comma": r"،\s*و?حيث" + E,
    "tr_ibara_3an": B + r"عباره عن" + E,
    "tr_kullama2": P + r"كلما" + E + SE + r"{1,60}?" + B + r"كلما" + E,
    "tr_rughm_illa": P + r"(?:علي الرغم|بالرغم|برغم|رغم)" + E + SE + r"{1,110}?" + B + r"الا ان",
    "tr_sawa_aw": P + r"سواء" + E + SE + r"{1,60}?" + B + r"او" + E,
    "tr_yu3tabar": P + r"(?:يعتبر|تعتبر)" + E,
    "tr_yu3add": P + r"(?:يعد|تعد)" + E,
    "tr_min_ajl": P + r"من اجل" + E,
    "tr_mimma": B + r"مما" + E,
    "tr_mimma_eval": B + r"(?:مما|ما)\s+(?:يعكس|يجعل|يشير|يؤكد|يدل|يبرز|يعزز|يسهم|يساهم|يساعد|يمنح|يتيح|يوفر|"
                     r"يشكل|يفتح|يزيد|يؤدي)" + E,
    "tr_amr_alladhi": P + r"الامر الذي" + E,
    "tr_alati_1": P + r"(?:والتي|والذي|واللذين|والذين)" + E,
    "tr_bil_idafa": P + r"بالاضافه" + E,
    "tr_bima_fi": P + r"بما في ذلك" + E,
    "tr_topic_shell": P + r"(?:بالنسبه ل|فيما يتعلق ب|فيما يخص|اما بالنسبه)",
    "tr_nafs": B + r"(?:ب|في|ل|و)?نفس\s+ال",
    "tr_wa_dhalika": B + r"وذلك" + E,
    "tr_qad_past": B + r"[وف]?قد\s+[ء-ي]{3,}",
    "tr_for_example": P + r"علي سبيل المثال" + E,

    # Signpost connectors at sentence start (matched on sentence starts only)
    "sign_also": r"^[\s\W]*(?:بالاضافه الي ذلك|بالاضافه الي|علاوه علي ذلك|فضلا عن ذلك|اضافه الي ذلك|كما ان)" + E,
    "sign_kama": r"^[\s\W]*و?كما\s",
    "sign_therefore": r"^[\s\W]*و?(?:بالتالي|لذلك|لذا|عليه|بناء علي ذلك|من هنا|من ثم)" + E,
    "sign_however": r"^[\s\W]*و?(?:مع ذلك|علي الرغم من ذلك|رغم ذلك|في المقابل|من ناحيه اخري|من جهه اخري)" + E,
    "sign_ordinals": r"^[\s\W]*و?(?:اولا|ثانيا|ثالثا|رابعا|اخيرا)" + E,
    "sign_when": r"^[\s\W]*و?(?:عندما|حينما|عند)\s",

    # Restatement and lists
    "restate": P + r"(?:هذا يعني|مما يعني|ما يعني|يعني ذلك|هذا ما يعني)" + E,
    "list_3": r"[^،.:؟!\n]{1,28}،[^،.:؟!\n]{1,28}،\s*و[ء-ي]",
    "pair_definite": B + r"ال([ء-ي]{3,})\s+وال[ء-ي]{3,}" + E,
    "triple_masdar": B + r"(?:ل|في|ب)?(?:تعزيز|تحسين|تطوير|زياده|تقديم|توفير|دعم|رفع|تحقيق)\s+[ء-ي]+"
                     r"\s+و(?:تعزيز|تحسين|تطوير|زياده|تقديم|توفير|دعم|رفع|تحقيق)" + E,

    # Lexical favourites: measure before trusting
    "lex_boost": P + r"(?:تعزيز|يعزز|تعزز|تحسين|يحسن|تطوير)" + E,
    "lex_effective": B + r"(?:فعال|فعاله|الفعال|الفعاله|فعاليه|الفعاليه)" + E,
    "lex_grandiose": P + r"(?:ال)?(?:محوري|محوريه|جوهري|جوهريه|حيوي|حيويه|مستدام|مستدامه|متكامل|متكامله|مبتكر|مبتكره|"
                     r"رائد|رائده)" + E,
    "lex_challenge": B + r"و?(?:ال)?تحديات" + E,

    # Punctuation (counted, not judged, until measured)
    "p_comma": r"،",
    "p_semicolon": r"؛",
    "p_colon": r":",
    "p_emdash": r"[—–]",
    "p_quote_guillemet": r"«",
    "p_quote_straight": r"[\"“]",
    "p_paren": r"\(",
    "p_question": r"؟",
    "p_exclaim": r"!",
    "p_latin_comma": r"(?<=[ء-ي]),",
}

SENTENCE_START = {"sign_also", "sign_kama", "sign_therefore", "sign_however", "sign_ordinals", "sign_when",
                  "close_start"}
# Quotation marks are counted before masking, since masking removes them.
RAW_TEXT = {"p_quote_guillemet", "p_quote_straight"}

COMPILED = {k: rx(v) for k, v in CANDIDATES.items()}

# Sentence openers, as a share of sentences.
OPEN_WAW = rx(r"^[\s\W]*[وف][ء-ي]{2,}")
OPEN_DEFINITE = rx(r"^[\s\W]*ال[ء-ي]{2,}")
OPEN_PAST_VERB = rx(r"^[\s\W]*[و]?(?:قال|قالت|اعلن|اعلنت|اكد|اكدت|اوضح|اوضحت|اشار|اشارت|ذكر|ذكرت|كشف|كشفت|شهد|شهدت|"
                    r"بدا|بدات|اصدر|اصدرت|افاد|افادت|اضاف|اضافت|يعد|تعد|يقول|تقول)" + E)


def signature(sent):
    """Rough sentence shape: commas, colon, brackets, length band (5-word bands)."""
    return (sent.count("،") + sent.count(","), ":" in sent, "(" in sent, word_count(sent) // 5)


def iso_hits(para, n):
    """Runs of n adjacent sentences (6+ words) with the same shape and at least one comma."""
    sents = [s for s in split_sents(para) if word_count(s) >= 6]
    hits = []
    for i in range(len(sents) - n + 1):
        sigs = [signature(s) for s in sents[i:i + n]]
        if all(g == sigs[0] for g in sigs) and sigs[0][0] >= 1:
            hits.append(sents[i:i + n])
    return hits


def protected_text(text):
    """Prose lines with protected spans blanked, normalised. Skips headings, lists, code."""
    lines = []
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or QUOTE_LINE.match(line) or TABLE_LINE.match(line):
            continue
        lines.append(norm(mask_protected(line)))
    return "\n".join(lines)


def doc_features(text):
    """All candidate counts and structure measures for one document."""
    clean = protected_text(text)
    prose_lines = []
    for kind, body, _ in paragraph_blocks(clean):
        if kind == "prose":
            prose_lines.append(body)
    prose = "\n\n".join(prose_lines)
    n_words = word_count(prose)
    sents = []
    paras = []
    for body in prose_lines:
        ss = split_sents(body)
        sents.extend(ss)
        if ss:
            paras.append(word_count(body))
    raw_norm = norm(text)
    counts = {}
    for k, pat in COMPILED.items():
        if k in SENTENCE_START:
            counts[k] = sum(1 for s in sents if pat.search(s))
        elif k in RAW_TEXT:
            counts[k] = len(pat.findall(raw_norm))
        else:
            counts[k] = len(pat.findall(prose))
    lens = [word_count(s) for s in sents]
    toks = WORD.findall(prose)
    struct = {
        "sent_mean": (sum(lens) / len(lens)) if lens else None,
        "sent_cv": cv(lens),
        "para_cv": cv(paras),
        "iso2_per100p": (sum(len(iso_hits(b, 2)) for b in prose_lines) / len(prose_lines) * 100) if prose_lines else None,
        "iso3_per100p": (sum(len(iso_hits(b, 3)) for b in prose_lines) / len(prose_lines) * 100) if prose_lines else None,
        "mtld": mtld(toks),
        "open_waw": (sum(1 for s in sents if OPEN_WAW.search(s)) / len(sents)) if sents else None,
        "open_definite": (sum(1 for s in sents if OPEN_DEFINITE.search(s)) / len(sents)) if sents else None,
        "open_verb": (sum(1 for s in sents if OPEN_PAST_VERB.search(s)) / len(sents)) if sents else None,
    }
    return {"words": n_words, "sents": len(sents), "counts": counts, "struct": struct}
