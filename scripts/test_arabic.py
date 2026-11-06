#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests. Run: python3 scripts/test_arabic.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from arabic import COMPILED, doc_features, mask_protected, norm, norm_map, split_sents, word_count
from detect import RULES, find_hits, measure_docs
from report import inline_diff


def count(key, text):
    return doc_features(text)["counts"][key]


class Protection(unittest.TestCase):
    def test_quran_brackets_masked(self):
        self.assertEqual(mask_protected("﴿ليس مجرد﴾").strip(), "")

    def test_quotes_masked(self):
        self.assertEqual(count("neg_formula", "قال المعلم «ليس مجرد كتاب بل منهج» في كلمته أمس."), 0)

    def test_vocalised_line_masked(self):
        line = "إِنَّ مَعَ الْعُسْرِ يُسْرًا مِمَّا يَعْكِسُ"
        self.assertEqual(mask_protected(line).strip(), "")

    def test_mask_keeps_length(self):
        s = "نص «مقتبس» هنا"
        self.assertEqual(len(mask_protected(s)), len(s))

    def test_code_and_markdown_quote_skipped(self):
        text = "```\nبالإضافة إلى\n```\n\n> بالإضافة إلى\n\nجملة عادية في المتن هنا."
        self.assertEqual(count("tr_bil_idafa", text), 0)


class Normalisation(unittest.TestCase):
    def test_folds_variants(self):
        self.assertEqual(norm("أإآ مُدرّسة"), "ااا مدرسه")

    def test_map_points_to_original(self):
        s = "إِنّ"
        n, idx = norm_map(s)
        self.assertEqual(s[idx[0]], "إ")
        self.assertEqual(len(n), len(idx))

    def test_excerpt_keeps_author_spelling(self):
        hits = find_hits("t", "قال إنها مهمّة، بالإضافة إلى أنها مفيدة جدًّا.")
        self.assertIn("بالإضافة", hits["tr_bil_idafa"][0]["excerpt"])


class Patterns(unittest.TestCase):
    def test_haythu_connector(self):
        self.assertEqual(count("tr_haythu_comma", "ارتفعت الأسعار، حيث بلغت الزيادة كثيرًا هذا العام."), 1)

    def test_haythu_not_min_haythu(self):
        self.assertEqual(count("tr_haythu", "هذا جيد من حيث المعنى والمبنى في النص."), 0)

    def test_haythu_not_bihaythu(self):
        self.assertEqual(count("tr_haythu", "رتبناها بحيث تناسب الجميع في المكان."), 0)

    def test_mimma_eval_not_kama(self):
        self.assertEqual(count("tr_mimma_eval", "كما يعزز هذا الغذاء صحة العظام عند الكبار."), 0)

    def test_definite_grandiose(self):
        self.assertEqual(count("lex_grandiose", "هذا هو الدور الجوهري في عمل الفريق كله."), 1)

    def test_era_not_afternoon(self):
        self.assertEqual(count("filler_era", "خرج الوفد في عصر أمس من المدينة إلى القرية."), 0)

    def test_close_only_at_sentence_start(self):
        self.assertEqual(count("close_start", "وصل القطار في النهاية إلى المحطة بعد تأخر طويل."), 0)
        self.assertEqual(count("close_start", "مضى اليوم بسلام وهدوء. في النهاية عاد الجميع إلى البيت."), 1)

    def test_every_rule_has_pattern(self):
        for _, key, *_ in RULES:
            self.assertIn(key, COMPILED)


class ShortText(unittest.TestCase):
    def test_short_text_still_measured(self):
        import subprocess, tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8", delete=False) as f:
            f.write("نص قصير جدًّا، حيث لا يبلغ الحد الأدنى من الكلمات المطلوبة.")
        script = str(Path(__file__).parent / "detect.py")
        r = subprocess.run([sys.executable, script, f.name, "--json"], capture_output=True, text=True)
        Path(f.name).unlink()
        self.assertEqual(r.returncode, 0)
        self.assertIn("meta", r.stdout)


class Segmentation(unittest.TestCase):
    def test_decimal_and_abbreviation(self):
        self.assertEqual(len(split_sents("قال د. أحمد إن النسبة بلغت 3.5 في المئة هذا العام.")), 1)

    def test_arabic_question_mark(self):
        self.assertEqual(len(split_sents("ما رأيك في هذا الأمر؟ أظن أنه جيد جدًّا.")), 2)

    def test_word_count_ignores_latin_and_digits(self):
        self.assertEqual(word_count("نشرت Apple تقريرًا في 2020"), 3)


class Report(unittest.TestCase):
    def test_diff_marks_whole_words(self):
        out = inline_diff("زادت الأمطار كثيرا", "زادت الثلوج كثيرا", lambda s: s)
        self.assertIn("<del>الأمطار</del>", out)
        self.assertIn("<ins>الثلوج</ins>", out)

    def test_measure_on_empty_prose(self):
        r = measure_docs([("t", "# عنوان فقط")])
        self.assertEqual(r["meta"]["words"], 0)


if __name__ == "__main__":
    unittest.main()
