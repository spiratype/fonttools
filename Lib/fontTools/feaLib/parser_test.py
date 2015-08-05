from __future__ import print_function, division, absolute_import
from __future__ import unicode_literals
from fontTools.feaLib.lexer import LexerError
from fontTools.feaLib.parser import Parser, ParserError, SymbolTable
from fontTools.misc.py23 import *
import fontTools.feaLib.ast as ast
import codecs
import os
import shutil
import sys
import tempfile
import unittest


class ParserTest(unittest.TestCase):
    def __init__(self, methodName):
        unittest.TestCase.__init__(self, methodName)
        # Python 3 renamed assertRaisesRegexp to assertRaisesRegex,
        # and fires deprecation warnings if a program uses the old name.
        if not hasattr(self, "assertRaisesRegex"):
            self.assertRaisesRegex = self.assertRaisesRegexp

    def test_glyphclass(self):
        [gc] = self.parse("@dash = [endash emdash figuredash];").statements
        self.assertEqual(gc.name, "dash")
        self.assertEqual(gc.glyphs, {"endash", "emdash", "figuredash"})

    def test_glyphclass_bad(self):
        self.assertRaisesRegex(
            ParserError,
            "Expected glyph name, glyph range, or glyph class reference",
            self.parse, "@bad = [a 123];")

    def test_glyphclass_duplicate(self):
        self.assertRaisesRegex(
            ParserError, "Glyph class @dup already defined",
            self.parse, "@dup = [a b]; @dup = [x];")

    def test_glyphclass_empty(self):
        [gc] = self.parse("@empty_set = [];").statements
        self.assertEqual(gc.name, "empty_set")
        self.assertEqual(gc.glyphs, set())

    def test_glyphclass_equality(self):
        [foo, bar] = self.parse("@foo = [a b]; @bar = @foo;").statements
        self.assertEqual(foo.glyphs, {"a", "b"})
        self.assertEqual(bar.glyphs, {"a", "b"})

    def test_glyphclass_range_uppercase(self):
        [gc] = self.parse("@swashes = [X.swash-Z.swash];").statements
        self.assertEqual(gc.name, "swashes")
        self.assertEqual(gc.glyphs, {"X.swash", "Y.swash", "Z.swash"})

    def test_glyphclass_range_lowercase(self):
        [gc] = self.parse("@defg.sc = [d.sc-g.sc];").statements
        self.assertEqual(gc.name, "defg.sc")
        self.assertEqual(gc.glyphs, {"d.sc", "e.sc", "f.sc", "g.sc"})

    def test_glyphclass_range_digit1(self):
        [gc] = self.parse("@range = [foo.2-foo.5];").statements
        self.assertEqual(gc.glyphs, {"foo.2", "foo.3", "foo.4", "foo.5"})

    def test_glyphclass_range_digit2(self):
        [gc] = self.parse("@range = [foo.09-foo.11];").statements
        self.assertEqual(gc.glyphs, {"foo.09", "foo.10", "foo.11"})

    def test_glyphclass_range_digit3(self):
        [gc] = self.parse("@range = [foo.123-foo.125];").statements
        self.assertEqual(gc.glyphs, {"foo.123", "foo.124", "foo.125"})

    def test_glyphclass_range_bad(self):
        self.assertRaisesRegex(
            ParserError,
            "Bad range: \"a\" and \"foobar\" should have the same length",
            self.parse, "@bad = [a-foobar];")
        self.assertRaisesRegex(
            ParserError, "Bad range: \"A.swash-z.swash\"",
            self.parse, "@bad = [A.swash-z.swash];")
        self.assertRaisesRegex(
            ParserError, "Start of range must be smaller than its end",
            self.parse, "@bad = [B.swash-A.swash];")
        self.assertRaisesRegex(
            ParserError, "Bad range: \"foo.1234-foo.9876\"",
            self.parse, "@bad = [foo.1234-foo.9876];")

    def test_glyphclass_range_mixed(self):
        [gc] = self.parse("@range = [a foo.09-foo.11 X.sc-Z.sc];").statements
        self.assertEqual(gc.glyphs, {
            "a", "foo.09", "foo.10", "foo.11", "X.sc", "Y.sc", "Z.sc"
        })

    def test_glyphclass_reference(self):
        [vowels_lc, vowels_uc, vowels] = self.parse(
            "@Vowels.lc = [a e i o u]; @Vowels.uc = [A E I O U];"
            "@Vowels = [@Vowels.lc @Vowels.uc y Y];").statements
        self.assertEqual(vowels_lc.glyphs, set(list("aeiou")))
        self.assertEqual(vowels_uc.glyphs, set(list("AEIOU")))
        self.assertEqual(vowels.glyphs, set(list("aeiouyAEIOUY")))
        self.assertRaisesRegex(
            ParserError, "Unknown glyph class @unknown",
            self.parse, "@bad = [@unknown];")

    def test_glyphclass_scoping(self):
        [foo, liga, smcp] = self.parse(
            "@foo = [a b];"
            "feature liga { @bar = [@foo l]; } liga;"
            "feature smcp { @bar = [@foo s]; } smcp;"
        ).statements
        self.assertEqual(foo.glyphs, {"a", "b"})
        self.assertEqual(liga.statements[0].glyphs, {"a", "b", "l"})
        self.assertEqual(smcp.statements[0].glyphs, {"a", "b", "s"})

    def test_ignore_sub(self):
        doc = self.parse("feature test {ignore sub e t' c;} test;")
        s = doc.statements[0].statements[0]
        self.assertEqual(type(s), ast.IgnoreSubstitutionRule)
        self.assertEqual(s.prefix, [{"e"}])
        self.assertEqual(s.glyphs, [{"t"}])
        self.assertEqual(s.suffix, [{"c"}])

    def test_ignore_substitute(self):
        doc = self.parse(
            "feature test {"
            "    ignore substitute f [a e] d' [a u]' [e y];"
            "} test;")
        s = doc.statements[0].statements[0]
        self.assertEqual(type(s), ast.IgnoreSubstitutionRule)
        self.assertEqual(s.prefix, [{"f"}, {"a", "e"}])
        self.assertEqual(s.glyphs, [{"d"}, {"a", "u"}])
        self.assertEqual(s.suffix, [{"e", "y"}])

    def test_substitute_single_format_a(self):  # GSUB LookupType 1
        doc = self.parse("feature smcp {substitute a by a.sc;} smcp;")
        sub = doc.statements[0].statements[0]
        self.assertEqual(sub.old_prefix, [])
        self.assertEqual(sub.old, [{"a"}])
        self.assertEqual(sub.old_suffix, [])
        self.assertEqual(sub.new, [{"a.sc"}])

    def test_substitute_single_format_b(self):  # GSUB LookupType 1
        doc = self.parse(
            "feature smcp {"
            "    substitute [one.fitted one.oldstyle] by one;"
            "} smcp;")
        sub = doc.statements[0].statements[0]
        self.assertEqual(sub.old_prefix, [])
        self.assertEqual(sub.old, [{"one.fitted", "one.oldstyle"}])
        self.assertEqual(sub.old_suffix, [])
        self.assertEqual(sub.new, [{"one"}])

    def test_substitute_single_format_c(self):  # GSUB LookupType 1
        doc = self.parse(
            "feature smcp {"
            "    substitute [a-d] by [A.sc-D.sc];"
            "} smcp;")
        sub = doc.statements[0].statements[0]
        self.assertEqual(sub.old_prefix, [])
        self.assertEqual(sub.old, [{"a", "b", "c", "d"}])
        self.assertEqual(sub.old_suffix, [])
        self.assertEqual(sub.new, [{"A.sc", "B.sc", "C.sc", "D.sc"}])

    def test_substitute_ligature(self):  # GSUB LookupType 4
        doc = self.parse("feature liga {substitute f f i by f_f_i;} liga;")
        sub = doc.statements[0].statements[0]
        self.assertEqual(sub.old_prefix, [])
        self.assertEqual(sub.old, [{"f"}, {"f"}, {"i"}])
        self.assertEqual(sub.old_suffix, [])
        self.assertEqual(sub.new, [{"f_f_i"}])

    def test_substitute_missing_by(self):
        self.assertRaisesRegex(
            ParserError, "Expected \"by\"",
            self.parse, "feature liga {substitute f f i;} liga;")

    def test_valuerecord_format_a_horizontal(self):
        doc = self.parse("feature liga {valueRecordDef 123 foo;} liga;")
        value = doc.statements[0].statements[0].value
        self.assertEqual(value.xPlacement, 0)
        self.assertEqual(value.yPlacement, 0)
        self.assertEqual(value.xAdvance, 123)
        self.assertEqual(value.yAdvance, 0)

    def test_valuerecord_format_a_vertical(self):
        doc = self.parse("feature vkrn {valueRecordDef 123 foo;} vkrn;")
        value = doc.statements[0].statements[0].value
        self.assertEqual(value.xPlacement, 0)
        self.assertEqual(value.yPlacement, 0)
        self.assertEqual(value.xAdvance, 0)
        self.assertEqual(value.yAdvance, 123)

    def test_valuerecord_format_b(self):
        doc = self.parse("feature liga {valueRecordDef <1 2 3 4> foo;} liga;")
        value = doc.statements[0].statements[0].value
        self.assertEqual(value.xPlacement, 1)
        self.assertEqual(value.yPlacement, 2)
        self.assertEqual(value.xAdvance, 3)
        self.assertEqual(value.yAdvance, 4)

    def test_valuerecord_named(self):
        doc = self.parse("valueRecordDef <1 2 3 4> foo;"
                         "feature liga {valueRecordDef <foo> bar;} liga;")
        value = doc.statements[1].statements[0].value
        self.assertEqual(value.xPlacement, 1)
        self.assertEqual(value.yPlacement, 2)
        self.assertEqual(value.xAdvance, 3)
        self.assertEqual(value.yAdvance, 4)

    def test_valuerecord_named_unknown(self):
        self.assertRaisesRegex(
            ParserError, "Unknown valueRecordDef \"unknown\"",
            self.parse, "valueRecordDef <unknown> foo;")

    def test_valuerecord_scoping(self):
        [foo, liga, smcp] = self.parse(
            "valueRecordDef 789 foo;"
            "feature liga {valueRecordDef <foo> bar;} liga;"
            "feature smcp {valueRecordDef <foo> bar;} smcp;"
        ).statements
        self.assertEqual(foo.value.xAdvance, 789)
        self.assertEqual(liga.statements[0].value.xAdvance, 789)
        self.assertEqual(smcp.statements[0].value.xAdvance, 789)

    def test_languagesystem(self):
        [langsys] = self.parse("languagesystem latn DEU;").statements
        self.assertEqual(langsys.script, "latn")
        self.assertEqual(langsys.language, "DEU ")
        self.assertRaisesRegex(
            ParserError, "Expected ';'",
            self.parse, "languagesystem latn DEU")
        self.assertRaisesRegex(
            ParserError, "longer than 4 characters",
            self.parse, "languagesystem foobar DEU")
        self.assertRaisesRegex(
            ParserError, "longer than 4 characters",
            self.parse, "languagesystem latn FOOBAR")

    def test_feature_block(self):
        [liga] = self.parse("feature liga {} liga;").statements
        self.assertEqual(liga.tag, "liga")

    # TODO: Implement the needed bits in the parser.
    @unittest.expectedFailure
    def test_roundtrip(self):
        self.roundtrip("mini.fea")

    def setUp(self):
        self.tempdir = None
        self.num_tempfiles = 0

    def tearDown(self):
        if self.tempdir:
            shutil.rmtree(self.tempdir)

    def parse(self, text):
        if not self.tempdir:
            self.tempdir = tempfile.mkdtemp()
        self.num_tempfiles += 1
        path = os.path.join(self.tempdir, "tmp%d.fea" % self.num_tempfiles)
        with codecs.open(path, "wb", "utf-8") as outfile:
            outfile.write(text)
        return Parser(path).parse()

    def roundtrip(self, testfile):
        buffer1, buffer2 = StringIO(), StringIO()
        Parser(ParserTest.getpath(testfile)).parse().write(buffer1, os.linesep)
        text1 = buffer1.getvalue().decode("utf-8")
        self.parse(text1).write(buffer2, os.linesep)
        text2 = buffer2.getvalue().decode("utf-8")
        self.assertEqual(text1, text2)

    @staticmethod
    def getpath(testfile):
        path, _ = os.path.split(__file__)
        return os.path.join(path, "testdata", testfile)


class SymbolTableTest(unittest.TestCase):
    def test_scopes(self):
        symtab = SymbolTable()
        symtab.define("foo", 23)
        self.assertEqual(symtab.resolve("foo"), 23)
        symtab.enter_scope()
        self.assertEqual(symtab.resolve("foo"), 23)
        symtab.define("foo", 42)
        self.assertEqual(symtab.resolve("foo"), 42)
        symtab.exit_scope()
        self.assertEqual(symtab.resolve("foo"), 23)

    def test_resolve_undefined(self):
        self.assertEqual(SymbolTable().resolve("abc"), None)


if __name__ == "__main__":
    unittest.main()
