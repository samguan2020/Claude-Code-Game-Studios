"""Generate Copilot-native studio definitions from the preserved Claude sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOL_MAP = {
    "Read": "read",
    "Glob": "search",
    "Grep": "search",
    "Write": "edit",
    "Edit": "edit",
    "Bash": "execute",
    "Task": "agent",
    "WebSearch": "web",
    "WebFetch": "web",
    "AskUserQuestion": "vscode/askQuestions",
    "TodoWrite": "todo",
}
COORDINATORS = {
    "creative-director", "technical-director", "producer", "lead-programmer",
    "game-designer", "qa-lead", "release-manager",
}
AGENT_FIELDS = {
    "name", "description", "tools", "model", "maxTurns", "disallowedTools",
    "memory", "skills", "isolation",
}
SKILL_FIELDS = {
    "name", "description", "argument-hint", "user-invocable", "allowed-tools",
    "model", "agent", "context", "isolation", "disable-model-invocation",
}
CONTEXT_READS = {
    "help": (
        "Read `production/stage.txt`, list `production/sprints/`, and read the "
        "opening of `production/session-state/active.md` when present. Report "
        "missing state as missing; do not create it during this read-only skill."
    ),
    "changelog": (
        "Use the terminal to run `git --no-pager log --oneline -30` and "
        "`git tag --list --sort=-v:refname`; inspect the first five tags. "
        "Report Git errors instead of suppressing them."
    ),
    "sprint-plan": (
        "List `production/sprints/` with file search before planning. If the "
        "directory is absent, report that no sprint history exists."
    ),
}


def parse_scalar(value: str) -> object:
    """Parse the deliberately limited YAML subset used by the source headers."""
    if value.startswith('"'):
        return json.loads(value)
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    if value.startswith("[") and value.endswith("]"):
        return [parse_scalar(item.strip()) for item in value[1:-1].split(",") if item.strip()]
    if value in ("true", "false"):
        return value == "true"
    if re.fullmatch(r"\d+", value):
        return int(value)
    if not value or value[0] in "{&*!>|":
        raise ValueError(f"Unsupported frontmatter value: {value!r}")
    return value


def parse_document(text: str) -> tuple[dict[str, object], str]:
    """Read source frontmatter, rejecting duplicate keys and unsupported shapes."""
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("Missing frontmatter")
    end = lines.index("---", 1)
    header: dict[str, object] = {}
    index = 1
    while index < end:
        line = lines[index]
        index += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([a-zA-Z][a-zA-Z-]*):\s*(.*)", line)
        if not match:
            raise ValueError(f"Unsupported frontmatter line: {line!r}")
        key, value = match.groups()
        if key in header:
            raise ValueError(f"Duplicate frontmatter key: {key}")
        if value == "|":
            block = []
            while index < end and (not lines[index].strip() or lines[index].startswith("  ")):
                block.append(lines[index][2:])
                index += 1
            header[key] = "\n".join(block)
        elif not value:
            entries = []
            while index < end and lines[index].startswith("  - "):
                entries.append(parse_scalar(lines[index][4:]))
                index += 1
            if not entries:
                raise ValueError(f"Empty frontmatter field: {key}")
            header[key] = entries
        else:
            header[key] = parse_scalar(value)
    return header, "\n".join(lines[end + 1:]).strip()


def strings(value: object) -> list[str]:
    """Normalize source inline lists and comma-separated tool declarations."""
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError(f"Expected a string list, got {value!r}")


def render_document(header: dict[str, object], body: str) -> str:
    """Write JSON-compatible YAML scalars without introducing a YAML dependency."""
    fields = [f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in header.items()]
    lines = ["---", *fields, "---", "", body.strip()]
    return "\n".join(line.rstrip() for line in "\n".join(lines).splitlines()).rstrip() + "\n"


def adapt_body(body: str) -> str:
    """Translate host-specific instructions, preserving domain code and shared docs."""
    replacements = {
        ".claude/skills/": ".github/skills/",
        ".claude/agents/": ".github/agents/",
        "CLAUDE.md": "AGENTS.md",
        "Claude Code Game Studios": "Game Studios for GitHub Copilot",
        "Claude Code session": "GitHub Copilot chat session",
        "AskUserQuestion": "vscode/askQuestions",
        "TodoWrite": "todo",
        "WebSearch": "web search",
        "WebFetch": "web fetch",
        "Write/Edit tools": "edit tools",
        "Task tool": "agent tool (runSubagent)",
        "Task subagent": "Copilot subagent",
        "Task calls": "runSubagent calls",
        "Task call": "runSubagent call",
        "Task prompt": "subagent prompt",
        "Task in this skill": "runSubagent in this skill",
        "parallel Task\nagents": "parallel subagents",
        "parallel Task agents": "parallel subagents",
        "Claude session": "Copilot subagent context",
        "via Task": "via runSubagent",
        "Use Task": "Use runSubagent",
        "subagent_type:": "agentName:",
        "$ARGUMENTS[0]": "the first supplied argument",
        "$ARGUMENTS": "the supplied arguments",
        "/clear": "a new chat",
        "/compact": "a context checkpoint",
    }
    for old, new in replacements.items():
        body = body.replace(old, new)
    body = re.sub(r"\bBash\b", "terminal", body)
    body = re.sub(r"\bGrep\b", "text search", body)
    body = re.sub(r"\bGlob\b", "file search", body)
    body = re.sub(
        r"(\.github/agents/[a-z0-9-]+)\.md\b", r"\1.agent.md", body,
    )
    # Copilot follows Markdown references; Claude's @ imports are not portable.
    body = re.sub(
        r"^@docs/(.+)$", r"[Engine version reference](docs/\1)", body, flags=re.MULTILINE,
    )
    body = body.replace("`@` import", "Markdown link").replace(
        "## 8. Update AGENTS.md Import", "## 8. Update AGENTS.md Reference",
    )
    return body


def runtime_preamble(source: Path, kind: str) -> str:
    link = "../copilot-instructions.md" if kind == "agent" else "../../copilot-instructions.md"
    guard = (
        "Check the workflow's argument guard first. If required arguments are "
        "missing, return its usage message and stop without reading other files "
        "or delegating. Otherwise, "
        if kind == "skill" else ""
    )
    return (
        f"<!-- Generated by tools/sync_copilot.py from {source.as_posix()}. -->\n\n"
        f"{guard}read the [Copilot runtime contract]({link}) before executing this workflow. "
        "Its host/tool, approval, and delegation rules apply to the instructions below. "
        "Repository paths below are relative to the selected project root.\n\n"
    )


def convert_agent(source: Path, text: str) -> str:
    meta, body = parse_document(text)
    unknown = meta.keys() - AGENT_FIELDS
    if unknown:
        raise ValueError(f"{source}: unmapped agent fields: {sorted(unknown)}")
    name = meta["name"]
    if name != source.stem:
        raise ValueError(f"{source}: agent name differs from filename")
    allowed = strings(meta["tools"])
    denied = strings(meta.get("disallowedTools", []))
    if set(allowed + denied) - TOOL_MAP.keys():
        raise ValueError(f"{source}: unknown source tools")
    tools = list(dict.fromkeys(TOOL_MAP[tool] for tool in allowed if tool not in denied))
    if name in COORDINATORS and "agent" not in tools:
        tools.append("agent")
    tools.append("vscode/askQuestions")
    header: dict[str, object] = {
        "name": name,
        "description": meta["description"],
        "tools": list(dict.fromkeys(tools)),
        "user-invocable": True,
        "disable-model-invocation": False,
    }
    if "agent" in tools:
        header["agents"] = ["*"]
    notes = runtime_preamble(source, "agent")
    if denied:
        notes += (
            "Do not use terminal execution, including through another agent, "
            "to bypass this role's no-shell restriction.\n\n"
        )
    if "skills" in meta:
        links = [
            f"[{skill}](../skills/{skill}/SKILL.md)" for skill in strings(meta["skills"])
        ]
        notes += "Load these related skills when relevant (not automatically): " + ", ".join(links) + ".\n\n"
    if "memory" in meta:
        notes += (
            "Persistent Claude agent memory is not provisioned here. Read approved "
            "project documents and existing session state; do not assume prior chats "
            "or user-global memory are available.\n\n"
        )
    if "isolation" in meta:
        notes += (
            "No automatic worktree is created. Keep prototypes isolated in their "
            "directory; obtain approval before creating a branch or worktree.\n\n"
        )
    return render_document(header, notes + adapt_body(body))


def convert_skill(source: Path, text: str) -> str:
    meta, body = parse_document(text)
    unknown = meta.keys() - SKILL_FIELDS
    if unknown:
        raise ValueError(f"{source}: unmapped skill fields: {sorted(unknown)}")
    name = meta["name"]
    if name != source.parent.name:
        raise ValueError(f"{source}: skill name differs from directory")
    header = {
        key: adapt_body(value) if isinstance(value, str) else value
        for key, value in meta.items()
        if key in {"name", "description", "argument-hint", "user-invocable", "disable-model-invocation"}
    }
    if re.search(r"explicit invocation only", body, re.IGNORECASE):
        header["disable-model-invocation"] = True
    notes = runtime_preamble(source, "skill")
    allowed = strings(meta["allowed-tools"])
    if set(allowed) - TOOL_MAP.keys():
        raise ValueError(f"{source}: unknown source tools")
    budget = list(dict.fromkeys(TOOL_MAP[tool] for tool in allowed))
    notes += (
        f"Workflow capability budget: {', '.join(budget)}. "
        "This is an instruction-level limit, not a Copilot tool permission setting. "
        "Do not use other capabilities to bypass it; report missing tools.\n\n"
    )
    if "edit" not in budget:
        notes += "This workflow is read-only: do not write files, including checkpoints or reports.\n\n"
    if "agent" in meta:
        role = meta["agent"]
        notes += (
            f"Use the [{role} role](../../agents/{role}.agent.md) for specialist "
            "guidance. The skill stays in the parent chat for user decisions; "
            "delegate bounded specialist work only when needed. Do not claim that "
            "a skill header switched the active agent or preloaded its tools.\n\n"
        )
    if "context" in meta:
        if name not in CONTEXT_READS:
            raise ValueError(f"{source}: no explicit replacement for shell context")
        notes += "### Context gathering (explicit, not shell injection)\n\n" + CONTEXT_READS[name] + "\n\n"
    if "isolation" in meta:
        notes += (
            "No automatic worktree isolation is configured. Request approval "
            "before creating a branch/worktree; otherwise remain in the approved "
            "prototype directory.\n\n"
        )
    if name == "setup-engine":
        notes += (
            "Update the shared `AGENTS.md` Technology Stack and its Markdown "
            "engine-reference link. Edit Copilot specialists only under "
            "`.github/agents/` using the `.agent.md` suffix. Keep "
            "`.claude/docs/technical-preferences.md` as the shared preferences file.\n\n"
        )
    return render_document(header, notes + adapt_body(body))


def convert_rule(source: Path, text: str) -> str:
    meta, body = parse_document(text)
    if set(meta) != {"paths"}:
        raise ValueError(f"{source}: unmapped rule fields")
    header = {"applyTo": ",".join(strings(meta["paths"]))}
    note = f"<!-- Generated by tools/sync_copilot.py from {source.as_posix()}. -->\n\n"
    return render_document(header, note + adapt_body(body))


def generated_files(root: Path) -> dict[Path, str]:
    """Build all outputs in memory before making any filesystem changes."""
    outputs: dict[Path, str] = {}
    groups = [
        (".claude/agents", "*.md", convert_agent),
        (".claude/skills", "*/SKILL.md", convert_skill),
        (".claude/rules", "*.md", convert_rule),
    ]
    for folder, pattern, converter in groups:
        sources = sorted((root / folder).glob(pattern))
        if not sources:
            raise ValueError(f"No sources found under {folder}")
        for source in sources:
            relative = source.relative_to(root)
            if converter is convert_agent:
                target = Path(".github/agents") / f"{source.stem}.agent.md"
            elif converter is convert_skill:
                target = Path(".github/skills") / source.parent.name / "SKILL.md"
            else:
                target = Path(".github/instructions") / f"{source.stem}.instructions.md"
            outputs[target] = converter(relative, source.read_text(encoding="utf-8"))
    resources = [
        path for path in (root / ".claude/skills").rglob("*")
        if path.is_file() and path.name != "SKILL.md"
    ]
    if resources:
        raise ValueError("New bundled skill resources require an explicit migration: " + str(resources))
    return outputs


def synchronize(root: Path, write: bool, overwrite: bool = False) -> list[str]:
    """Check generated output, or write it without silently overwriting local edits."""
    outputs = generated_files(root)
    differences = [
        str(path) for path, text in outputs.items()
        if not (root / path).exists() or (root / path).read_text(encoding="utf-8") != text
    ]
    extras = []
    for folder, pattern in (
        (".github/agents", "*.agent.md"),
        (".github/skills", "*/SKILL.md"),
        (".github/instructions", "*.instructions.md"),
    ):
        for path in (root / folder).glob(pattern):
            if path.relative_to(root) not in outputs:
                extras.append(str(path.relative_to(root)))
    if extras:
        raise ValueError("Unmapped Copilot definitions; reconcile manually: " + ", ".join(extras))
    if write:
        changed_existing = [path for path in differences if (root / path).exists()]
        if changed_existing and not overwrite:
            raise ValueError(
                "Refusing to overwrite changed definitions; review and use --overwrite explicitly: "
                + ", ".join(changed_existing)
            )
        for path, text in outputs.items():
            if str(path) in differences:
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_text(text, encoding="utf-8", newline="\n")
    return differences


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Check generated files without writing")
    mode.add_argument("--write", action="store_true", help="Create missing Copilot definitions")
    parser.add_argument("--overwrite", action="store_true", help="Explicitly replace changed definitions")
    args = parser.parse_args()
    if args.overwrite and not args.write:
        parser.error("--overwrite requires --write")
    try:
        differences = synchronize(ROOT, args.write, args.overwrite)
    except (ValueError, OSError) as error:
        print(f"Copilot migration failed: {error}", file=sys.stderr)
        return 1
    if args.check and differences:
        print("Copilot definitions differ:\n" + "\n".join(differences), file=sys.stderr)
        return 1
    counts = {name: 0 for name in ("agents", "skills", "instructions")}
    for path in generated_files(ROOT):
        counts[path.parts[1]] += 1
    print(
        f"Copilot definitions {'written' if args.write else 'verified'}: "
        f"{sum(counts.values())} ({counts['agents']} agents, {counts['skills']} skills, "
        f"{counts['instructions']} rules); {len(differences)} changed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
