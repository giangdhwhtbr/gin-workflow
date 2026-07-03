# Anthropic skill authoring — distilled best practices

This file summarizes Anthropic's published guidance on writing skills, condensed to what we found load-bearing for this plugin's authors. For the canonical, current source, consult Anthropic's documentation directly. The originals live with Anthropic; this is a paraphrased reference, not the authoritative document.

## Core principles

### Be concise

The context window is shared with everything else the agent is reasoning about: the system prompt, conversation history, other skills' metadata, the user's actual request. Once a skill is loaded, every token competes with the rest.

Default assumption: the agent is already smart. Only include context the agent doesn't already have.

For each paragraph in your skill, ask:

- Does the agent really need this explanation?
- Can I assume the agent already knows it?
- Does this paragraph justify its token cost?

Prefer concise (≈50 tokens):

```markdown
Use pdfplumber for text extraction:

with pdfplumber.open("file.pdf") as pdf:
    text = pdf.pages[0].extract_text()
```

Over verbose (≈150 tokens):

```markdown
PDF (Portable Document Format) files are a common file format that contains
text, images, and other content. To extract text, you'll need a library.
There are many libraries available, but we recommend pdfplumber because it's
easy to use and handles most cases well. First install it...
```

The concise version assumes the agent knows what PDFs are and how libraries work.

### Match specificity to the task

Choose the level of prescriptiveness to fit the task's fragility.

**High freedom — text-based instructions.** Use when several approaches are valid and context decides. Example: code review.

```markdown
1. Analyze the structure and organization.
2. Check for potential bugs or edge cases.
3. Suggest readability and maintainability improvements.
4. Verify adherence to project conventions.
```

**Medium freedom — pseudocode or parameterized scripts.** Use when there's a preferred pattern but variation is acceptable.

```markdown
def generate_report(data, format="markdown", include_charts=True):
    # process data
    # generate output in chosen format
    # optionally include charts
```

**Low freedom — exact scripts, no parameters.** Use when the operation is fragile or consistency is critical. Example: a database migration.

```bash
python scripts/migrate.py --verify --backup
```

Mental model: a robot exploring terrain. On a narrow bridge over a cliff, give exact step-by-step guardrails. In an open field, give general direction and trust the agent to find the path.

### Test with the models you'll deploy on

Skills layer on top of models, so effectiveness depends on the model. Test with each model the team will use. A skill that works perfectly for the most capable model may need more detail for a smaller one.

## Skill structure

### Frontmatter

Two required fields:

```yaml
---
name: skill-name
description: Use when [triggering conditions]
---
```

- `name` — human-readable, max 64 characters. Letters, numbers, hyphens only.
- `description` — one-line "Use when…" plus context, max 1024 characters.

### Naming conventions

Gerund form (verb-ing) works well for activity-style skills:

- `processing-pdfs`, `analyzing-spreadsheets`, `managing-databases`, `testing-code`, `writing-documentation`.

Acceptable alternatives: noun phrases (`pdf-processing`), action-oriented (`process-pdfs`).

Avoid: vague names (`helper`, `utils`, `tools`), overly generic (`documents`, `data`, `files`).

### Description writing

The description determines whether the agent loads your skill. It's the most load-bearing line.

**Always third person.** The description is injected into the system prompt; first or second person reads strangely there.

| Wrong | Right |
|-------|-------|
| "I can help you process Excel files" | "Processes Excel files and generates reports" |
| "You can use this to process Excel files" | "Processes Excel files and generates reports" |

**Include both what the skill does and when to use it.**

```yaml
# PDF processing
description: Extracts text and tables from PDFs, fills forms, merges documents.
  Use when working with PDF files or when the user mentions PDFs, forms, or
  document extraction.

# Excel analysis
description: Analyzes Excel spreadsheets, creates pivot tables, generates charts.
  Use when analyzing Excel files, spreadsheets, tabular data, or .xlsx files.

# Git commit helper
description: Generates descriptive commit messages by analyzing git diffs.
  Use when the user asks for help writing commit messages or reviewing staged
  changes.
```

Avoid vague descriptions ("Helps with documents", "Processes data", "Does stuff with files").

## Progressive disclosure

SKILL.md serves as an overview that points to detailed material as needed — like a table of contents.

- Keep SKILL.md body under 500 lines for performance.
- Split into supporting files when approaching that limit.
- Keep supporting files one level deep from SKILL.md (the agent may partially read deeply-nested files and miss content).

### Pattern 1 — Overview with references

```markdown
# PDF processing

## Quick start

Extract text with pdfplumber: <small example>

## Advanced features

- Form filling — see FORMS.md
- API reference — see REFERENCE.md
- Examples — see EXAMPLES.md
```

The agent loads the deep references only when needed.

### Pattern 2 — Domain-specific organization

For multi-domain skills, group reference material by domain so the agent reads only what's relevant:

```
bigquery-skill/
├── SKILL.md                  (overview + navigation)
└── reference/
    ├── finance.md            (revenue, billing)
    ├── sales.md              (pipeline, opportunities)
    ├── product.md            (API usage, features)
    └── marketing.md          (campaigns, attribution)
```

When the user asks about revenue, the agent reads SKILL.md, sees the reference to `reference/finance.md`, reads only that. The other domain files cost nothing.

### Pattern 3 — Conditional details

Show basic content inline; link to advanced content for the niche cases:

```markdown
# DOCX processing

## Creating documents

Use docx-js. See DOCX-JS.md for details.

## Editing documents

For simple edits, modify the XML directly.

For tracked changes, see REDLINING.md.
For OOXML internals, see OOXML.md.
```

### Structuring long reference files

Reference files over 100 lines should start with a table of contents, so the agent can see the scope even when it previews with a partial read:

```markdown
# API reference

## Contents
- Authentication and setup
- Core methods (CRUD)
- Advanced features (batch, webhooks)
- Error handling
- Code examples

## Authentication and setup
...
```

## Workflows and feedback loops

### Use a workflow for complex tasks

Break complex operations into clear, sequential steps. For multi-step processes, give a checklist the agent can copy and tick off:

```markdown
## Form-filling workflow

Copy this checklist and tick items as you complete them:

- [ ] Step 1: Analyze the form (run analyze_form.py)
- [ ] Step 2: Create field mapping (edit fields.json)
- [ ] Step 3: Validate the mapping (run validate_fields.py)
- [ ] Step 4: Fill the form (run fill_form.py)
- [ ] Step 5: Verify output (run verify_output.py)
```

Then describe each step concretely.

### Build feedback loops

Validators catch errors early:

```markdown
1. Make your edits.
2. Validate immediately: <validation command>
3. If validation fails, read the error, fix the file, re-validate.
4. Only proceed after the validator passes.
5. Run the next step.
```

The validator can be a script, a checklist against a style guide, or a manual review against a reference doc.

## Content guidelines

### Avoid time-sensitive information

Don't write content that becomes wrong over time:

```markdown
# Wrong
If you're doing this before August 2025, use the old API. After, use the new one.

# Right
## Current method
Use the v2 API endpoint: api.example.com/v2/messages

## Old patterns

<details>
<summary>Legacy v1 API (deprecated 2025-08)</summary>
The v1 API used api.example.com/v1/messages. No longer supported.
</details>
```

### Use consistent terminology

Pick one term per concept and stick with it. Mixing "API endpoint", "URL", "API route", and "path" makes the skill harder to search and harder to follow. Same for "field" vs "box" vs "element" vs "control".

## Common patterns

### Templates

For strict requirements (output formats), provide an exact template:

```markdown
ALWAYS use this exact structure:

# [Analysis title]

## Executive summary
[Overview]

## Key findings
- ...

## Recommendations
1. ...
```

For flexible guidance, provide a sensible default and tell the agent to adapt:

```markdown
A sensible default — adjust as appropriate:

# [Analysis title]
## Executive summary
[Overview]
## Key findings
[Adapt sections based on what you find]
## Recommendations
[Tailor to context]
```

### Examples

For skills where output quality depends on style, provide input/output pairs (examples-style prompting):

```markdown
**Input:** Added user authentication with JWT tokens.
**Output:**
feat(auth): implement JWT-based authentication

Add login endpoint and token validation middleware.

**Input:** Fixed bug where dates displayed incorrectly in reports.
**Output:**
fix(reports): correct date formatting in timezone conversion

Use UTC timestamps consistently across report generation.

Follow this style: type(scope): brief description, then detailed explanation.
```

## Iteration

### Build evaluations first

Before writing extensive documentation, build evaluations. They prove the skill solves a real problem.

1. Run the agent on representative tasks without the skill. Document specific failures.
2. Build three evaluation scenarios that test those gaps.
3. Establish a baseline — measure performance without the skill.
4. Write minimal instructions that address the gaps and pass the evaluations.
5. Iterate: run evaluations, compare against baseline, refine.

This is the same red → green loop as TDD.

### Develop with the agent

Pair work: have one agent help you author the skill, another agent test it on real tasks. Iterate based on what the test agent does.

1. Complete a task with the help of agent A using normal prompting. Notice what context you keep providing.
2. Ask agent A to capture that context as a skill.
3. Review agent A's draft for conciseness — strip explanations the agent already knows.
4. Have agent B (a fresh instance with the skill loaded) attempt similar tasks.
5. Note where agent B succeeds or struggles. Bring those observations back to agent A for refinement.
6. Repeat.

### Observe how agents navigate the skill

When the test agent uses the skill, watch for:

- Reading files in an unexpected order — your structure may not be as intuitive as you thought.
- Failing to follow references — links might need to be more explicit.
- Repeatedly reading the same supporting file — that content may belong in SKILL.md.
- Never accessing a bundled file — it may be unnecessary.

## Anti-patterns

### Windows-style paths

Always use forward slashes, including on Windows:

- Right: `scripts/helper.py`, `reference/guide.md`
- Wrong: `scripts\helper.py`, `reference\guide.md`

Forward slashes work on every platform; backslashes break on Unix.

### Too many options

Don't present every possible approach. Pick a default; mention alternatives only when they matter:

```markdown
# Wrong
You can use pypdf, or pdfplumber, or PyMuPDF, or pdf2image, or...

# Right
Use pdfplumber for text extraction:
  import pdfplumber

For scanned PDFs requiring OCR, use pdf2image with pytesseract.
```

## Working with executable code

### Solve, don't punt

When a skill ships scripts, handle error conditions inside the script — don't return them to the agent and hope the agent figures them out.

```python
# Right — handles missing files explicitly
def process_file(path):
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        print(f"File {path} not found, creating default")
        with open(path, 'w') as f:
            f.write('')
        return ''

# Wrong — let the agent figure it out
def process_file(path):
    return open(path).read()
```

### No magic numbers

Constants should be self-documenting. If you don't know why a timeout is 47 seconds, the agent won't know either.

```python
# Right
REQUEST_TIMEOUT = 30  # HTTP requests typically complete within 30s
MAX_RETRIES = 3       # most intermittent failures resolve by the second retry

# Wrong
TIMEOUT = 47
RETRIES = 5
```

### Make execution intent clear

For each script, state whether the agent should run it or read it as a reference:

- "Run `analyze_form.py` to extract fields" — execute.
- "See `analyze_form.py` for the extraction algorithm" — read as reference.

Most utility scripts are meant to be executed; saying so explicitly avoids the agent loading the source into context unnecessarily.

## Final checklist

Before publishing a skill:

**Core quality**

- [ ] Description is specific, third-person, and includes triggering conditions.
- [ ] SKILL.md body is under ~500 lines.
- [ ] Heavy reference content is in supporting files, one level deep.
- [ ] No time-sensitive language outside an "old patterns" section.
- [ ] Terminology is consistent throughout.
- [ ] Examples are concrete, not abstract.
- [ ] Workflows have numbered steps.

**Code and scripts (if applicable)**

- [ ] Scripts handle errors explicitly — they don't punt to the agent.
- [ ] No unjustified magic numbers.
- [ ] Required packages are listed and verified to be available.
- [ ] All paths use forward slashes.
- [ ] Validation steps are spelled out for critical operations.

**Testing**

- [ ] At least three evaluations exist.
- [ ] Tested with the models the team will use.
- [ ] Tested on real tasks, not just constructed scenarios.
- [ ] Team feedback incorporated where applicable.

## Where to read the originals

This file is a distillation. For Anthropic's current guidance — including details we deliberately omitted — consult their official skill authoring docs. The originals are the authoritative source; this file's job is to keep the essentials at fingertip distance while you're working in this plugin.
