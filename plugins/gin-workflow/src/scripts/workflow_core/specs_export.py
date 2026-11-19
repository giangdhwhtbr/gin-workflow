"""`gin specs export`: living specs to one self-contained SRS HTML file."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import date
from html import escape
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from . import specs, specs_matter

MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".svg": "image/svg+xml", ".webp": "image/webp"}
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
_TEMPLATE_SRC = re.compile(r'\bsrc=(["\'])(.+?)\1')
_REMOTE = ("http://", "https://")
_INLINE = re.compile(r"`([^`]+)`|!\[([^\]]*)\]\(([^)\s]+)\)|\[([^\]]+)\]\(([^)\s]+)\)"
                     r"|\*\*(.+?)\*\*|\*(.+?)\*|(?<!\w)_(.+?)_(?!\w)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


@dataclass
class Embed:
    """Turns local image paths into data: URIs and records the ones not found."""

    root: Path
    missing: list[str] = field(default_factory=list)
    shown: set[Path] = field(default_factory=set)

    def src(self, target: str, base: Path, origin: str) -> str | None:
        if target.startswith(_REMOTE):
            return target
        path = (base / target).resolve()
        if not (path.is_file() and path.is_relative_to(self.root) and path.suffix.lower() in MEDIA_TYPES):
            self.missing.append(f"{origin}: {target}")
            return None
        self.shown.add(path)
        return data_uri(path)


def data_uri(path: Path) -> str:
    media = MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return f"data:{media};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _inline(text: str, image: Callable[[str, str], str]) -> str:
    out, last = [], 0
    for found in _INLINE.finditer(text):
        out.append(escape(text[last:found.start()]))
        code, alt, target, label, href, strong, em, em2 = found.groups()
        if code is not None:
            out.append(f"<code>{escape(code)}</code>")
        elif target is not None:
            out.append(image(alt, target))
        elif href is not None:
            if href.startswith(("http://", "https://", "mailto:", "#")) or ":" not in re.split(r"[/?#]", href)[0]:
                out.append(f'<a href="{escape(href)}">{_inline(label, image)}</a>')
            else:
                out.append(_inline(label, image))
        elif strong is not None:
            out.append(f"<strong>{_inline(strong, image)}</strong>")
        else:
            out.append(f"<em>{_inline(em if em is not None else em2, image)}</em>")
        last = found.end()
    out.append(escape(text[last:]))
    return "".join(out)


def _list(items: list[tuple[int, bool, str]], inline: Callable[[str], str]) -> str:
    tag = "ol" if items[0][1] else "ul"
    out, i = [f"<{tag}>"], 0
    while i < len(items):
        indent, _, text = items[i]
        j = i + 1
        while j < len(items) and items[j][0] > indent:
            j += 1
        nested = _list(items[i + 1:j], inline) if j > i + 1 else ""
        out.append(f"<li>{inline(text)}{nested}</li>")
        i = j
    out.append(f"</{tag}>")
    return "".join(out)


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def markdown_html(text: str, base: Path, origin: str, embed: Embed, top: int = 3) -> str:
    """Convert the Markdown subset the specs use; every piece of text is escaped."""
    lines = _COMMENT.sub("", text).splitlines()
    fenced = False
    levels = []
    for line in lines:
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and _HEADING.match(line):
            levels.append(len(_HEADING.match(line).group(1)))
    shift = top - min(levels) if levels else 0

    def image(alt: str, target: str) -> str:
        src = embed.src(target, base, origin)
        if src is None:
            return f'<span class="missing-image">{escape(alt or target)}</span>'
        return f'<img src="{escape(src)}" alt="{escape(alt)}">'

    def inline(value: str) -> str:
        return _inline(value, image)

    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("```"):
            language = line[3:].strip()
            body: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            source = escape("\n".join(body))
            out.append(f'<pre class="mermaid">{source}</pre>' if language == "mermaid"
                       else f"<pre><code>{source}</code></pre>")
        elif _HEADING.match(line):
            marks, title = _HEADING.match(line).groups()
            level = min(6, max(1, len(marks) + shift))
            out.append(f"<h{level}>{inline(title)}</h{level}>")
            i += 1
        elif line.lstrip().startswith("|") and i + 1 < len(lines) and _TABLE_RULE.match(lines[i + 1]):
            head = "".join(f"<th>{inline(cell)}</th>" for cell in _cells(line))
            rows = []
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append("<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in _cells(lines[i])) + "</tr>")
                i += 1
            out.append(f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>")
        elif _LIST_ITEM.match(line):
            items = []
            while i < len(lines) and _LIST_ITEM.match(lines[i]):
                indent, marker, value = _LIST_ITEM.match(lines[i]).groups()
                items.append((len(indent), marker[0].isdigit(), value))
                i += 1
            out.append(_list(items, inline))
        else:
            paragraph = [line.strip()]
            i += 1
            while i < len(lines) and lines[i].strip() and not (
                    lines[i].startswith("```") or _HEADING.match(lines[i]) or _LIST_ITEM.match(lines[i])
                    or lines[i].lstrip().startswith("|")):
                paragraph.append(lines[i].strip())
                i += 1
            out.append(f"<p>{inline(chr(10).join(paragraph))}</p>")
    return "\n".join(out)


def _title(text: str, fallback: str) -> str:
    found = re.search(r"^# (.+)$", text, re.MULTILINE)
    return found.group(1).strip() if found else fallback


def _section(text: str, heading: str) -> str:
    found = re.search(rf"^## {re.escape(heading)}[ \t]*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return found.group(1).strip() if found else ""


def _shown(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _files(title: str | None, description: Path | None, files: list[Path], folder: Path, root: Path,
           embed: Embed) -> str:
    out = []
    embed.shown = set()
    if description is not None:
        out.append(markdown_html(description.read_text(encoding="utf-8"), description.parent,
                                 _shown(description, root), embed))
    if title is not None:
        out.append(f"<h3>{escape(title)}</h3>")
    others = []
    for path in files:
        if path == description or path.resolve() in embed.shown:
            continue
        name = escape(path.relative_to(folder).as_posix())
        if path.suffix.lower() in MEDIA_TYPES and path.resolve().is_relative_to(root):
            out.append(f'<figure><img src="{data_uri(path)}" alt="{name}"><figcaption>{name}</figcaption></figure>')
        else:
            others.append(f"<li><code>{name}</code></li>")
    if others:
        out.append(f'<ul class="asset-files">{"".join(others)}</ul>')
    return "\n".join(out)


def _assets(folder: Path, root: Path, embed: Embed) -> str:
    if not folder.is_dir():
        return ""
    groups = []
    for dated in sorted(p for p in folder.iterdir() if p.is_dir() and specs._ISO_DATE.match(p.name)):
        description = dated / "description.md"
        found = description if description.is_file() else None
        files = sorted(p for p in dated.rglob("*") if p.is_file())
        groups.append(_files(None if found else dated.name, found, files, dated, root, embed))
    flat = sorted(p for p in folder.iterdir() if p.is_file())
    if flat:
        groups.append(_files("Files", None, flat, folder, root, embed))
    return "\n".join(f'<section class="asset-group">{group}</section>' for group in groups)


def _quoted(text: str) -> str:
    return '"' + text.replace('"', "#quot;") + '"'


def use_case_diagram(capability: str, folder: Path) -> str:
    """Mermaid flowchart of a capability's use cases: actors outside the system box, include and extend edges.

    Actor names match without regard to case or repeated spaces; the first spelling met labels the node."""
    texts = {path.stem: path.read_text(encoding="utf-8") for path in sorted((folder / "use-cases").glob("*.md"))}
    if not texts:
        return ""
    ids = {slug: f"uc{number}" for number, slug in enumerate(texts, 1)}
    actors: dict[str, tuple[str, str]] = {}

    def actor(name: str) -> str:
        label = " ".join(name.split())
        return actors.setdefault(specs.actor_key(name), (f"a{len(actors) + 1}", label))[0]

    nodes: list[str] = []
    edges: list[str] = []
    for slug, text in texts.items():
        heading = re.search(r"^# (\S.*)$", specs._COMMENT.sub("", text), re.MULTILINE)
        nodes.append(f"    {ids[slug]}([{_quoted(heading.group(1).strip() if heading else slug)}])")
        primary = specs.line_value(text, "Actor")
        if primary:
            edges.append(f"  {actor(primary)} --> {ids[slug]}")
        edges += [f"  {ids[slug]} --> {actor(name)}" for name in specs.line_values(text, "Secondary actors")]
        for key, label in (("Includes", "«include»"), ("Extends", "«extend»")):
            edges += [f"  {ids[slug]} -. {label} .-> {ids[other]}"
                      for other in specs.line_values(text, key) if other in ids and other != slug]
    lines = ["flowchart LR", "  classDef actor fill:none,stroke-width:3px",
             *(f"  {node}[{_quoted(label)}]" for node, label in actors.values()),
             f"  subgraph system[{_quoted(capability)}]", *nodes, "  end", *edges]
    if actors:
        lines.append(f"  class {','.join(node for node, _ in actors.values())} actor")
    return "\n".join(lines)


def _chapter(cap: str, spec: Path, root: Path, embed: Embed, template: str) -> tuple[str, str]:
    text = spec.read_text(encoding="utf-8")
    folder = spec.parent
    title = _title(text, cap)
    purpose = markdown_html(_section(text, "Purpose"), folder, _shown(spec, root), embed)
    use_cases = "\n".join(
        f'<section class="use-case" id="{escape(cap)}-{escape(path.stem)}">{_use_case(cap, path, root, embed)}</section>'
        for path in sorted((folder / "use-cases").glob("*.md")))
    diagram = use_case_diagram(title, folder)
    if diagram:
        use_cases = (f'<section class="use-case-diagram" id="{escape(cap)}-use-case-diagram">'
                     f'<pre class="mermaid">{escape(diagram)}</pre></section>\n' + use_cases)
    diagrams = "\n".join(
        f'<section class="diagram" id="{escape(cap)}-{escape(path.stem)}">'
        f'{markdown_html(path.read_text(encoding="utf-8"), path.parent, _shown(path, root), embed)}</section>'
        for path in sorted((folder / "diagrams").glob("*.md")))
    blocks = specs.parse_blocks(text)[0]
    requirements = _requirements(blocks, folder, _shown(spec, root), embed)
    chapter = fill(template, {"cap": escape(cap), "capability": escape(title), "purpose": purpose,
                              "use_cases": use_cases,
                              "diagrams": diagrams, "requirements": requirements,
                              "assets": _assets(folder / "assets", root, embed)})
    links = "".join(f'<li><a href="#{escape(b.id)}">{escape(b.id)}: {escape(b.title)}</a></li>' for b in blocks)
    toc = f'<li><a href="#{escape(cap)}">{escape(title)}</a>' + (f"<ul>{links}</ul>" if links else "") + "</li>"
    return chapter, toc


_REQUIREMENT_FIELD = re.compile(r"^(Type|Category|Measure):[ \t]*(.*)$")
_FIELD = re.compile(r"^(Actor|Secondary actors|Trigger|Requirements|Includes|Extends):[ \t]*(.*)$")
_FIRST_SECTION = re.compile(r"^#{2,6} ", re.MULTILINE)


def _header_fields(text: str, pattern: re.Pattern[str], css: str) -> tuple[str, str]:
    """The header lines matching `pattern` before the first section heading, as a two-column table of class `css`,
    and the text without them. A line with no value is dropped; an image in a value shows its alt text.
    The first line is a title, so a `### REQ-` heading there does not end the head."""
    text = _COMMENT.sub("", text)
    found = _FIRST_SECTION.search(text, text.find("\n") + 1 if "\n" in text else 0)
    head, rest = (text[:found.start()], text[found.start():]) if found else (text, "")
    kept, rows = [], []
    for line in head.split("\n"):
        field = pattern.match(line)
        if field and not field.group(2).strip():
            continue
        if field:
            value = _inline(field.group(2), lambda alt, target: escape(alt or target))
            rows.append(f"<tr><th>{escape(field.group(1))}</th><td>{value}</td></tr>")
        else:
            kept.append(line)
    table = f'<table class="{css}">{"".join(rows)}</table>' if rows else ""
    return table, "\n".join(kept) + rest


def _requirement(block: specs.Block, folder: Path, origin: str, embed: Embed) -> str:
    fields, text = _header_fields(block.text, _REQUIREMENT_FIELD, "requirement-fields")
    html = markdown_html(text, folder, origin, embed)
    if fields:
        html = re.sub(r"(</h[1-6]>)", lambda found: found.group(1) + fields, html, count=1)
    return f'<section class="requirement" id="{escape(block.id)}">{html}</section>'


def _requirements(blocks: list[specs.Block], folder: Path, origin: str, embed: Embed) -> str:
    """Requirements in file order; with any non-functional or business rule, grouped under type headings."""
    def render(group: list[specs.Block]) -> str:
        return "\n".join(_requirement(block, folder, origin, embed) for block in group)

    kinds = {kind: [b for b in blocks if specs.type_of(b) == kind] for kind in specs.REQ_TYPES}
    if len(kinds["functional"]) == len(blocks):
        return render(blocks)
    out = []
    if kinds["functional"]:
        out.append("<h3>Functional requirements</h3>\n" + render(kinds["functional"]))
    if kinds["non-functional"]:
        out.append("<h3>Non-functional requirements</h3>")
        for category in (*specs.NFR_CATEGORIES, None):
            members = [b for b in kinds["non-functional"]
                       if (b.category == category if category else b.category not in specs.NFR_CATEGORIES)]
            if members:
                out.append(f"<h4>{escape(category or 'other')}</h4>\n" + render(members))
    if kinds["business-rule"]:
        out.append("<h3>Business rules</h3>\n" + render(kinds["business-rule"]))
    return "\n".join(out)


def _use_case(cap: str, path: Path, root: Path, embed: Embed) -> str:
    fields, text = _header_fields(path.read_text(encoding="utf-8"), _FIELD, "use-case-fields")
    return _with_id(markdown_html(text, path.parent, _shown(path, root), embed), cap, path.stem, fields)


def _with_id(html: str, cap: str, slug: str, fields: str = "") -> str:
    """The use case ID `<capability>/<slug>`, then its fields table, under the first heading, or first without one."""
    id_html = f'<p class="use-case-id">{escape(cap)}/{escape(slug)}</p>{fields}'
    if "</h" not in html:
        return id_html + html
    return re.sub(r"(</h[1-6]>)", lambda found: found.group(1) + id_html, html, count=1)


def _table(headers: list[str], rows: list[list[str]], empty: str) -> str:
    """Cells are HTML already escaped by the caller."""
    if not rows:
        return f'<p class="none">{escape(empty)}</p>'
    head = "".join(f"<th>{escape(name)}</th>" for name in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _use_case_link(ref: str, caps: list[str]) -> str:
    owner, slug = ref.split("/", 1)
    return f'<a href="#{escape(owner)}-{escape(slug)}">{escape(ref)}</a>' if owner in caps else escape(ref)


def _joined(items: list[str]) -> str:
    return ", ".join(escape(item) for item in items)


def _matter(root: Path, cfg: Mapping[str, Any], cap: str | None, caps: list[str]) -> dict[str, str]:
    """The HTML of the document-level sections for `export`."""
    revisions = [[escape(r["date"]), escape(r["epic"]), escape(r["title"]), _joined(r["capabilities"]),
                  _joined(r["added"]), _joined(r["modified"]), _joined(r["removed"])]
                 for r in specs_matter.revisions(root, cfg, cap)]
    glossary = [[escape(g["english"]), escape(f"{g['term']} ({g['lang']})" if g["lang"] else g["term"]),
                 escape(g["meaning"])] for g in specs_matter.glossary(root, cfg)]
    actors = [[escape(a["actor"]), escape(a["description"]),
               ", ".join(_use_case_link(u["ref"], caps) + (" (secondary)" if u["secondary"] else "")
                         for u in a["use_cases"])] for a in specs_matter.actors(root, cfg, cap)]
    trace = [[f'<a href="#{escape(t["id"])}">{escape(t["id"])}</a>: {escape(t["title"])}', escape(t["capability"]),
              escape(t["type"]), ", ".join(_use_case_link(ref, caps) for ref in t["use_cases"]),
              "<br>".join(f"<code>{escape(path)}</code>" for path in t["tests"]), _joined(t["qa_cases"]),
              escape(t["status"])] for t in specs_matter.traceability(root, cfg, cap)]
    nfr = [[escape(n["category"]), f'<a href="#{escape(n["id"])}">{escape(n["id"])}</a>: {escape(n["title"])}',
            escape(n["capability"]), escape(n["measure"])] for n in specs_matter.nonfunctional(root, cfg, cap)]
    rules = [[f'<a href="#{escape(r["id"])}">{escape(r["id"])}</a>: {escape(r["title"])}', escape(r["capability"]),
              escape(r["statement"]), ", ".join(_use_case_link(ref, caps) for ref in r["use_cases"])]
             for r in specs_matter.business_rules(root, cfg, cap)]
    return {
        "revisions": _table(["Date", "Epic", "Title", "Capabilities", "Added", "Modified", "Removed"],
                            revisions, "No revisions yet."),
        "glossary": _table(["English", "Term", "Meaning"], glossary, "No glossary."),
        "actors": _table(["Actor", "Description", "Use cases"], actors, "No actors."),
        "nfr": _table(["Category", "Requirement", "Capability", "Measure"], nfr, "No non-functional requirements."),
        "business_rules": _table(["Rule", "Capability", "Statement", "Use cases"], rules, "No business rules."),
        "traceability": _table(["Requirement", "Capability", "Type", "Use cases", "Tests", "QA cases", "Status"],
                               trace, "No requirements."),
    }


def fill(template: str, values: Mapping[str, str]) -> str:
    """One pass: text inside a value is never substituted again."""
    return _PLACEHOLDER.sub(lambda found: values.get(found.group(1), found.group(0)), template)


def _template(root: Path, name: str, embed: Embed) -> str:
    def local(found: re.Match[str]) -> str:
        target = found.group(2)
        if target.startswith((*_REMOTE, "data:", "#")) or "{{" in target:
            return found.group(0)
        src = embed.src(target, root, name)
        return f'src="{escape(src)}"' if src else found.group(0)

    return _TEMPLATE_SRC.sub(local, _COMMENT.sub("", specs.template_text(root, name)))


def export(root: Path, cfg: Mapping[str, Any], cap: str | None, out: str | None,
           today: date | None = None) -> dict[str, Any]:
    living = specs.living_files(root, cfg)
    if cap is None:
        caps = sorted(living)
        if not caps:
            raise specs.SpecsError(f"no capability with a spec.md under {cfg['specs']}")
    elif cap in living:
        caps = [cap]
    else:
        raise specs.SpecsError(f"unknown capability: {cap} (no {cfg['specs']}/{cap}/spec.md)")
    path = (root / (out or (f"srs-{cap}.html" if cap else "srs.html"))).resolve()
    if not path.is_relative_to(root):
        raise specs.SpecsError(f"--out must stay inside the repository: {out}")
    embed = Embed(root)
    chapter_template = _template(root, "srs-capability.html", embed)
    document = _template(root, "srs.html", embed)
    chapters, toc = [], []
    for name in caps:
        chapter, entry = _chapter(name, living[name], root, embed, chapter_template)
        chapters.append(chapter)
        toc.append(entry)
    title = _title(living[cap].read_text(encoding="utf-8"), cap) if cap else root.name
    front = [(anchor, label) for anchor, label in (("revisions", "Revision history"), ("signoff", "Sign-off"),
                                                   ("glossary", "Glossary"), ("actors", "Actors"),
                                                   ("nfr", "Non-functional requirements"),
                                                   ("business-rules", "Business rules"))
             if f'id="{anchor}"' in document]
    back = [("traceability", "Traceability matrix")] if 'id="traceability"' in document else []
    entries = ([f'<li><a href="#{anchor}">{label}</a></li>' for anchor, label in front] + toc
               + [f'<li><a href="#{anchor}">{label}</a></li>' for anchor, label in back])
    html = fill(document, {"title": escape(title), "date": (today or date.today()).isoformat(),
                           "toc": f'<ul>{"".join(entries)}</ul>', "chapters": "\n".join(chapters),
                           **_matter(root, cfg, cap, caps)})
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    except OSError as error:
        raise specs.SpecsError(f"cannot write {out or path}: {error}") from error
    return {"path": _shown(path, root), "capabilities": caps, "missing": embed.missing}
