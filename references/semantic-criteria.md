# Semantic layer criteria (four items)

The script handles what can be counted. This layer needs sentence meaning, so you judge it item by item. What automated judges can't agree on, such as metaphor quality, goes to human review.

**Evidence warning:** these four criteria aren't tested on Arabic. No human or AI reference figures exist for them, so never say a text passed a "proven" threshold. Present results as reviewable notes, weighing less than measured script findings.

**Arabic warning:** Arabic rhetoric prizes parallelism, rhymed prose, antithesis and varied wording. Parallel sentences and synonyms may be deliberate in literary, oratorical and religious text. When unsure, use the fallback label.

Usage: run `python3 scripts/detect.py <file> --candidates --out candidates.json`, then give each candidate a closed label from its table (never your own), a confidence (عالية / متوسطة / منخفضة) and a one-sentence reason. Write `label`, `confidence` and `reason` into the candidate for `report.py`. **Use the Arabic labels exactly as written:** `report.py` matches them and shows them to the writer.

**Judgement discipline:**

- Judge by the criterion, not by whether it "feels AI". Overall impressions are fooled by style.
- Judge each candidate alone, ignoring the rest of the text.
- When unsure, use the fallback label. Don't force a verdict.
- Never judge a verse, hadith, line of poetry or quoted text. If one appears in a candidate, use «تعذر الحكم».

---

## 1. Renaming with synonyms (paragraph level)

**Idea:** one entity or concept gets different names inside a paragraph, so the reader must infer that X is Y.

**Candidate:** one paragraph, in `para`.

**Criterion** (count changes of name by a meaningful word; pronouns and ellipsis don't count):

| Label | Criterion |
|---|---|
| لا تغيير | Each entity or concept keeps the same or a near-identical word, or appears once |
| تغيير واحد | One entity changed name once, needing one link by the reader |
| تغييران | Two entities changed name, or one changed twice |
| ثلاثة فأكثر | Three or more changes |
| تعذر الحكم | The paragraph can't be analysed |

**Example:** «المشروع ← المبادرة ← الخطوة ← البرنامج» for one thing in one paragraph, or «تعزيز / تحسين / رفع / تطوير» for the same action.

**Edit direction** (after approval): unify on the first name. Don't replace a synonym carrying a real difference in meaning.

---

## 2. Cohesion between paragraphs

**Idea:** every paragraph grips the end of the last one with no jump, leaving the reader nothing to infer.

**Candidate:** each paragraph boundary (`prev_tail` is the last sentence before, `next_head` the first sentence after).

**Criterion** (if the second sentence opens with a connector, first check that its relation is real):

| Label | Criterion |
|---|---|
| أداة بلا علاقة | Opens with a connector (لكن، لذلك، بالتالي، في المقابل…) whose relation is weak or absent. **Check this first** |
| اتصال واضح | Same topic or relation, smooth transition, and any connector is correct |
| صلة بانتقال مفاجئ | Related, but a step is missing that the reader must supply |
| قفزة موضوعية | A nearly different topic, with no lead-in |
| تعذر الحكم | Not enough context |

**Calculation:** chain length is the run of consecutive «اتصال واضح» boundaries. Report the longest chain as a note, not a verdict.

**Edit direction** (after approval): pick one or two boundaries and make the move direct, after confirming they carry no needed causation or setup. Start with «أداة بلا علاقة». Leave links in reasoning chains in instructional and legal text.

---

## 3. Classifying colons

**Idea:** the total colon count reveals nothing (humans used more colons in our measurement). The target is one type: a sentence announcing a conclusion, then explaining it after the colon.

**Candidate:** a body sentence with a colon (`colon_before`, `colon_after`, `sentence`).

**Criterion** (top to bottom; stop at the first match):

| Label | Criterion |
|---|---|
| قول منقول | A speaker or speech verb before the colon (قال، أوضح، أضاف، كتب). **Takes priority** |
| بيانات شكلية | Title, time, ratio, source, author name |
| تعريف أو تفصيل | A term or name before it, its definition or content after |
| تمهيد لقائمة | An empty announcement that points follow, with no claim, then a list. **Don't edit** |
| نتيجة معلنة | A standalone explicit judgement before it, its explanation after. **The only type to edit** |
| نقطتان أخريان | Default for anything else |
| تعذر الحكم | Not enough context; don't overuse it |

**Example:** «هذه الأرقام تكشف واقعًا قاسيًا: …»

**Edit direction** (after approval, «نتيجة معلنة» only): delete the announcement and write the content directly, or change only the punctuation if the first half connects to what precedes it.

---

## 4. Three sentences with identical structure

**Idea:** three consecutive sentences share one syntactic frame and differ only in the words filling it.

**Candidate:** three consecutive sentences that passed the rough filter (`sents`). The filter is broad and this judgement is narrower.

**Criterion** (judge the three sentences alone):

| Label | Criterion |
|---|---|
| تطابق عال | Verb, subject, object and complement in nearly matching positions; one frame, only words differ |
| تطابق جزئي | Clear similarity, but some parts don't correspond, or one is added or missing |
| تكرار لفظ فقط | Words repeat, but the grammatical arrangement differs |
| توازٍ في المعنى فقط | About things of one kind, with different structures |
| لا علاقة | No clear repetition or parallelism |
| تعذر الحكم | Not enough context, or incomplete sentences |

**Edit direction** (after approval): break the frame in one sentence by merging, splitting or reordering, deleting no information. Leave deliberate rhymed prose and parallelism, speeches, poetry, lists and event sequences as they are.

---

## Final calculation

| Measure | Calculation |
|---|---|
| Renaming per paragraph | Total changes ÷ paragraphs |
| Cohesion chain | Longest run of «اتصال واضح» |
| Announcing colons | «نتيجة معلنة» ÷ body colons |
| Identical sentences | Count of «تطابق عال» |

Report these values and their examples without calling them high or low. No thresholds are calibrated on Arabic yet. If you measure them on an Arabic corpus, add the thresholds and cite the source.
