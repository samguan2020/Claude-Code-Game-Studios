"""Unit and repository integration checks for the Copilot configuration port."""

from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile
import unittest

from sync_copilot import (
    ROOT, TOOL_MAP, adapt_body, convert_agent, convert_skill, generated_files,
    parse_document, render_document, strings, synchronize,
)


AGENT_SOURCE = """---
name: example
description: "Example role"
tools: Read, Glob, Grep, Write, Edit, Bash, Task
disallowedTools: Bash
model: sonnet
maxTurns: 10
---
Use the Task tool. Await Task.Delay(1000).
"""

SKILL_SOURCE = """---
name: example
description: "Example workflow"
argument-hint: "[scope]"
user-invocable: true
allowed-tools: Read, Glob, Grep
model: haiku
---
Read the supplied scope.
"""


class ConversionTests(unittest.TestCase):
    def test_frontmatter_round_trip_preserves_metadata(self):
        header = {"name": "example", "tools": ["read", "search"], "user-invocable": True}
        actual, body = parse_document(render_document(header, "Body\n"))
        self.assertEqual(header, actual)
        self.assertEqual("Body", body)

    def test_parser_accepts_comments_and_paths(self):
        header, _ = parse_document('---\n# source comment\npaths:\n  - "src/ai/**"\n---\nRules')
        self.assertEqual({"paths": ["src/ai/**"]}, header)

    def test_parser_rejects_duplicate_fields(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            parse_document("---\nname: example\nname: another\n---\nBody")

    def test_tool_conversion_preserves_denial(self):
        text = convert_agent(Path(".claude/agents/example.md"), AGENT_SOURCE)
        header, body = parse_document(text)
        self.assertNotIn("execute", header["tools"])
        self.assertEqual(["read", "search", "edit", "agent", "vscode/askQuestions"], header["tools"])
        self.assertNotIn("model", header)
        self.assertNotIn("maxTurns", header)
        self.assertIn("no-shell restriction", body)

    def test_task_api_code_is_not_renamed(self):
        _, body = parse_document(convert_agent(Path(".claude/agents/example.md"), AGENT_SOURCE))
        self.assertIn("agent tool (runSubagent)", body)
        self.assertIn("Task.Delay(1000)", body)

    def test_unknown_tool_or_metadata_is_rejected(self):
        for source in (
            AGENT_SOURCE.replace("Read, Glob", "UnknownTool, Glob"),
            AGENT_SOURCE.replace("maxTurns: 10", "unmappedFeature: true"),
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                convert_agent(Path(".claude/agents/example.md"), source)

    def test_read_only_skill_has_no_unsupported_permission_header(self):
        header, body = parse_document(
            convert_skill(Path(".claude/skills/example/SKILL.md"), SKILL_SOURCE),
        )
        self.assertNotIn("allowed-tools", header)
        self.assertIn("read-only: do not write files", body)
        self.assertIn("not a Copilot tool permission setting", body)

    def test_explicit_only_skill_cannot_auto_invoke(self):
        source = SKILL_SOURCE + "\nExplicit invocation only"
        header, _ = parse_document(convert_skill(Path(".claude/skills/example/SKILL.md"), source))
        self.assertIs(header["disable-model-invocation"], True)

    def test_unknown_dynamic_context_is_rejected(self):
        source = SKILL_SOURCE.replace("model: haiku", "context: |\n  !echo test")
        with self.assertRaisesRegex(ValueError, "no explicit replacement"):
            convert_skill(Path(".claude/skills/example/SKILL.md"), source)

    def test_arguments_references_and_imports_use_copilot_forms(self):
        body = (
            "$ARGUMENTS[0] $ARGUMENTS AskUserQuestion TodoWrite via Task\n"
            ".claude/agents/producer.md .claude/skills/help/SKILL.md\n"
            "@docs/engine-reference/godot/VERSION.md\nCLAUDE.md"
        )
        result = adapt_body(body)
        self.assertNotIn("$ARGUMENTS", result)
        self.assertNotIn("@docs", result)
        self.assertIn(".github/agents/producer.agent.md", result)
        self.assertIn(".github/skills/help/SKILL.md", result)
        self.assertIn("AGENTS.md", result)

    def test_review_delegation_does_not_request_claude_sessions(self):
        source = "Task in this skill spawns a separate Claude session. Spawn parallel Task\nagents."
        result = adapt_body(source)
        self.assertNotIn("Claude session", result)
        self.assertNotIn("Task", result)
        self.assertIn("parallel subagents", result)


class RepositoryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs = generated_files(ROOT)

    def test_complete_source_inventory(self):
        self.assertEqual(49, sum("agents" in path.parts for path in self.outputs))
        self.assertEqual(73, sum("skills" in path.parts for path in self.outputs))
        self.assertEqual(11, sum("instructions" in path.parts for path in self.outputs))

    def test_generated_files_are_current(self):
        self.assertEqual([], synchronize(ROOT, write=False))

    def test_native_agent_headers(self):
        allowed = {"name", "description", "tools", "agents", "user-invocable", "disable-model-invocation"}
        for path, text in self.outputs.items():
            if "agents" not in path.parts:
                continue
            with self.subTest(path=path):
                header, _ = parse_document(text)
                self.assertLessEqual(header.keys(), allowed)
                self.assertEqual(path.name, header["name"] + ".agent.md")
                self.assertLessEqual(set(header["tools"]), set(TOOL_MAP.values()))
                if "agents" in header:
                    self.assertIn("agent", header["tools"])

    def test_native_skill_headers(self):
        allowed = {"name", "description", "argument-hint", "user-invocable", "disable-model-invocation"}
        for path, text in self.outputs.items():
            if "skills" not in path.parts:
                continue
            with self.subTest(path=path):
                header, body = parse_document(text)
                self.assertLessEqual(header.keys(), allowed)
                self.assertEqual(path.parent.name, header["name"])
                self.assertRegex(header["name"], r"^[a-z0-9-]{1,64}$")
                self.assertLessEqual(len(header["description"]), 1024)
                self.assertIn("Copilot runtime contract", body)
                self.assertNotRegex(body, r"\$ARGUMENTS|\bAskUserQuestion\b|\bTodoWrite\b|subagent_type:")

    def test_rule_globs_preserve_scope(self):
        for source in (ROOT / ".claude/rules").glob("*.md"):
            original, _ = parse_document(source.read_text(encoding="utf-8"))
            target = Path(".github/instructions") / (source.stem + ".instructions.md")
            result, _ = parse_document(self.outputs[target])
            self.assertEqual(",".join(strings(original["paths"])), result["applyTo"])

    def test_migration_links_and_preloaded_roles_resolve(self):
        for path, text in self.outputs.items():
            # Only relative configuration links, not runtime output/template placeholders.
            for link in re.findall(r"\]\((\.\./[^)\s]+)\)", text):
                with self.subTest(path=path, link=link):
                    self.assertTrue((ROOT / path.parent / link).resolve().exists())

    def test_context_injections_have_explicit_replacements(self):
        for name in ("help", "changelog", "sprint-plan"):
            text = self.outputs[Path(f".github/skills/{name}/SKILL.md")]
            header, body = parse_document(text)
            self.assertNotIn("context", header)
            self.assertIn("Context gathering (explicit, not shell injection)", body)
            self.assertNotRegex(body, r"(?m)^\s*!(?:echo|git|ls)\b")

    def test_release_and_hotfix_stay_manual(self):
        for name in ("hotfix", "launch-checklist", "release-checklist"):
            header, _ = parse_document(self.outputs[Path(f".github/skills/{name}/SKILL.md")])
            self.assertIs(header["disable-model-invocation"], True)

    def test_workspace_selects_only_native_project_skills(self):
        settings = json.loads((ROOT / ".vscode/settings.json").read_text(encoding="utf-8"))
        self.assertTrue(settings["chat.agentSkillsLocations"][".github/skills"])
        self.assertFalse(settings["chat.agentSkillsLocations"][".claude/skills"])
        self.assertFalse(settings["chat.agentSkillsLocations"][".agents/skills"])
        self.assertFalse(settings["chat.useClaudeHooks"])
        self.assertNotIn("chat.tools.global.autoApprove", settings)

    def test_setup_engine_edits_shared_instructions_and_native_agents(self):
        text = self.outputs[Path(".github/skills/setup-engine/SKILL.md")]
        self.assertIn("Update AGENTS.md Technology Stack", text)
        self.assertIn("[Engine version reference](docs/engine-reference/<engine>/VERSION.md)", text)
        self.assertIn(".agent.md", text)
        self.assertNotIn("CLAUDE.md", text)

    def test_team_guard_precedes_context_and_delegation(self):
        text = self.outputs[Path(".github/skills/team-combat/SKILL.md")]
        self.assertLess(text.index("argument guard first"), text.index("Copilot runtime contract"))
        self.assertIn("Usage: `/team-combat [combat feature description]`", text)
        self.assertIn("stop immediately without spawning any subagents or reading any files", text)

    def test_runtime_has_parent_mediated_approvals(self):
        text = (ROOT / ".github/copilot-instructions.md").read_text(encoding="utf-8")
        self.assertIn("NEEDS_APPROVAL", text)
        self.assertIn("starts a fresh worker", text)
        self.assertIn("Nested delegation is not required", text)
        self.assertIn("No commits, pushes", text)

    def test_generation_is_idempotent_and_protects_existing_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = {
                ".claude/agents/example.md": AGENT_SOURCE,
                ".claude/skills/example/SKILL.md": SKILL_SOURCE,
                ".claude/rules/example.md": '---\npaths:\n  - "src/**"\n---\nRules',
            }
            for name, text in sources.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            self.assertEqual(3, len(synchronize(root, write=True)))
            self.assertEqual([], synchronize(root, write=True))
            agent = root / ".github/agents/example.agent.md"
            agent.write_text("Local edit\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                synchronize(root, write=True)
            self.assertEqual("Local edit\n", agent.read_text(encoding="utf-8"))
            self.assertEqual(1, len(synchronize(root, write=True, overwrite=True)))
            self.assertEqual([], synchronize(root, write=False))


if __name__ == "__main__":
    unittest.main()
