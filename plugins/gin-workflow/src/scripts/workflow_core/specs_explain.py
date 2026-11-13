"""`gin specs explain`: one interactive HTML page for a capability or an active change."""

from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path
import re
from typing import Any, Mapping

from . import specs
from .specs_export import MEDIA_TYPES, Embed, _section, _template, _title, data_uri, fill, markdown_html

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_STORY = re.compile(r"^### US-\d+:")
_REQ_LINE = re.compile(r"^REQ:(.*)$", re.MULTILINE)
_SOURCE_LINE = re.compile(r"^Source:(.*)$", re.MULTILINE)
_CITED_DATE = re.compile(r"`assets/(\d{4}-\d{2}-\d{2})/")
_CODE_PATH = re.compile(r"<code>(assets/\d{4}-\d{2}-\d{2}/[A-Za-z0-9._/-]+?)(?:#([a-z][a-z0-9-]*))?</code>")
_SCREEN = re.compile(r"""<section\b[^>]*?\bid=["']([a-z][a-z0-9-]*)["']""")
_LISTENER = ("<script>addEventListener('message',function(e){var s=e.data;"
             "if(typeof s==='string'&&/^[a-z][a-z0-9-]*$/.test(s)){location.hash=s;}});"
             # A srcdoc document's base URL is the parent page: keep its own `#id` links inside the frame.
             "document.addEventListener('click',function(e){"
             "var a=e.target.closest&&e.target.closest('a[href^=\"#\"]');"
             "if(a&&!e.defaultPrevented){e.preventDefault();location.hash=a.getAttribute('href').slice(1);}});</script>")
TABS = (("overview", "Overview"), ("requirements", "Requirements"), ("stories", "Stories"),
        ("diagrams", "Diagrams"), ("mockups", "Mockups and images"))


def _anchor(cap: str, relative: str) -> str:
    """Element id of a dated folder or one of its files, e.g. `asset-auth-assets-2026-05-11-mockup-index-html`."""
    # simplified: two names that differ only in case or punctuation (`Login.png`/`login.png`, `a b.png`/`a-b.png`)
    # share one id, so a link reaches the first; upgrade with a per-folder counter suffix if that matters.
    return "asset-" + re.sub(r"[^a-z0-9]+", "-", f"{cap}-{relative}".lower()).strip("-")


def _titled(heading: str, html: str) -> str:
    return f"<h3>{escape(heading)}</h3>\n{html}" if html else ""


def _resolve(root: Path, cfg: Mapping[str, Any], name: str) -> tuple[str, Path]:
    if not _NAME.match(name):
        raise specs.SpecsError(f"not a capability or change name: {name!r}")
    living = specs.living_files(root, cfg)
    if name in living:
        return "capability", living[name]
    try:
        return "change", specs.find_change(root, cfg, name)
    except specs.SpecsError as error:
        if "ambiguous" in str(error):
            raise
        raise specs.SpecsError(f"unknown capability or change: {name} (no {cfg['specs']}/{name}/spec.md "
                               f"and no change under {cfg['changes']})") from error


def _narrative(root: Path, narrative: str | None, embed: Embed) -> str:
    if narrative is None:
        return ""
    path = (root / narrative).resolve()
    if not (path.is_relative_to(root) and path.is_file()):
        raise specs.SpecsError(f"--narrative must be a file inside the repository: {narrative}")
    return markdown_html(path.read_text(encoding="utf-8"), path.parent, specs.shown(root, path), embed)


def _link_sources(html: str, cap: str) -> str:
    def link(found: re.Match[str]) -> str:
        screen = f' data-screen="{found.group(2)}"' if found.group(2) else ""
        return f'<a href="#{_anchor(cap, found.group(1))}"{screen}>{found.group(0)}</a>'

    return _CODE_PATH.sub(link, html)


def _cards(blocks: list[specs.Block], groups: list[str] | tuple[str, ...], base: Path, origin: str,
           embed: Embed) -> str:
    out = []
    for group in groups:
        cards = [f'<article class="card" id="{escape(block.id)}">'
                 f'{_link_sources(markdown_html(block.text, base, origin, embed, top=4), block.cap)}</article>'
                 for block in blocks if block.section == group]
        if cards:
            out.append(f'<section class="req-group"><h3>{escape(group)}</h3>\n' + "\n".join(cards) + "</section>")
    if not out:
        return ""
    return ('<input type="search" id="req-search" placeholder="Filter by text or REQ-ID" '
            'aria-label="Filter requirements">\n' + "\n".join(out))


def _stories(root: Path, change: Path, ids: set[str] | None, embed: Embed) -> list[str]:
    """Each `### US-<n>` block under `## User Stories`; with `ids`, only those naming one of them, labelled."""
    path = specs.change_file(change, "proposal")
    if not path.is_file():
        return []
    out = []
    for part in re.split(r"(?m)^(?=### )", _section(path.read_text(encoding="utf-8"), "User Stories")):
        if not _STORY.match(part):
            continue
        reqs = [found.group(0) for line in _REQ_LINE.findall(part) for found in specs.REQ_ID.finditer(line)]
        if ids is not None and not ids.intersection(reqs):
            continue
        label = f'<p class="from">{escape(change.name)}</p>' if ids is not None else ""
        links = " ".join(f'<a href="#{escape(req)}">{escape(req)}</a>' for req in reqs)
        body = markdown_html(part, change, specs.shown(root, path), embed)
        out.append(f'<article class="story">{label}{body}' + (f'<p class="reqs">{links}</p>' if links else "")
                   + "</article>")
    return out


def _changes(root: Path, cfg: Mapping[str, Any]) -> list[Path]:
    """Archived change folders, then active ones, each sorted by name."""
    base = specs.changes_dir(root, cfg)
    if not base.is_dir():
        return []
    archive = base / "archive"
    archived = sorted(p for p in archive.iterdir() if p.is_dir()) if archive.is_dir() else []
    return archived + sorted(p for p in base.iterdir() if p.is_dir() and p.name != "archive")


def _doc(path: Path, root: Path, embed: Embed) -> str:
    html = markdown_html(path.read_text(encoding="utf-8"), path.parent, specs.shown(root, path), embed)
    return f'<section class="diagram">{html}</section>'


def _diagrams(folder: Path, root: Path, embed: Embed) -> str:
    return "\n".join(_doc(path, root, embed) for path in sorted(folder.glob("*.md")))


def _dated(assets: Path) -> list[Path]:
    if not assets.is_dir():
        return []
    return sorted(p for p in assets.iterdir() if p.is_dir() and specs._ISO_DATE.match(p.name))


def _mockup(path: Path, anchor: str, name: str, root: Path, assets: Path, embed: Embed) -> str:
    real = path.resolve()
    home = assets.resolve()
    inside = (real.is_file() and real.suffix.lower() == ".html" and real.is_relative_to(root)
              and real.is_relative_to(home) and specs._ISO_DATE.match(real.relative_to(home).parts[0]))
    if not inside:
        embed.missing.append(f"{specs.shown(root, path)}: mockup not embedded")
        return f'<p class="missing-image" id="{anchor}">{name}</p>'
    source = real.read_text(encoding="utf-8")
    end = source.lower().rfind("</body>")
    document = source[:end] + _LISTENER + source[end:] if end >= 0 else source + _LISTENER
    options = "".join(f'<option value="{screen}">{screen}</option>'
                      for screen in dict.fromkeys(_SCREEN.findall(source)))
    picker = (f'<select class="screens" data-frame="{anchor}" aria-label="Screen">{options}</select>'
              if options else "")
    return (f'<figure class="mockup" id="{anchor}"><figcaption>{name}</figcaption>{picker}'
            f'<iframe sandbox="allow-scripts" srcdoc="{escape(document)}" title="{name}"></iframe></figure>')


def _folder(cap: str, folder: Path, root: Path, embed: Embed) -> str:
    """One dated folder: `description.md`, then images, mockups, and the other file names."""
    relative = f"assets/{folder.name}"
    out = [f'<section class="asset-group" id="{_anchor(cap, relative)}"><h3>{escape(cap)}: {folder.name}</h3>']
    description = folder / "description.md"
    embed.shown = set()
    if description.is_file():
        html = markdown_html(description.read_text(encoding="utf-8"), folder, specs.shown(root, description),
                             embed, top=4)
        out.append(f'<div id="{_anchor(cap, relative + "/description.md")}">{html}</div>')
    others = []
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        if path == description or path.resolve() in embed.shown:
            continue
        inner = path.relative_to(folder).as_posix()
        anchor, name = _anchor(cap, f"{relative}/{inner}"), escape(inner)
        if path.name == "index.html" and path.parent.name == "mockup":
            out.append(_mockup(path, anchor, name, root, folder.parent, embed))
        elif path.suffix.lower() in MEDIA_TYPES and path.resolve().is_relative_to(root):
            out.append(f'<figure id="{anchor}"><img src="{data_uri(path)}" alt="{name}">'
                       f'<figcaption>{name}</figcaption></figure>')
        else:
            others.append(f'<li id="{anchor}"><code>{name}</code></li>')
    if others:
        out.append(f'<ul class="asset-files">{"".join(others)}</ul>')
    out.append("</section>")
    return "\n".join(out)


def _capability(root: Path, cfg: Mapping[str, Any], cap: str, spec: Path,
                embed: Embed) -> tuple[str, dict[str, str]]:
    text = spec.read_text(encoding="utf-8")
    folder, origin = spec.parent, specs.shown(root, spec)
    blocks = specs.parse_blocks(text)[0]
    ids = {block.id for block in blocks}
    return _title(text, cap), {
        "overview": _titled("Purpose", markdown_html(_section(text, "Purpose"), folder, origin, embed, top=4)),
        "requirements": _cards(blocks, list(dict.fromkeys(b.section for b in blocks)), folder, origin, embed),
        "stories": "\n".join(story for change in _changes(root, cfg) for story in _stories(root, change, ids, embed)),
        "diagrams": _diagrams(folder / "diagrams", root, embed),
        "mockups": "\n".join(_folder(cap, dated, root, embed) for dated in _dated(folder / "assets")),
    }


def _change(root: Path, cfg: Mapping[str, Any], change: Path, embed: Embed) -> tuple[str, dict[str, str]]:
    path = specs.change_file(change, "proposal")
    proposal = path.read_text(encoding="utf-8") if path.is_file() else ""
    origin = specs.shown(root, path)
    blocks = specs.delta_blocks(root, change)[0]
    caps = sorted({block.cap for block in blocks})
    base = specs.specs_dir(root, cfg)
    cited = sorted({(day, block.cap) for block in blocks for line in _SOURCE_LINE.findall(block.text)
                    for day in _CITED_DATE.findall(line)})
    design = specs.change_file(change, "design")
    diagrams = [_doc(design, root, embed)] if design.is_file() else []
    diagrams += [_diagrams(base / cap / "diagrams", root, embed) for cap in caps]
    delta_origin = specs.shown(root, specs.change_file(change, "spec-delta"))
    return _title(proposal, change.name), {
        "overview": "\n".join(_titled(heading, markdown_html(_section(proposal, heading), change, origin, embed, top=4))
                              for heading in ("Why", "What Changes")),
        "requirements": _cards(blocks, specs.DELTA_SECTIONS, change, delta_origin, embed),
        "stories": "\n".join(_stories(root, change, None, embed)),
        "diagrams": "\n".join(part for part in diagrams if part),
        "mockups": "\n".join(_folder(cap, base / cap / "assets" / day, root, embed)
                             for day, cap in cited if (base / cap / "assets" / day).is_dir()),
    }


def _require_frozen_app(root: Path, kind: str, legacy: str) -> None:
    from . import workspace

    if kind != "capability":
        raise specs.SpecsError("--legacy explains a capability, not a change")
    found = workspace.locate(root).workspace
    if found is None:
        raise specs.SpecsError("--legacy needs a workspace with frozen entries")
    apps = [repo.path.rsplit("/", 1)[-1] for repo in found.repos if repo.frozen]
    if legacy not in apps:
        raise specs.SpecsError(f"no frozen app {legacy}; frozen apps: {', '.join(apps) or 'none'}")


def explain(root: Path, cfg: Mapping[str, Any], name: str, narrative: str | None = None, out: str | None = None,
            today: date | None = None, legacy: str | None = None) -> dict[str, Any]:
    kind, target = _resolve(root, cfg, name)
    folder_name = target.parent.name if kind == "capability" else target.name
    if legacy is not None:
        _require_frozen_app(root, kind, legacy)
        folder = Path("legacy") / legacy / folder_name
    else:
        folder = Path(folder_name)
    path = (root / (out or str(Path(cfg["explain"]) / folder / f"{folder_name}.html"))).resolve()
    if not path.is_relative_to(root):
        raise specs.SpecsError(f"--out must stay inside the repository: {out}" if out
                               else f"artifacts.explain must stay inside the repository: {cfg['explain']}")
    embed = Embed(root)
    summary = _narrative(root, narrative, embed)
    document = _template(root, "explain.html", embed)
    if kind == "capability":
        title, bodies = _capability(root, cfg, folder_name, target, embed)
    else:
        title, bodies = _change(root, cfg, target, embed)
    bodies["overview"] = "\n".join(part for part in (summary, bodies["overview"]) if part)
    present = [(key, label) for key, label in TABS if bodies.get(key)]
    nav = "".join(f'<a href="#{key}">{label}</a>' for key, label in present)
    sections = "\n".join(f'<section class="tab" id="{key}"><h2>{label}</h2>\n{bodies[key]}</section>'
                         for key, label in present)
    shown_kind = f"legacy capability ({legacy})" if legacy is not None else kind
    html = fill(document, {"title": escape(title), "kind": shown_kind, "date": (today or date.today()).isoformat(),
                           "nav": nav, "sections": sections})
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    except OSError as error:
        raise specs.SpecsError(f"cannot write {out or path}: {error}") from error
    return {"path": specs.shown(root, path), "kind": kind, "missing": embed.missing}
