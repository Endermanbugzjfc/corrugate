# corrugate — a visual companion for Codex TUI

## Summary

Build **corrugate**, named after corrugated cat-scratching cardboard: a persistent whiteboard
beside unmodified Codex TUI in Kitty.

Target local Linux and macOS. Use Python, Textual, and textual-image, with TeX/`dvipng` for
mathematical expressions and CairoSVG for SVG. Deliver a Nix package and an installable local
Codex plugin.

## Publishing and persistence

- Provide `corrugate publish`, `view`, `attach`, and `doctor`.
- `publish` accepts JSON on stdin with conversation identity, description, math source or local
  image path, optional explanation text, and an optional existing item ID.
- New items receive stable IDs and conversation markers. Updating an item preserves its position
  and anchor. Return structured JSON distinguishing successful storage from display or navigation
  availability.
- Store one versioned SQLite database per conversation at
  `.corrugate/<conversation-id>.sqlite3`, relative to the project root, with a path override.
  Ignore generated boards in Git.
- Embed original sources, image bytes, previews, descriptions, ordering, and anchor metadata.
  Use transactions and rollback journaling so a closed database is a self-contained archive.
- Support mathematical LaTeX bodies, including matrices and multiline expressions, plus static
  PNG, JPEG, WebP, and self-contained SVG.
- Preserve content when terminal integration or rendering fails; show actionable diagnostics.
  Run rendering outside the UI event loop with execution limits and shell escape disabled for TeX.

## Codex and Kitty integration

- The corrugate plugin supplies publishing instructions and startup/resume hooks. Hooks provide
  conversation identity and warn about unavailable terminal integration without blocking Codex.
- Inspect actual alternate-screen state. Recommend `codex --no-alt-screen` when scrollback
  navigation is unavailable.
- Use verified Kitty instance/window identity, never whichever window happens to be active.
  When automatic association cannot be verified, save the content and provide an explicit
  `corrugate attach` command.
- After publishing, check for an existing viewer under a lock. Reuse it or open one pane to
  Codex's right without stealing focus. Reopen it on the next publish if the user closes it.
- The running viewer checks the database for changes. No launcher, permanent daemon, or external
  file watcher is required.
- Remote-control configuration remains the user's responsibility. Ship plugin installation and
  hook-trust instructions without automatically editing global configuration.

## Viewer and navigation

- Display chronological vertical cards containing descriptions and visuals.
- `j/k` select cards; `h/l` pan oversized visuals; zoom controls support inspection. New arrivals
  preserve selection unless the viewer is already following the end.
- Implement selection, navigation, panning, and zoom as shared actions, independent of keyboard
  bindings. Expose card focus and selection state so later mouse interaction and TUI buttons can
  reuse them.
- Space/Enter makes one alignment attempt, preserving viewer focus. Locate the conversation
  anchor, scroll Codex, reread the viewport, and correct with bounded retries. Reposition the card
  when Codex reaches a scroll boundary.
- Start with visible markers placed on recognizable standalone conversation lines. Structure
  publishing responses so they do not impersonate those lines.
- Add optional explanation-text matching for comparison. Normalize whitespace, require a unique
  match, and report ambiguity rather than guess.
- Use Kitty's standard remote commands for viewport reads and line scrolling; a custom kitten
  is not required initially.
- Report missing anchors, inaccessible history, and unstable output explicitly. Archived items
  remain viewable indefinitely; navigation works only when their linked text is available in the
  attached terminal.
- Clip large visuals, handle resizing, and clear graphics when cards disappear or the viewer exits.

## Delivery and validation

- Extend `flake.nix` with the corrugate application, development shell, rendering dependencies,
  and tests for Linux and macOS. Preserve existing working-tree changes.
- Create `GLOSSARY.md` defining whiteboard, item, card, and conversation anchor. Add concise ADRs
  explaining self-contained storage and scrollback-based navigation.
- Test publishing, updates, concurrency, schema handling, and reopening archives after original
  assets are deleted.
- Test equations, matrices, multiline math, SVG, transparency, malformed inputs, rendering
  failures, and oversized visuals.
- Test selection, focus preservation, follow-at-end behavior, shared actions, and reopening
  the viewer.
- Test disabled remote control, alternate-screen warnings, stale bindings, and simultaneous
  publishes opening only one viewer.
- Validate in real Kitty on Linux and macOS: split-induced wrapping, resizing, manual scrolling,
  streaming output, duplicate text, missing anchors, and scroll boundaries. Keep terminal-dependent
  acceptance explicitly pending until remote control is enabled.

Mouse controls, TUI buttons, SSH, tmux, full LaTeX documents, PDF, animation, deletion,
revision-history UI, and guaranteed navigation to absent history are deferred.

---

## Development handoff

This is an incomplete implementation checkpoint for moving development to another machine.

- Written but untested: Nix/Python package scaffold, SQLite storage, subprocess renderer, glossary,
  and two ADRs. Review these implementations before building on them.
- Not yet implemented: CLI, Kitty integration, navigation, Textual viewer, Codex plugin, tests,
  and user-facing README/setup instructions.
- The entry point references `corrugate.cli`, which does not exist yet. Nix packaging also copies
  a `plugin` directory that has not been created. The application is not runnable yet.
- Dependency setup was interrupted after repeated TLS errors and timeouts from `cache.nixos.org`,
  including a retry outside the sandbox. Both attempts were stopped. No tests or successful builds
  have run. Follow `AGENTS.md`: pause and inform the user on network errors or if sudo is needed.
- Resume dependency setup with `nix develop path:.`; the explicit path form includes untracked
  development files. If the default cache directory is read-only, use
  `XDG_CACHE_HOME=/tmp/corrugate-nix-cache nix develop path:.`.
- Remote control was disabled on the original machine. Live integration remains unverified.

### Research useful for continuing

- Kitty uses `vsplit` for panes side by side, under its `splits` layout. Use explicit window
  targeting and preserve focus when opening the viewer.
- Kitty 0.49.2 source was inspected: `get-text --extent screen --add-wrap-markers` reads the
  currently scrolled viewport. Preserve physical wrap boundaries when locating rows. `--extent all`
  can include pager history that is no longer scrollable, so verify the final viewport.
- `kitten @ ls` exposes `in_alternate_screen`, foreground processes, dimensions, window IDs,
  creation time, and user variables. A window ID alone does not identify a Kitty instance.
- Inherited `KITTY_WINDOW_ID` was present during research, but inheritance from a reused Codex
  daemon is not guaranteed. Explicit attachment is the fallback; do not guess from active focus.
- Codex hooks document a `session_id` input and user-visible `systemMessage` output. Hook trust
  must be handled through the normal plugin installation workflow.
- textual-image's `TGPImage` uses Kitty Unicode placeholders. Probe/import the image backend
  before Textual starts consuming terminal input. Large visuals may require viewport cropping
  because the placeholder renderer has dimension limits; verify against the pinned dependency.
- The original image rendering inspiration was `3rd/image.nvim`, particularly image caching,
  clipping, placement, and cleanup. No code has been copied from it.

References:

- [Kitty remote control](https://sw.kovidgoyal.net/kitty/remote-control/)
- [Kitty splits layout](https://sw.kovidgoyal.net/kitty/layouts/#the-splits-layout)
- [Kitty graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/)
- [Kitty custom kittens](https://sw.kovidgoyal.net/kitty/kittens/custom/)
- [textual-image](https://github.com/lnqs/textual-image)
- [image.nvim](https://github.com/3rd/image.nvim)
- [Codex hooks](https://learn.chatgpt.com/docs/hooks)
- [Codex plugin packaging](https://developers.openai.com/plugins/build/plugins)
- [CairoSVG](https://cairosvg.org/documentation/)
