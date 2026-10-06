# Game Studios -- Shared Agent Instructions

Indie game development supported by 49 specialist roles and 73 workflow skills,
adapted from Donchitos' open-source Claude Code Game Studios. Each role owns a
specific domain, enforcing separation of concerns and quality.

## Assistant Configuration

- GitHub Copilot: [runtime contract](.github/copilot-instructions.md),
  [custom agents](.github/agents/), and [skills](.github/skills/).
- Claude Code: [configuration](CLAUDE.md) and [.claude](.claude/).
- Codex: existing [.codex](.codex/) configuration and [.agents/skills](.agents/skills/).
- Use the configuration for the active assistant; do not combine duplicate
  skill definitions. Read referenced documents explicitly, not as `@` imports.
- [Migration and activation guide](docs/copilot-migration.md).

## Repository Scope

This root is the reusable studio harness, not a single game. Games under
[Games](Games/) are separate Git submodules with their own instructions and
technology choices. Select the target game before running its design or
implementation workflow; do not replace its configuration with root defaults.

## Technology Stack

- **Engine**: [CHOOSE: Godot 4 / Unity / Unreal Engine 5]
- **Language**: [CHOOSE: GDScript / C# / C++ / Blueprint]
- **Version Control**: Git with trunk-based development
- **Build System**: [SPECIFY after choosing engine]
- **Asset Pipeline**: [SPECIFY after choosing engine]

> **Note**: Engine-specialist agents exist for Godot, Unity, and Unreal with
> dedicated sub-specialists. Use the set matching your engine.

## Project Structure

[Directory structure](.claude/docs/directory-structure.md)

## Engine Version Reference

[Godot version reference](docs/engine-reference/godot/VERSION.md)

## Technical Preferences

[Shared technical preferences](.claude/docs/technical-preferences.md)

## Coordination Rules

[Coordination rules](.claude/docs/coordination-rules.md)

Role ownership and review gates are shared. Model identifiers, tools, hooks,
and agent-team mechanics in this legacy guide are host-specific; use the active
assistant's runtime contract rather than assuming Claude features exist.

## Collaboration Protocol

**User-driven collaboration, not autonomous execution.**
Every task follows: **Question -> Options -> Decision -> Draft -> Approval**

- Agents MUST ask "May I write this to [filepath]?" before using Write/Edit tools
- Agents MUST show drafts or summaries before requesting approval
- Multi-file changes require explicit approval for the full changeset
- No commits without user instruction

See [the collaborative design principle](docs/COLLABORATIVE-DESIGN-PRINCIPLE.md)
for full protocol and examples. In Copilot, the parent chat obtains approvals on
behalf of workers that cannot interact with the user.

> **First session?** If the project has no engine configured and no game concept,
> run `/start` to begin the guided onboarding flow.

## Coding Standards

[Coding standards](.claude/docs/coding-standards.md)

## Context Management

[Context management](.claude/docs/context-management.md)

File-backed checkpoints are shared practice. Automatic hooks, persistent agent
memory, and context-reset commands depend on the assistant; never claim they ran
without evidence.
