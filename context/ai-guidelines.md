# AI Interaction Guidelines

## Communication
- Be concise and direct
- Explain non-obvious decisions briefly
- Ask before large refactors or architectural changes
- Don't add features not in the project spec
- Never delete files without clarification

## Workflow
This is the common workflow for every single feature/fix:

1. **Document** — Document the feature in `@context/current-feature.md`
2. **Branch** — Create a new branch for the feature/fix
3. **Implement** — Implement what is described in `@context/current-feature.md`
4. **Test** — Verify it works. For backend: run `pytest`. For question generation scripts: run manually and inspect output. Fix any errors before proceeding.
5. **Iterate** — Iterate and change things if needed
6. **Commit** — Only after tests pass and everything works
7. **Merge** — Merge to main
8. **Delete Branch** — Delete branch after merge
9. **Review** — Review AI-generated code periodically and on demand
10. **Complete** — Mark as completed in `@context/current-feature.md` and add to history

Do NOT commit without permission and until tests pass. If tests fail, fix issues first.

## Branching
Create a new branch for every feature/fix.
- `feature/[feature-name]`
- `fix/[fix-name]`
- `chore/[task-name]`

Ask to delete the branch once merged.

## Commits
- Ask before committing (don't auto-commit)
- Use conventional commit messages: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`
- Keep commits focused — one feature/fix per commit
- Never put "Generated With Claude" in commit messages

## When Stuck
- If something isn't working after 2-3 attempts, stop and explain the issue
- Don't keep trying random fixes
- Ask for clarification if requirements are unclear

## Code Changes
- Make minimal changes to accomplish the task
- Don't refactor unrelated code unless asked
- Don't add "nice to have" features
- Preserve existing patterns in the codebase

## Code Review
Review AI-generated code periodically, especially for:
- **Security** — input validation, API key handling, no secrets in code
- **Performance** — unnecessary DB calls, inefficient loops
- **Logic errors** — edge cases in scoring, question selection, model predictions
- **Patterns** — matches existing codebase structure?
