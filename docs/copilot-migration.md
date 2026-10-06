# GitHub Copilot Studio Migration

This fork extends [Donchitos/Claude-Code-Game-Studios](https://github.com/Donchitos/Claude-Code-Game-Studios).
The Copilot port preserves the upstream studio responsibilities and workflows,
with native discovery files and explicit adaptations for GitHub Copilot in VS
Code. It is not a claim that the original 49 roles and 73 skills were all newly
authored in this fork.

## What is installed

| Component | Count | Copilot location |
|---|---:|---|
| Custom agents | 49 | [`.github/agents`](../.github/agents/) (`*.agent.md`) |
| Agent Skills | 73 | [`.github/skills`](../.github/skills/) (`<name>/SKILL.md`) |
| Path instructions | 11 | [`.github/instructions`](../.github/instructions/) (`*.instructions.md`) |
| Runtime contract | 1 | [copilot-instructions.md](../.github/copilot-instructions.md) |
| Shared project instructions | 1 | [AGENTS.md](../AGENTS.md) |

The original [Claude configuration](../.claude/), [Codex configuration](../.codex/),
and [Codex skills](../.agents/skills/) remain intact. Shared design standards,
engine preferences, workflow catalog, and document templates remain in
[`.claude/docs`](../.claude/docs/); the folder name does not make them executable
Claude instructions. The Copilot runtime contract adapts legacy tool references.

No game submodule is migrated or modified by this root configuration change.
The root is a studio harness. Its blank engine preferences do not describe the
existing AI Town game.

## Activate in VS Code

1. Open the repository root as the workspace and use GitHub Copilot Chat with
   an agent-capable model. Review Workspace Trust before permitting execution.
2. Reload the window after adding/updating these files. Use a fresh chat so
   stale definitions from an earlier conversation are not retained.
3. Use **Chat: Open Customizations** (or the Chat configuration menu) to inspect
   the agent, skill, and instruction lists. Check that each studio role/skill
   appears once and that its source is under `.github`.
4. Choose `producer`, `lead-programmer`, `gameplay-programmer`, or another role
   in the agent picker. Alternatively use the built-in Agent role and invoke
   `/help`, `/start`, or a named workflow.
5. For team workflows, ensure the current agent exposes the `agent`/subagent
   tool. Role names are the same as in Claude; agent filenames now end in
   `.agent.md`. The parent coordinates approval and dependent work.

If a built-in command or personal skill shadows a studio name such as `/help`,
select the studio skill from the Skills customization list or explicitly attach
its `.github/skills/<name>/SKILL.md` file. Verify the source rather than assuming
the matching name selected the intended workflow.

[Workspace settings](../.vscode/settings.json) enable skills, select `.github`
agents/skills/instructions, and disable duplicate `.claude`/`.agents` discovery
for these project locations. They also disable automatic Claude instructions
and Claude hook compatibility. They do not enable auto-approval, recursive
subagents, or change personal model choices.

These discovery settings target the VS Code Local Copilot harness. CLI, cloud,
SDK wrappers, and other agent harnesses may have different discovery, settings,
and tools. Native `.github` files are portable where supported, but do not
assume the VS Code settings configure those hosts. Personal skills or other
workspace roots may still introduce duplicates; inspect their source locations.

When working on a game, explicitly name the submodule and read that game's
instructions first. Opening only the game folder does not necessarily load
parent-repository agents. Open the studio root for this configuration; do not
copy its default engine settings into a game.

## Important adaptations

| Claude feature | Copilot treatment |
|---|---|
| `.claude/agents/<name>.md` | `.github/agents/<name>.agent.md`, native tool-set list |
| `model: haiku/sonnet/opus` | Omitted; use Copilot's selected/available model |
| `Read`, `Glob`, `Grep` | `read` and `search` tool sets |
| `Write`, `Edit`, `Bash` | `edit` and `execute`; no-shell role restrictions preserved |
| `Task`, `subagent_type` | `runSubagent`, selecting the native custom agent by name |
| `AskUserQuestion` | Parent uses `vscode/askQuestions`; chat question if unavailable |
| Worker waits for user approval | Worker returns `NEEDS_APPROVAL`; parent obtains approval and dispatches a new worker |
| Nested leadership/specialist calls | Parent dispatches handoffs when nested delegation is unavailable |
| Skill `agent` | Linked specialist guidance; no automatic agent/tool switch assumed |
| Agent `skills` preload | Explicit relative links to load on demand |
| Skill `allowed-tools` | Behavioral capability budget, not an enforced tool allowlist |
| Three shell-injected `context` headers | Explicit file/Git reads in help, changelog, sprint-plan |
| `$ARGUMENTS` | Plain interpretation of text following the skill command |
| `@file` imports | Markdown references and explicit reads |
| Rule `paths` | Native instruction `applyTo` patterns, same scope |
| Hotfix/release/launch explicit-only rule | `disable-model-invocation: true` |

### Not automatically migrated

- Claude hooks and hook payloads, permission/deny rules, and status-line scripts.
- Claude user/project agent memory and `maxTurns` enforcement.
- Automatic `isolation: worktree` and experimental Claude Agent Teams.
- Automatic context compaction, checkpoint hooks, or `/clear` semantics.

The runtime contract preserves approval, secret handling, bounded delegation,
and test expectations as instructions. Those are **not a replacement for
enforced platform permissions or executable hooks**. Do not describe the old
commit/push guard as active protection in Copilot.

## Maintaining the port

The generated 133 definitions come from the existing Claude sources using
[sync_copilot.py](../tools/sync_copilot.py). The converter is Python standard
library only, checks source metadata, and refuses unknown fields/resources
instead of silently dropping a newly added feature.

From the repository root:

```powershell
python tools\sync_copilot.py --check
python -m unittest discover -s tools -p test_sync_copilot.py -v
```

To create missing definitions:

```powershell
python tools\sync_copilot.py --write
```

To regenerate changed definitions **after reviewing local changes**:

```powershell
python tools\sync_copilot.py --write --overwrite
```

By default the writer refuses to overwrite changed existing definitions. It
never deletes stale or new custom files automatically. When adding an upstream
role or skill, update the inventory assertions and any new mapping deliberately.
Keep generated-role changes in the source and host-specific changes in the
converter. Direct Copilot edits made by `/skill-improve` or `/setup-engine` will
be detected as drift: reconcile them into the appropriate source/mapping before
regeneration. Do not blindly overwrite such user-approved edits.

[AGENTS.md](../AGENTS.md), the runtime contract, workspace settings, this guide,
and the migration tests are hand-maintained, not generated. Root workflow state
and shared engine preferences are not overwritten by synchronization.

## Verification and smoke prompts

Automated checks cover:

- Complete 49/73/11 inventory and deterministic output.
- Native metadata, valid skill identifiers and description lengths.
- Tool translation, denied terminal access, and manual-only workflows.
- Role/skill/runtime links, unchanged rule patterns, shell-context replacements.
- Preservation of unrelated code terms such as C# `Task.Delay()`.
- Safe synchronization, refusal to overwrite edits, and duplicate discovery settings.

The [Copilot configuration workflow](../.github/workflows/copilot-config.yml)
runs those checks on relevant pushes and pull requests.

Static checks do not prove model behavior or live discovery. In a fresh Copilot
chat, use these non-destructive smoke prompts:

| Prompt | Expected behavior |
|---|---|
| `/team-combat` with no arguments | Show the usage guard; do not read project files or spawn a team |
| `/help` | Load the `.github` skill, read the shared catalog/state, advise without writing files |
| Select `accessibility-specialist`: "Review our UI accessibility approach; do not edit." | Use the specialist role; return review/draft, no unapproved edits |
| "Ask lead-programmer for a read-only assessment of the Copilot configuration." | A real named delegation if available; otherwise explicitly report the limitation |
| `/start` | Ask where the user is in development, rather than treating existing games as blank projects |

The CLI shim on the migration workstation does not contain an installed Copilot
CLI. No CLI/model end-to-end run or fresh VS Code UI smoke test is claimed by
these static checks. Use the prompts above to confirm behavior in your selected
host, account, model, and organization policy.

## Official format references

Verified when porting:

- [VS Code custom agents](https://code.visualstudio.com/docs/agent-customization/custom-agents)
- [VS Code Agent Skills](https://code.visualstudio.com/docs/agent-customization/agent-skills)
- [VS Code custom instructions](https://code.visualstudio.com/docs/agent-customization/custom-instructions)
- [VS Code subagents](https://code.visualstudio.com/docs/agents/run/subagents)
- [VS Code discovery configuration](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/chat/common/promptSyntax/config/config.ts)
