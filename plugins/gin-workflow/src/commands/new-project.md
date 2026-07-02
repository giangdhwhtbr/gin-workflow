---
name: new-project
description: Scaffold a new project or file set from a user-supplied name and template.
---

# /new-project Command

Scaffold a new project or skeleton file set from a user-supplied name and optional template.

## Instructions

1. Collect the project name (and template, if given) from the command args; ask the user to clarify if either is missing or ambiguous.
2. Follow the `writing-skills` skill's style guidance for generating skeleton files — emit the minimum set of files needed to start (config, entrypoint, README stub, etc.) matching the chosen template.
3. Write the files into a new directory named after the project. Do not run build or install commands — only create files.
