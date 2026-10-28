import io
import json
import unittest
from contextlib import redirect_stdout

import text_deobfuscate
from text_deobfuscate import Result, Step, deobfuscate
from text_deobfuscate.cli import main


class InterfaceTest(unittest.TestCase):
    def test_returns_a_result(self):
        result = deobfuscate("plain text")
        self.assertIsInstance(result, Result)
        self.assertEqual(result.text, "plain text")
        self.assertFalse(result.changed)

    def test_rejects_unknown_strictness(self):
        with self.assertRaises(ValueError):
            deobfuscate("x", strictness="reckless")

    def test_result_serialises_steps(self):
        step = Step("base64", 0, 4, "aGk=", "hi", 0.9)
        data = Result("hi", (step,)).to_dict()
        self.assertEqual(data["steps"][0]["transform"], "base64")
        json.dumps(data)

    def test_cli_adds_nothing_when_the_output_is_piped(self):
        out = io.StringIO()      # not a terminal, like a pipe or a redirect
        with redirect_stdout(out):
            self.assertEqual(main(["hello"]), 0)
        self.assertEqual(out.getvalue(), "hello")

    def test_version_is_reported_by_the_module_and_the_command(self):
        self.assertRegex(text_deobfuscate.__version__, r"^\d+\.\d+")
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as stopped:
            main(["--version"])
        self.assertEqual(stopped.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), f"text-deobfuscate {text_deobfuscate.__version__}")

    def test_cli_ends_the_line_for_a_terminal(self):
        class Terminal(io.StringIO):
            def isatty(self) -> bool:
                return True

        out = Terminal()
        with redirect_stdout(out):
            main(["hello"])
        self.assertEqual(out.getvalue(), "hello\n")

    def test_cli_prints_json(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["hello", "--json"]), 0)
        self.assertEqual(json.loads(out.getvalue()), {"text": "hello", "steps": []})


if __name__ == "__main__":
    unittest.main()
