# Visual companion — protocol guide

Browser-based helper for visual brainstorming questions: mockups, wireframes, side-by-side comparisons, architecture diagrams. Not every question goes through the browser — only ones that are easier to see than to read.

> **v0.1.0 status:** the companion server is **not bundled** with claude-draft. This document describes the protocol so the offer in `:brainstorming` step 3 stays forward-compatible. If you have a companion server from another source, this guide explains how it interacts with the skill. A bundled implementation is targeted for v0.2.0.

## When to use the companion

Decide per question, not per session. The yardstick: would the user understand this faster by *seeing* it than by *reading* it?

**Use the companion** when the content itself is visual:

- UI mockups (wireframes, layouts, navigation, component designs)
- Architecture diagrams (system shape, data flow, relationships)
- Side-by-side comparisons of layouts or visual designs
- Polish questions (spacing, hierarchy, look-and-feel)
- Spatial structures rendered as diagrams (state machines, flowcharts)

**Stay in the terminal** when the answer is words or a tradeoff list:

- Requirements / scope ("what does X mean here?", "which features are in scope?")
- Conceptual A/B/C choices described in prose
- Pros/cons tables, technical decisions, API shape
- Any clarifying question whose answer is text

A question *about* a UI feature isn't automatically a visual question. "What kind of wizard do you want?" is conceptual — terminal. "Which of these three wizard layouts feels right?" is visual — companion.

## Server protocol (for reference)

A compatible companion server provides:

1. A startup command that prints connection JSON: `{port, url, screen_dir, state_dir}`.
2. A directory (`screen_dir`) where you write HTML files. The server watches the directory and serves the newest file to the browser.
3. A directory (`state_dir`) where the server writes user interaction events as JSON Lines.
4. A frame template that wraps content fragments with a header, theme CSS, selection indicator, and a small client-side helper.
5. A way to signal that the server is alive (`$state_dir/server-info`) or has shut down (`$state_dir/server-stopped`).

The skill does not depend on a specific implementation as long as the protocol is honored.

## Starting a session (when a server is available)

You will run a startup command provided by the server implementation. The exact command depends on which companion you have installed. After it runs:

- Capture the JSON it prints (`port`, `url`, `screen_dir`, `state_dir`).
- Save `screen_dir` and `state_dir` for the rest of the session.
- Tell the user the URL and ask them to open it.

If the URL is unreachable from the user's browser (remote development, container), the server should support binding to a non-loopback host with a separate displayed hostname.

If the startup command was launched in the background and you didn't capture stdout, read `$state_dir/server-info` to recover the connection details.

## Loop per question

1. **Confirm the server is alive.** Check that `$state_dir/server-info` exists and `$state_dir/server-stopped` does not. If it has shut down (most servers exit after some idle minutes), restart it before continuing.

2. **Write the screen** — a fresh HTML file inside `screen_dir`:
   - Use a semantic filename (`platform.html`, `layout.html`, `wizard-layouts.html`).
   - Never reuse a filename. Each screen is a new file.
   - Use the Write tool. Avoid `cat`/heredoc inside the Bash tool — they pollute the terminal with markup.
   - The server serves the newest file by modification time.

3. **End your turn with a brief framing message in the terminal:**
   - Repeat the URL (every step, not just the first).
   - One sentence summarizing what's on screen.
   - Invite the user to respond in the terminal — clicks in the browser are nice-to-have, not required.

4. **On the next turn**, before continuing:
   - Read `$state_dir/events` if it exists. Each line is a JSON object describing a click. The pattern of clicks can reveal hesitation; the last click is usually the final pick.
   - Combine that with the user's terminal text. The terminal text is primary; click events are corroborating evidence.

5. **Iterate or advance.** If the user wants changes, write a new file (`layout-v2.html`). Move to the next question only after the current one is settled.

6. **Unload when leaving the browser.** When the next step is text-only, push a small "waiting" screen so the user isn't staring at a stale picture:

   ```html
   <!-- filename: waiting.html -->
   <div style="display:flex;align-items:center;justify-content:center;min-height:60vh">
     <p class="subtitle">Continuing in the terminal…</p>
   </div>
   ```

   When the next visual question arrives, push a new content file as usual.

## Content fragments vs full HTML documents

If your file starts with `<!DOCTYPE` or `<html`, the server serves it untouched (it only injects the helper script). Otherwise, the server wraps your content in its frame template — adding the header, CSS theme, selection indicator, and interactive bits.

**Default to fragments.** Write only the part of the page that contains the question. Use the frame's CSS classes for layout. Reach for full HTML only when you need pixel-level control over the entire page.

## Frame CSS conventions (reference)

A typical frame template offers classes such as:

- `.options` (with optional `data-multiselect`) — A/B/C clickable choice cards
- `.cards` — larger card grid for visual designs
- `.mockup` (with `.mockup-header`, `.mockup-body`) — wireframe container
- `.split` — side-by-side comparison of two mockups
- `.pros-cons` (with `.pros`, `.cons`) — tradeoff display
- `.mock-nav`, `.mock-sidebar`, `.mock-content`, `.mock-button`, `.mock-input`, `.placeholder` — wireframe building blocks
- `.subtitle`, `.section`, `.label` — typography and section helpers
- `h2` for the page title, `h3` for section headings

Treat these as a guideline. The exact class set depends on your companion's frame template.

### Minimal example fragment

```html
<h2>Which layout works better?</h2>
<p class="subtitle">Consider readability and visual hierarchy.</p>

<div class="options">
  <div class="option" data-choice="a" onclick="toggleSelect(this)">
    <div class="letter">A</div>
    <div class="content">
      <h3>Single column</h3>
      <p>Clean, focused reading experience.</p>
    </div>
  </div>
  <div class="option" data-choice="b" onclick="toggleSelect(this)">
    <div class="letter">B</div>
    <div class="content">
      <h3>Two column</h3>
      <p>Sidebar navigation with a main content pane.</p>
    </div>
  </div>
</div>
```

No `<html>` wrapper, no embedded CSS, no scripts — the frame supplies them.

## Browser event format

The server records clicks to `$state_dir/events`, one JSON object per line:

```jsonl
{"type":"click","choice":"a","text":"Option A — Single column","timestamp":1706000101}
{"type":"click","choice":"c","text":"Option C — Hybrid",        "timestamp":1706000108}
{"type":"click","choice":"b","text":"Option B — Two column",    "timestamp":1706000115}
```

The file is reset whenever a new screen is pushed. If `$state_dir/events` is absent, the user didn't click anything — rely on their terminal message.

## Design tips

- **Match fidelity to the question.** Wireframes for "which layout?", polish for "does this look professional?".
- **Restate the question on the page.** "Which layout feels more professional?" beats "Pick one".
- **2–4 options per screen.** More than four becomes overwhelming.
- **Use real content where it matters.** A photography portfolio mockup with placeholder gray boxes hides design issues that real images would expose.
- **Iterate before advancing.** When feedback changes the current screen, push a v2 of that screen rather than moving on.

## File naming

- Semantic filenames: `platform.html`, `visual-style.html`, `layout.html`.
- Never reuse a filename. The server serves the newest file by modification time, so each new screen needs a new file.
- For iterations on the same screen, append a version suffix: `layout-v2.html`, `layout-v3.html`.

## Cleanup

When the brainstorming session ends, run the server's stop command (typically passes the session directory). If the server was started with a project-scoped path, the HTML files remain on disk for reference; ephemeral sessions in `/tmp` are deleted.
