# Mockup HTML

The structure every `mockup/index.html` follows, and the default look when the repository has no UI and the harness has no `frontend-design` skill.

## Rules

- One file. CSS in one `<style>`, JavaScript in one `<script>`, both inline. No `<link>`, no `src="http..."`, no `@import`, no web font: the file opens offline from `file://`.
- Sample data is fictional: names like `Alex Pham`, amounts like `1,250.00`, dates near the folder's date.
- Each screen is `<section class="screen" id="<screen-id>" data-title="<Screen title>">`. Ids match `[a-z][a-z0-9-]*` and never change after the BA has seen them: requirements cite them.
- A screen with empty, error, or loading states holds one `<div data-state="<state>">` per state, `default` first.
- An image larger than an icon is a `<div class="placeholder">` with a caption naming what it shows.
- Controls respond: a button that opens another screen links to `#<screen-id>`; a form shows its validation message on submit.

## Skeleton

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Capability: mockup</title>
<style>
  :root { --bg: #f7f7f8; --surface: #ffffff; --text: #1d1d1f; --muted: #6b6b70; --accent: #2f5bd3; --danger: #c62828; --radius: 8px; --gap: 16px; font-family: system-ui, sans-serif; }
  body { margin: 0; background: var(--bg); color: var(--text); display: grid; grid-template-columns: 220px 1fr; min-height: 100vh; }
  nav { background: var(--surface); border-right: 1px solid #e3e3e6; padding: var(--gap); }
  nav a { display: block; padding: 6px 8px; border-radius: var(--radius); color: var(--text); text-decoration: none; }
  nav a[aria-current="page"] { background: var(--accent); color: #fff; }
  main { padding: calc(var(--gap) * 2); }
  .screen { display: none; }
  .screen.active { display: block; }
  .states { display: flex; gap: 8px; margin-bottom: var(--gap); }
  [data-state] { display: none; }
  [data-state].shown { display: block; }
  .placeholder { background: #e9e9ec; border-radius: var(--radius); display: grid; place-items: center; min-height: 120px; color: var(--muted); }
  @media (max-width: 720px) { body { grid-template-columns: 1fr; } nav { border-right: 0; border-bottom: 1px solid #e3e3e6; } }
</style>
</head>
<body>
<nav id="screens"></nav>
<main>
  <section class="screen" id="report-list" data-title="Report list">
    <h1>Reports</h1>
    <div data-state="default"><!-- the screen with sample data --></div>
    <div data-state="empty"><p>No reports yet.</p></div>
    <div data-state="error"><p role="alert">Reports could not be loaded. Try again.</p></div>
    <div data-state="loading"><p aria-busy="true">Loading reports</p></div>
  </section>
</main>
<script>
  const screens = [...document.querySelectorAll('.screen')];
  const nav = document.getElementById('screens');
  screens.forEach(s => { const a = document.createElement('a'); a.href = '#' + s.id; a.textContent = s.dataset.title; nav.append(a); });
  function showState(screen, state) {
    screen.querySelectorAll('[data-state]').forEach(d => d.classList.toggle('shown', d.dataset.state === state));
  }
  screens.forEach(s => {
    const states = [...s.querySelectorAll('[data-state]')].map(d => d.dataset.state);
    if (states.length > 1) {
      const bar = document.createElement('div'); bar.className = 'states';
      states.forEach(st => { const b = document.createElement('button'); b.type = 'button'; b.textContent = st; b.onclick = () => showState(s, st); bar.append(b); });
      s.insertBefore(bar, s.children[1] || null);
    }
    if (states.length) showState(s, states[0]);
  });
  function route() {
    const id = location.hash.slice(1) || screens[0].id;
    screens.forEach(s => s.classList.toggle('active', s.id === id));
    nav.querySelectorAll('a').forEach(a => {
      if (a.hash === '#' + id) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
  }
  window.addEventListener('hashchange', route);
  route();
</script>
</body>
</html>
```

## Default look

When neither the repository's UI nor `frontend-design` sets the look, keep the skeleton's tokens: a neutral background, one accent colour, the system font, 8px radius, and a 16px spacing step. Text contrast stays at 4.5:1 or more, every control has a visible label, and focus outlines stay visible.
