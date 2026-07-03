---
name: agent-browser
description: Automates browser interactions for web testing, form filling, screenshots, and data extraction. Use when the user needs to navigate websites, interact with web pages, fill forms, take screenshots, test web applications, or extract information from web pages.
---

# Browser Automation with agent-browser

## Quick start

```bash
agent-browser open <url>        # Navigate to page
agent-browser snapshot -i       # Get interactive elements with refs
agent-browser click @e1         # Click element by ref
agent-browser fill @e2 "text"   # Fill input by ref
agent-browser close             # Close browser
```

## Batch execution (recommended for AI agents)

Each CLI invocation has startup overhead. For multi-step flows, prefer `batch` to run several commands in a single process — much faster and atomic-ish:

```bash
agent-browser batch \
  "open https://example.com/login" \
  "fill @e1 user@example.com" \
  "fill @e2 password123" \
  "click @e3" \
  "wait --url **/dashboard"
```

Combine with `--json` for parseable output of every step.

## Core workflow

1. Navigate: `agent-browser open <url>`
2. Snapshot: `agent-browser snapshot -i` (returns elements with refs like `@e1`, `@e2`)
3. Interact using refs from the snapshot
4. Re-snapshot after navigation or significant DOM changes

## Commands

### Navigation
```bash
agent-browser open <url>      # Navigate to URL
agent-browser back            # Go back
agent-browser forward         # Go forward
agent-browser reload          # Reload page
agent-browser close           # Close browser
```

### Snapshot (page analysis)
```bash
agent-browser snapshot            # Full accessibility tree
agent-browser snapshot -i         # Interactive elements only (recommended)
agent-browser snapshot -c         # Compact output
agent-browser snapshot -d 3       # Limit depth to 3
agent-browser snapshot -s "#main" # Scope to CSS selector
```

### Interactions (use @refs from snapshot)
```bash
agent-browser click @e1           # Click
agent-browser dblclick @e1        # Double-click
agent-browser focus @e1           # Focus element
agent-browser fill @e2 "text"     # Clear and type
agent-browser type @e2 "text"     # Type without clearing
agent-browser press Enter         # Press key
agent-browser press Control+a     # Key combination
agent-browser keydown Shift       # Hold key down
agent-browser keyup Shift         # Release key
agent-browser hover @e1           # Hover
agent-browser check @e1           # Check checkbox
agent-browser uncheck @e1         # Uncheck checkbox
agent-browser select @e1 "value"  # Select dropdown
agent-browser scroll down 500     # Scroll page
agent-browser scrollintoview @e1  # Scroll element into view
agent-browser drag @e1 @e2        # Drag and drop
agent-browser upload @e1 file.pdf # Upload files
```

### Get information
```bash
agent-browser get text @e1        # Get element text
agent-browser get html @e1        # Get innerHTML
agent-browser get value @e1       # Get input value
agent-browser get attr @e1 href   # Get attribute
agent-browser get title           # Get page title
agent-browser get url             # Get current URL
agent-browser get count ".item"   # Count matching elements
agent-browser get box @e1         # Get bounding box
```

### Check state
```bash
agent-browser is visible @e1      # Check if visible
agent-browser is enabled @e1      # Check if enabled
agent-browser is checked @e1      # Check if checked
```

### Screenshots & PDF
```bash
agent-browser screenshot          # Screenshot to stdout
agent-browser screenshot path.png # Save to file
agent-browser screenshot --full   # Full page
agent-browser pdf output.pdf      # Save as PDF
```

### Video recording
```bash
agent-browser record start ./demo.webm    # Start recording (uses current URL + state)
agent-browser click @e1                   # Perform actions
agent-browser record stop                 # Stop and save video
agent-browser record restart ./take2.webm # Stop current + start new recording
```
Recording creates a fresh context but preserves cookies/storage from your session. If no URL is provided, it automatically returns to your current page. For smooth demos, explore first, then start recording.

### Wait
```bash
agent-browser wait @e1                     # Wait for element
agent-browser wait 2000                    # Wait milliseconds
agent-browser wait --text "Success"        # Wait for text
agent-browser wait --url "**/dashboard"    # Wait for URL pattern
agent-browser wait --load networkidle      # Wait for network idle
agent-browser wait --fn "window.ready"     # Wait for JS condition
```

### Mouse control
```bash
agent-browser mouse move 100 200      # Move mouse
agent-browser mouse down left         # Press button
agent-browser mouse up left           # Release button
agent-browser mouse wheel 100         # Scroll wheel
```

### Semantic locators (alternative to refs)
```bash
agent-browser find role button click --name "Submit"
agent-browser find text "Sign In" click
agent-browser find label "Email" fill "user@test.com"
agent-browser find first ".item" click
agent-browser find nth 2 "a" text
```

### Browser settings
```bash
agent-browser set viewport 1920 1080      # Set viewport size
agent-browser set device "iPhone 14"      # Emulate device
agent-browser set geo 37.7749 -122.4194   # Set geolocation
agent-browser set offline on              # Toggle offline mode
agent-browser set headers '{"X-Key":"v"}' # Extra HTTP headers
agent-browser set credentials user pass   # HTTP basic auth
agent-browser set media dark              # Emulate color scheme
```

### Cookies & Storage
```bash
agent-browser cookies                     # Get all cookies
agent-browser cookies set name value      # Set cookie
agent-browser cookies clear               # Clear cookies
agent-browser storage local               # Get all localStorage
agent-browser storage local key           # Get specific key
agent-browser storage local set k v       # Set value
agent-browser storage local clear         # Clear all
```

### Network
```bash
agent-browser network route <url>              # Intercept requests
agent-browser network route <url> --abort      # Block requests
agent-browser network route <url> --body '{}'  # Mock response
agent-browser network unroute [url]            # Remove routes
agent-browser network requests                 # View tracked requests
agent-browser network requests --filter api    # Filter requests
```

### Tabs & Windows
```bash
agent-browser tab                 # List tabs
agent-browser tab new [url]       # New tab
agent-browser tab 2               # Switch to tab
agent-browser tab close           # Close tab
agent-browser window new          # New window
```

### Frames
```bash
agent-browser frame "#iframe"     # Switch to iframe
agent-browser frame main          # Back to main frame
```

### Dialogs
```bash
agent-browser dialog accept [text]  # Accept dialog
agent-browser dialog dismiss        # Dismiss dialog
```

### JavaScript
```bash
agent-browser eval "document.title"   # Run JavaScript
```

### Natural-language control (chat)
```bash
agent-browser chat "log in then download the latest invoice"
```
Requires `AI_GATEWAY_API_KEY`. The model plans and executes the steps for you — useful for exploration, but for repeatable automation prefer explicit commands.

### Authentication vault (encrypted credentials)
The model never sees passwords — it only references the saved name.
```bash
agent-browser auth save mySite          # prompts for credentials, encrypts them
agent-browser auth login mySite          # uses saved credentials on the current page
agent-browser auth list
agent-browser auth delete mySite
```
Set `AGENT_BROWSER_ENCRYPTION_KEY` (64-char hex, AES-256-GCM) to control the key.

### React DevTools introspection
```bash
agent-browser open <url> --enable react-devtools
agent-browser react tree                  # component tree
agent-browser react profile start         # render profiling
```

### Live viewport stream
```bash
agent-browser stream enable               # WebSocket stream of the viewport
agent-browser stream disable
```

### Dashboard (live preview + observability)
```bash
agent-browser dashboard start             # default port 4848
agent-browser dashboard start --port 8080
```
Shows live viewport, command activity, console output. Optional in-dashboard AI chat with `AI_GATEWAY_API_KEY`.

## Configuration file

Project-level `agent-browser.json` or user-level `~/.agent-browser/config.json` (camelCase keys). CLI flags override config values; pass `--config <path>` to point elsewhere.

```json
{
  "$schema": "https://agent-browser.dev/schema.json",
  "headed": true,
  "profile": "./browser-data",
  "userAgent": "my-agent/1.0",
  "ignoreHttpsErrors": true,
  "defaultTimeout": 25000
}
```

## Environment variables

| Variable | Purpose |
|---|---|
| `AGENT_BROWSER_SESSION` | Isolated browser instance (same effect as `--session`) |
| `AGENT_BROWSER_SESSION_NAME` | Named session — auto-saves/restores cookies + localStorage |
| `AGENT_BROWSER_PROFILE` | Chrome profile name or persistent user-data dir |
| `AGENT_BROWSER_EXECUTABLE_PATH` | Custom browser binary |
| `AGENT_BROWSER_DEFAULT_TIMEOUT` | Per-operation timeout in ms (default 25000, intentionally < 30s CLI cap) |
| `AGENT_BROWSER_IDLE_TIMEOUT_MS` | Auto-shutdown daemon after inactivity |
| `AGENT_BROWSER_ENCRYPTION_KEY` | AES-256-GCM key for auth vault & state encryption |
| `AI_GATEWAY_API_KEY` | Enables `chat` command and dashboard AI |

## Safety flags (opt-in, important when an LLM drives the CLI)

```bash
--allowed-domains "example.com,*.example.com"   # block navigation outside allowlist
--action-policy ./policy.json                    # gate destructive actions
--content-boundaries                              # wrap untrusted page text in delimiters
--max-output 4000                                 # cap output chars to avoid context flooding
```

Use these whenever the agent operates on untrusted pages or with credentials available.

## Cloud / remote browser providers

Pass `-p <provider>` plus the provider's API-key env var:

```bash
export BROWSERLESS_API_KEY=...   && agent-browser -p browserless open <url>
export BROWSERBASE_API_KEY=...   && agent-browser -p browserbase open <url>
export BROWSER_USE_API_KEY=...   && agent-browser -p browseruse  open <url>
export KERNEL_API_KEY=...        && agent-browser -p kernel      open <url>
agent-browser -p agentcore open <url>                            # AWS Bedrock AgentCore
agent-browser -p ios --device "iPhone 16 Pro" open <url>          # iOS Simulator
```

Useful when local Chrome isn't available (CI, sandboxed environments) or when you need a managed/observed browser.

## Profile reuse (real Chrome login state)

```bash
agent-browser open <url> --profile ./browser-data    # persistent user-data dir
agent-browser open <url> --profile "Default"          # named Chrome profile
```
Survives across runs without re-login. Pair with `--session-name` for an automation-only profile.

## Example: Form submission

```bash
agent-browser open https://example.com/form
agent-browser snapshot -i
# Output shows: textbox "Email" [ref=e1], textbox "Password" [ref=e2], button "Submit" [ref=e3]

agent-browser fill @e1 "user@example.com"
agent-browser fill @e2 "password123"
agent-browser click @e3
agent-browser wait --load networkidle
agent-browser snapshot -i  # Check result
```

## Example: Authentication with saved state

```bash
# Login once
agent-browser open https://app.example.com/login
agent-browser snapshot -i
agent-browser fill @e1 "username"
agent-browser fill @e2 "password"
agent-browser click @e3
agent-browser wait --url "**/dashboard"
agent-browser state save auth.json

# Later sessions: load saved state
agent-browser state load auth.json
agent-browser open https://app.example.com/dashboard
```

## Sessions (parallel browsers)

```bash
agent-browser --session test1 open site-a.com
agent-browser --session test2 open site-b.com
agent-browser session list
```

## JSON output (for parsing)

Add `--json` for machine-readable output:
```bash
agent-browser snapshot -i --json
agent-browser get text @e1 --json
```

## Debugging

```bash
agent-browser open example.com --headed   # Show the browser window
agent-browser --cdp 9222 snapshot         # Attach to an existing Chrome via CDP
agent-browser console                     # View console messages
agent-browser console --clear             # Clear console
agent-browser errors                      # View page errors
agent-browser errors --clear              # Clear errors
agent-browser highlight @e1               # Highlight an element on the page
agent-browser trace start                 # Start a Playwright trace
agent-browser trace stop trace.zip        # Stop and save the trace
agent-browser record start ./debug.webm   # Record video from current page
agent-browser record stop                 # Stop and save recording
```

## Tips for AI-driven use

- **Always snapshot before interacting.** Refs (`@e1`…) only exist after `snapshot -i` and become stale after navigation/DOM changes.
- **Prefer `batch`** for multi-step flows — one process, much faster, atomic on the page state.
- **Use `--json`** when you need to parse output programmatically.
- **Use semantic locators (`find role/text/label`)** when refs are noisy or the snapshot is large.
- **Set `--allowed-domains` + `--max-output`** when running on untrusted pages.
- **Save state, don't re-login**: `state save auth.json` once, `state load` afterwards (or use the auth vault).
- **Daemon already running?** Subsequent commands are fast. Use `agent-browser session list` / `close` to manage instances.
