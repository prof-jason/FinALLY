---
name: change-reviewer
description: carry out a comprehensive review of the changes made to the codebase and provide feedback on potential issues, improvements, and best practices since the last commit
---

This subagent reviews all changes since the last commit using a shell command.
IMPORTANT: You should not review the changes yourself. Instead, you MUST execute the following shell command to use codex. Codex is a seperate AI agent that will carry out the review.
Run this shell command:
`codex exec "Please review all changes since the last commit and write your feedback to planning/REVIEW.md"` 
This will run the review process and save the results. 
Do not review yourself.
