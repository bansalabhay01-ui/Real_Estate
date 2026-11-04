---
description: Save this session: update SESSION_LOG.md, then commit and push to GitHub
argument-hint: "[optional notes to include]"
---

Save the current session. Claude also does this without being asked: whenever a piece of work is finished, and at the start of a new session if the last one wasn't saved (see "Sessions" in `CLAUDE.md`).

1. Update `SESSION_LOG.md` in the project root:
   - Rewrite the **Current status** block at the top: today's date in "Last updated", then the phase, what's done, what's next and anything blocked. Keep it short; it describes the whole project, not only this session.
   - If this session already has an entry (written earlier in this same session), update it. Otherwise add a new entry directly below the `---` line that follows "Current status", so the newest entry comes first. Head it `## YYYY-MM-DD · <name> · <short title of the work>`, taking the name from `git config user.name`.
   - Under the heading, write short bullets for **Done**, **Next** and **Notes** (decisions made, problems hit, anything a teammate should know). Name the actual files, features and decisions; skip filler.
   - When saving a previous session at the start of a new one, work out what it did from `git status`, `git diff` and the newest entries in `PROMPTS.md`.
   - Include these notes from the user, if any: $ARGUMENTS
2. Commit: run `git add -A`, then check the staged files. If they include `.env` files, keys, databases, `node_modules` or `.venv`, stop and tell the user instead of committing. Otherwise commit with a message that says what the session did: a short first line, then a few lines of detail.
3. Push: `git pull --rebase origin main`, then `git push origin main`. If `SESSION_LOG.md` or `PROMPTS.md` conflict, keep both sides. If GitHub asks for a sign-in, ask the user to run `! git push origin main` and finish the sign-in.
4. Tell the user in one or two lines what was saved and pushed.
