---
description: Save a summary of this session to SESSION_LOG.md
argument-hint: "[optional notes to include]"
---

Update `SESSION_LOG.md` in the project root with a summary of this session.

1. Rewrite the **Current status** block at the top: today's date in "Last updated", then the phase, what's done, what's next and anything blocked. Keep it short; it describes the whole project, not only this session.
2. Add a new entry directly below the `---` line that follows "Current status", so the newest entry comes first. Head it `## YYYY-MM-DD · <name>`, taking the name from `git config user.name`.
3. Under that heading, write short bullets for **Done**, **Next** and **Notes** (decisions made, problems hit, anything a teammate should know). Name the actual files, features and decisions; skip filler.
4. Include these notes from the user, if any: $ARGUMENTS
5. Change no other file. When finished, show the new entry.
