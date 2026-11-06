---
name: fasih
description: Clean AI-sounding patterns from finished Modern Standard Arabic text (إزالة نبرة الذكاء الاصطناعي، تنقية النص العربي من الأنماط الآلية، مراجعة نص عربي). Checks the text with a script and closed semantic criteria, reports figures, examples and proposed edits, edits only after the user replies, then rechecks and shows a before-and-after comparison. Rules are measured on Arabic news from three models. Does not determine authorship. Never edits Quran, hadith, poetry or quotations.
---

# Fasih

Order of work: **check, explain findings and proposed edits, wait for the user's reply, edit, recheck.**

**Language:** write every report and message in the user's language. If unclear, use the language of the text, normally Arabic. These instructions are in English only to save tokens.

Three layers:

- **Script:** countable words, punctuation and structure (`scripts/detect.py`).
- **Semantic layer:** needs sentence meaning; you judge it with [closed criteria](./references/semantic-criteria.md).
- **Human review:** metaphor quality and similar. You don't judge these.

## Evidence limits: read before quoting a figure

Measured on Arabic news rewritten by GPT-3.5, Gemini 2.5 Flash and Command R. Details: [research.md](./references/research.md).

1. Figures describe a **tendency in that corpus**. Free writing, literary and academic text, and newer models such as Claude weren't measured. Say so if the text is another type.
2. **Never call a text AI-written or human-written.** Many human articles in the study carry these patterns densely.
3. Never call a single text statistically significant. Significance belongs to the corpus.
4. Under 500 words, one hit moves density a lot. Rely on hit counts.

## Never touch

- **Quran, hadith, poetry and quotations, down to the letter and vowel mark.** The script masks ﴿ ﴾, « », quotation marks and heavily vocalised lines. It can miss unvocalised sacred text with no brackets, so check for that yourself before any edit.
- Customary religious and formal phrases: البسملة، الحمدلة، «أما بعد»، الصلاة على النبي، letter and contract formulas.
- Dialect: tell the user the rules target MSA news. Don't convert it.
- Names, numbers, dates, sources and digit style (٣ or 3).
- Structure: headings, paragraph order, lists, tables, code.

---

## Workflow

### Step 1: script check

```bash
python3 scripts/detect.py <file> --max-hits 5
python3 scripts/detect.py <file> --json > before.json
```

Levels are defined in [detect.md](./references/detect.md). Keep `before.json` for step 4.

### Step 1.5: semantic layer (single file)

```bash
python3 scripts/detect.py <file> --candidates --out candidates.json
```

Judge each candidate using the [criteria](./references/semantic-criteria.md): write `label`, `confidence` and `reason` into the same file. The criteria aren't validated on Arabic, so present results as notes weighing less than script findings.

### Step 2: report, then stop

Deliver a clear report and **end your turn. Don't edit before the user replies.** Don't paste raw script output. Include:

1. **Method:** what the script checked, what you judged, word, paragraph and candidate counts, and evidence limits relevant to this text type.
2. **Measures table:** for each locatable item: raw hits, valid hits, proposed, kept, plus density and reference. For whole-text level C items, give the value only.
3. **Examples and edits:** for each proposed item, one or two located passages, why it was flagged, and the specific edit. Don't write the full edited text here.
4. **Kept items and scope:** what you kept, how many, why, with an example, then the whole proposed scope. Ask for one reply: "edit as proposed" or a changed scope.

**Never drop an item silently.** Each hit gets a status with a reason: proposed, kept, script error, or needs review. Save this to a file when the input is a file. Few hits alone isn't a reason to keep a valid A or B hit: give a reason specific to that passage, such as meaning nothing else carries or deliberate style.

On agreement, go straight to step 3. On a question or a request to stop, answer or stop. Silence isn't agreement. "Edit everything" means A, B, semantic and editable F items, never X, C or human-review items.

### Step 3: edit

Edit only the agreed scope. Record the original, the new text and the rule number for each change.

### Step 4: recheck and compare

```bash
python3 scripts/detect.py <edited file> --json > after.json
python3 scripts/report.py <original> <edited file> before.json after.json \
    --semantic candidates.json --out report.md
```

Add `--format html` if the user wants a web page. Don't chase zero on every item or a target value in C.

---

## Editing principles

1. **Smallest edit.** Change only what resolves the finding, with no side polishing. When unsure, keep the original.
2. **Conserve information.** Every idea, fact and qualifier stays. «قد» doesn't become «لا بد», and «غالبًا» doesn't become «دائمًا».
3. **Never invent detail.** If a sentence is general and the source gives no detail, keep it or flag it. Add no number or example of your own.
4. **Grammar first.** Recheck case endings and agreement after each edit: «إنّ» takes the accusative, and verbs agree with subjects. If you change a particle, change what it governs, as in «رغم… فإن».
5. **Don't engineer variation.** Don't lengthen, shorten or split to match figures.
6. **Sentence-initial و is sound Arabic,** and common in the human news we measured. Don't remove it in imitation of English.
7. **The author's style comes first.** Read any style guide or earlier writing first. A repeated habit there is style, not an error.

**After editing, verify:** every edit has a rule, every new word has a source in the text, grammar is sound, structure is unchanged. Undo whatever fails.

---

## Rules

Ratios come from the held-out half of the data: model rate divided by human rate, in the order GPT / Gemini / Command. Full values: [references/measured.json](./references/measured.json).

### 1. Additive connectors (A)

«بالإضافة إلى» ×4.03 / ×2.09 / ×2.91; at sentence start ×3.53 / ×3.81 / ×2.68. و is usually enough.

> ❌ يحتوي على البروتين والألياف، بالإضافة إلى البوتاسيوم.
> ✅ يحتوي على البروتين والألياف والبوتاسيوم.

> ❌ بالإضافة إلى ذلك، تقدم الشركة خدمة التوصيل.
> ✅ وتقدم الشركة خدمة التوصيل.

### 2. Set phrases after negation (B)

«ليس مجرد / ليس فقط» ×2.80 / ×19.62 / ×2.05; «لا يقتصر» ×2.27 / ×19.83 / ×6.78. Say what the thing is, and keep what both sides contain.

> ❌ هذا التطبيق ليس مجرد أداة للتواصل، بل منصة لإدارة العمل.
> ✅ يجمع هذا التطبيق التواصل وإدارة العمل.

> ❌ لا يقتصر أثر القرار على الموظفين، بل يمتد إلى العملاء.
> ✅ يمس القرار الموظفين والعملاء.

**Limits:** general «ليس… بل» is sound Arabic style and isn't part of this rule (see rule 7). Don't edit a sentence answering a view actually stated in the text.

### 3. «، حيث» as a connector (B)

×3.10 / ×1.58 / ×3.56. The most widespread rule: in 59%, 46% and 67% of model texts, against about 30% of human texts. Use a full stop, و, or «إذ» for a reason.

> ❌ ارتفعت الأسعار، حيث بلغت الزيادة 12%.
> ✅ ارتفعت الأسعار، وبلغت الزيادة 12%.

**Keep:** place meaning («حيث يعيش»), «من حيث», «بحيث».

### 4. «مما» closing a sentence (B)

×3.75 / ×7.52 / ×1.69. Two uses:

- **Cause and result:** state the relation.
- **Added interpretation** («مما يعكس…», «مما يبرز…»): check whether the source says it. If it's the author's own, keep it as a separate sentence. If its basis is unknown, flag it; don't delete it yourself.

> ❌ زادت الأمطار، مما أدى إلى فيضانات.
> ✅ زادت الأمطار فأدت إلى فيضانات.

> ❌ أغلقت الشركة مصنعين، مما يعكس تراجع الطلب.
> ✅ أغلقت الشركة مصنعين. ويعكس ذلك تراجع الطلب.

**Keep:** comparison and partitive uses, as in «أكثر مما توقعنا» and «كثير مما قيل». The script counts them too, so exclude them on review.

### 5. Sentence-initial connectors (B)

«من ناحية أخرى / مع ذلك / في المقابل» ×2.86 / ×2.46 / ×1.90; «كما» ×1.61 / ×2.77 / ×2.10 (lower priority). Keep the connector when the contrast is real, preferably «لكنّ». Edit «كما» only when it repeats.

> ❌ ومن ناحية أخرى، شهد القطاع نموًّا.
> ✅ وشهد القطاع نموًّا.

### 6. Grand and generic words (B)

محوري، جوهري، حيوي، مستدام، متكامل، مبتكر، رائد ×1.70 / ×5.67 / ×1.89; «التحديات» ×4.13 / ×6.84 / ×1.39; «فعّال» ×2.39 / ×3.11 / ×1.41. **Don't swap in synonyms.** Delete what adds no meaning, and name the thing if the text itself states it.

> ❌ يواجه الطلاب التحديات في إيجاد الوقت.
> ✅ يجد الطلاب صعوبة في إيجاد الوقت.

**Keep:** the terms «الطاقة المستدامة» and «التنمية المستدامة», «فعالية» meaning an event, and «حيوي» in biology.

### 7. One model's habits (F)

These didn't hold across all three models. **Never infer which model wrote a text from them.** Propose at lower priority, only if the edit is grammatical and loses nothing:

| Pattern | Possible edit | Why it's here |
|---|---|---|
| «تمّ / يتمّ» | «أُطلقت الخدمة» for «تم إطلاق الخدمة» | Up in GPT; below humans in Gemini and Command |
| «يعتبر» | «يُعدّ» or a nominal sentence | Up in GPT; below humans in Command |
| «بشكل كبير» | «كثيرًا» | Up in GPT and Gemini; down in Command |
| «رغم… إلا أن» | «رغم… فإن» | Not established in Command |
| general «ليس… بل» | Usually leave it | Weak in GPT; sound style |
| «يلعب دورًا» | «يؤدي دورًا» | Down in Command |
| «باختصار» in a conclusion | Delete if not needed | Clear in GPT only |
| «تجدر الإشارة» | State the point directly | Below humans in Gemini |

The full list is in `detect.py`.

---

## Level X: never edit for this reason

Often called AI signs or weak style, but measurement doesn't support that. They may have other style merits or faults, but **they aren't this skill's patterns**:

| Pattern | Result (GPT / Gemini / Command) |
|---|---|
| «من أجل» | More human in all three: ×0.65 / ×0.13 / ×0.39 |
| «يذكر أن» | More human in all three: ×0.73 / ×0.21 / ×0.50 |
| «عبارة عن» | More human in all three: ×0.19 / ×0.06 / ×0.00 |
| «قام بـ» | No increase: ×0.88 / ×0.23 / ×0.59 |
| «من خلال» | No increase: ×1.05 / ×0.73 / ×0.43 |
| «بالنسبة لـ», «فيما يتعلق بـ» | No increase: ×1.16 / ×0.69 / ×0.41 |
| «هذا يعني» | No increase: ×0.79 / ×0.25 / ×0.98 |
| «وذلك» | No increase: ×0.65 / ×0.96 / ×0.87 |
| «أولًا», «ثانيًا» | No stable difference: ×1.79 / ×0.71 / ×1.45 |
| Colons, brackets, long dashes | More human. Neither remove nor add |

## Level U: unmeasured

Such as «في عالمنا المتسارع» and «لا شك أن». They may be common in free essays, but our data is rewritten news and can't measure them. Mention them as unmeasured notes, and propose an edit only if they add no meaning.

## Human review

Metaphor quality, simile, personification and the value of rhymed prose. Don't assess or edit these unless the user asks.

---

## Before delivering

- The report came first, and you waited for a reply before any edit.
- No sacred text or quotation changed, and you checked unvocalised text yourself.
- Every edit has a rule, and every new word has a source in the text.
- Names, numbers and qualifiers are unchanged, and grammar is sound.
- Structure is unchanged, no X item was edited, and no target was forced on C.
- You didn't call the text AI or human, and you stated the evidence limits.
- You rechecked and delivered the comparison.
