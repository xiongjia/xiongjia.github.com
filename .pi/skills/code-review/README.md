# code-review

AI agent skill for performing strict code review on diffs.

## Purpose

When invoked, this skill instructs the AI agent to act as a senior staff engineer and perform a thorough code review of all uncommitted/unpushed changes. It focuses on correctness, security, performance, readability, and consistency — with special attention to naming issues.

## Files

| File        | Purpose                                                                                        |
| ----------- | ---------------------------------------------------------------------------------------------- |
| `skill.md`  | Skill content installed to agent (Claude Code / Pi Agent). This is the prompt the agent reads. |
| `README.md` | This file — developer documentation for the skill itself.                                      |

## Usage

```bash
# Install globally for Claude Code
npx tsx shared/install.ts --skill code-review --target claude-code --scope global

# Install globally for Pi Agent
npx tsx shared/install.ts --skill code-review --target pi-agent --scope global

# Uninstall
npx tsx shared/uninstall.ts --skill code-review --target claude-code --scope global
```

## How It Works

The skill instructs the agent to:

1. Run `git status` to show the overall state
2. Run `git diff HEAD` to discover ALL uncommitted changes (staged + unstaged)
3. Run `git log origin/main..HEAD` for unpushed commits
4. Review against a defined set of principles
5. Report issues in a structured format with severity labels

## Notes for Developers

- This skill serves as a **template** for creating new skills — its `skill.md` demonstrates the required frontmatter format and the expected structure.
- When creating a new skill, copy this directory structure and adapt the content.
- The `compatibility` field in frontmatter lists which agents support this skill.
- The `tools` field lists the agent tools the skill requires.

## Registry

Registered in `skills/registry.json` as:

```json
{
  "name": "code-review",
  "description": "Review code changes for bugs, security, and quality — also serves as a skill template",
  "version": "0.1.0",
  "targets": ["claude-code", "pi-agent"],
  "path": "skills/code-review/skill.md"
}
```
