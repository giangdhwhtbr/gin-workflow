import unittest
import sys
import os

# Add the scripts directory to the path so we can import review_ledger
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../plugins/gin-workflow/src/scripts')))

from review_ledger import jcs

class TestJCS(unittest.TestCase):
    def test_jcs_basic_types(self):
        self.assertEqual(jcs.serialize(None), "null")
        self.assertEqual(jcs.serialize(True), "true")
        self.assertEqual(jcs.serialize(False), "false")
        self.assertEqual(jcs.serialize(123), "123")
        self.assertEqual(jcs.serialize(-456), "-456")
        self.assertEqual(jcs.serialize("hello"), '"hello"')
        self.assertEqual(jcs.serialize("hello \"world\" \\"), '"hello \\"world\\" \\\\"')

    def test_jcs_dict_sorting(self):
        d = {"z": 1, "a": 2, "m": {"y": True, "x": False}}
        # Should sort keys: a, m, z. And inside m: x, y
        expected = '{"a":2,"m":{"x":false,"y":true},"z":1}'
        self.assertEqual(jcs.serialize(d), expected)

    def test_jcs_list(self):
        l = [1, "two", {"three": 3}]
        self.assertEqual(jcs.serialize(l), '[1,"two",{"three":3}]')

    def test_jcs_unicode(self):
        s = "hello \u000a \u00e9 \u4e2d\u6587"
        expected = '"hello \\n \u00e9 \u4e2d\u6587"'
        self.assertEqual(jcs.serialize(s), expected)

    def test_jcs_type_error(self):
        with self.assertRaises(TypeError):
            jcs.serialize(set([1, 2]))

if __name__ == "__main__":
    unittest.main()
