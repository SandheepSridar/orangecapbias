---
name: save-chat
description: Save a timestamped summary of the current conversation to claudechats/. Run automatically every 20 minutes or invoke manually with /save-chat.
---

# Save Chat History

Save a concise summary of the current conversation to `claudechats/` with a timestamped filename.

## Steps

1. Run this shell command to get the current timestamp:
```
date '+%Y-%m-%d_%H%M%Z'
```

2. Write a summary of the conversation so far to:
```
claudechats/chat_history_{TIMESTAMP}.md
```

## File format

```markdown
# Chat History — {Session title derived from topic}

**Date:** {YYYY-MM-DD}
**Time:** {HH:MM TZ}
**Project:** IPL Orange Cap Bias Research

---

## Summary

{Concise bullet-point summary of what was discussed and decided this session.
Include: tasks completed, decisions made, code written, problems encountered, next steps.}

---

## Current Status

{Copy the current status checklist from CLAUDE.md, updated to reflect what was done this session.}

---

## Key Decisions Made

{Table of any decisions made this session.}
```

## Rules

- If a `chat_history_` file with today's date already exists in `claudechats/`, **update it** rather than creating a duplicate.
- Keep the summary factual and concise — focus on what was done and decided, not conversation filler.
- Always include next steps at the end.
