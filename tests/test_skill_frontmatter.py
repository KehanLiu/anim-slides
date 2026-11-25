"""SKILL.md frontmatter stays valid for strict YAML parsers and within the Agent Skills spec.

Stdlib only. When PyYAML is installed, the block is also parsed with yaml.safe_load.
Run: python3 -m unittest discover -s tests
"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "SKILL.md")
# The skill's name, not the checkout folder (a worktree may be named differently).
SKILL_NAME = "anim-slides"
DESCRIPTION_MAX = 1024


def frontmatter_lines():
    with open(SKILL, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if not lines or lines[0].strip() != "---":
        raise AssertionError("SKILL.md does not start with a --- frontmatter block")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i]
    raise AssertionError("SKILL.md frontmatter block is not closed with ---")


def parse(lines):
    """Parse the simple two-level mapping SKILL.md uses: key: value, and one level of nesting."""
    data, raw, parent = {}, [], None
    for n, line in enumerate(lines, 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^( *)([A-Za-z0-9_-]+):(?: (.*))?$", line)
        if not m:
            raise AssertionError("line %d is not a 'key: value' line: %r" % (n, line))
        indent, key, value = len(m.group(1)), m.group(2), m.group(3)
        if indent == 0:
            if value is None or value == "":
                data[key], parent = {}, key
            else:
                data[key], parent = value, None
        else:
            if parent is None:
                raise AssertionError("line %d is indented but has no parent key" % n)
            data[parent][key] = value
        if value:
            raw.append((n, key, value))
    return data, raw


def unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


class SkillFrontmatter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = frontmatter_lines()
        cls.data, cls.raw = parse(cls.lines)

    def test_plain_scalars_are_valid_yaml(self):
        # In an unquoted (plain) scalar, ": " starts a mapping and " #" starts a comment.
        for n, key, value in self.raw:
            if value[0] in "\"'":
                continue
            self.assertNotIn(": ", value, "line %d (%s): ': ' inside an unquoted value" % (n, key))
            self.assertNotIn(" #", value, "line %d (%s): ' #' inside an unquoted value" % (n, key))

    def test_name(self):
        self.assertEqual(unquote(self.data.get("name", "")), SKILL_NAME)

    def test_description_length(self):
        desc = unquote(self.data.get("description", ""))
        self.assertTrue(desc, "description is missing")
        self.assertLessEqual(len(desc), DESCRIPTION_MAX,
                             "description is %d characters, over %d" % (len(desc), DESCRIPTION_MAX))

    def test_version_matches_plugin_files(self):
        version = unquote(self.data.get("metadata", {}).get("version", ""))
        self.assertTrue(version, "metadata.version is missing")
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["version"], version, "plugin.json version")
        with open(os.path.join(ROOT, ".claude-plugin", "marketplace.json"), encoding="utf-8") as f:
            market = json.load(f)
        versions = [p.get("version") for p in market.get("plugins", []) if p.get("name") == SKILL_NAME]
        self.assertTrue(versions, "marketplace.json lists no plugin named " + SKILL_NAME)
        for v in versions:
            self.assertEqual(v, version, "marketplace.json version")

    def test_safe_load_when_available(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed; the stdlib checks above still ran")
        data = yaml.safe_load("\n".join(self.lines))
        self.assertIsInstance(data, dict)
        self.assertEqual(data["name"], SKILL_NAME)
        self.assertLessEqual(len(data["description"]), DESCRIPTION_MAX)
        self.assertEqual(str(data["metadata"]["version"]), unquote(self.data["metadata"]["version"]))


if __name__ == "__main__":
    unittest.main()
