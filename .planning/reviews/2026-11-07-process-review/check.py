"""Structural checks for the process review. Run from the repository root."""
import pathlib, re, subprocess, sys

D = pathlib.Path(".planning/reviews/2026-11-07-process-review")
ROLES = ["pm", "ba", "qa", "be-lead", "fe-lead"]
STAGES = 14
PROMPT_SECTIONS = ["## Identity and concerns", "## Task", "## Mandatory reading", "## Evidence rules", "## Output"]
REPORT_SECTIONS = ["## Walkthrough", "## Findings", "## Top 3 changes", "## Questions for other roles"]
CORE = ["docs/starters/brownfield.md", "docs/concepts/lifecycle.md", "docs/roles.md", "docs/guides/team.md",
        "docs/guides/workspace.md", "docs/guides/git-flow.md", "docs/reference/skills.md"]
ID = r"(?:PM|BA|QA|BE-LEAD|FE-LEAD)-\d+"
problems = []

def headings(text):
    return [line for line in text.splitlines() if line.startswith("## ")]

def kit():
    for name in ["README.md", "brief.md", "report-template.md"]:
        if not (D / name).is_file():
            problems.append(f"missing {name}")
    for role in ROLES:
        text = (D / "prompts" / f"{role}.md").read_text()
        if headings(text) != PROMPT_SECTIONS:
            problems.append(f"prompts/{role}.md sections {headings(text)}")
        for path in CORE:
            if path not in text:
                problems.append(f"prompts/{role}.md lacks {path}")

def tracked():
    return set(subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.split())

def findings(role):
    text = (D / "reports" / f"{role}.md").read_text()
    section = text.split("\n## Findings", 1)[1].split("\n## ", 1)[0]
    return re.findall(rf"^\|\s*({ID})\s*\|(.*)$", section, re.M)

def reports():
    files = tracked()
    for role in ROLES:
        path = D / "reports" / f"{role}.md"
        if not path.is_file():
            problems.append(f"missing reports/{role}.md")
            continue
        text = path.read_text()
        if [h for h in headings(text) if h in REPORT_SECTIONS] != REPORT_SECTIONS:
            problems.append(f"reports/{role}.md sections {headings(text)}")
            continue
        walk = text.split("\n## Walkthrough", 1)[1].split("\n## ", 1)[0]
        if len(re.findall(r"^### \d+\. ", walk, re.M)) != STAGES:
            problems.append(f"reports/{role}.md does not have {STAGES} stage sub-sections")
        rows = findings(role)
        if not rows:
            problems.append(f"reports/{role}.md has no findings rows")
        for fid, rest in rows:
            for ev in re.findall(r"`([^`\s]+?):\d+(?:-\d+)?`", rest):
                if ev not in files:
                    print(f"note: {fid} evidence not tracked: {ev}")

def synthesis():
    text = (D / "synthesis.md").read_text()
    for h in ["## Clusters", "## Conflicts", "## Dropped", "## Carry into /gin:roadmap"]:
        if h not in text:
            problems.append(f"synthesis.md lacks {h}")
    def part(h):
        return text.split(h, 1)[1].split("\n## ", 1)[0] if h in text else ""
    accounted = part("## Clusters") + part("## Dropped")
    files = tracked()
    for role in ROLES:
        for fid, rest in findings(role):
            count = len(re.findall(rf"(?<![\w-]){re.escape(fid)}(?![\w-])", accounted))
            if count != 1:
                problems.append(f"{fid} appears {count} times in Clusters and Dropped")
            missing = [e for e in re.findall(r"`([^`\s]+?):\d+(?:-\d+)?`", rest) if e not in files]
            if missing and not re.search(rf"(?<![\w-]){re.escape(fid)}(?![\w-]).*no evidence", part("## Dropped")):
                problems.append(f"{fid} cites untracked {missing} but is not dropped with 'no evidence'")

{"kit": kit, "reports": reports, "synthesis": synthesis}[sys.argv[1]]()
print("\n".join(problems) or "ok")
sys.exit(1 if problems else 0)
