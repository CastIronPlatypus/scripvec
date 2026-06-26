---
name: tkeep
description: >-
  Manage tmux sessions with tkeep — saving, resuming, archiving, restarting,
  and killing tmux sessions that contain Claude Code instances. Use when
  asked about saving tmux sessions, resuming Claude Code work, managing
  tmux workspace layout, or when told to run tkeep.
---

# tkeep — tmux session keeper

CLI tool at `/data/projects/flywheel/tools/utilities/human/tkeep/tkeep`.
Saves and restores tmux sessions with full Claude Code session tracking.

## When to invoke this skill

- Asked to save, resume, archive, restart, or kill a tmux session
- Asked about tkeep flags, usage, or troubleshooting
- Told to use tkeep

## What tkeep does

Saves the full state of a tmux session — windows, panes, layouts, working
directories, and which panes are running Claude Code (including the session
ID). On resume, it rebuilds the tmux session and launches `cc --resume
<session-id>` in each Claude Code pane.

## Commands

```bash
tkeep --save <session>       # Save running tmux session
tkeep --resume <session>     # Rebuild from save (refuses if session active)
tkeep --kill <session>       # Kill session (10s warning if unsaved)
tkeep --archive <session>    # Save + kill
tkeep --restart <session>    # Save + kill + rebuild
tkeep --list                 # List saved sessions
```

## Options

```bash
--theme <light|dark|auto>    # Set Claude Code theme before launch
--prompt <message>           # Send message to all Claude panes after launch
--favorite                   # Save current flags as default for bare 'tkeep'
```

## Typical workflows to suggest

**End of day:**
```bash
tkeep --archive myproject
```

**Start of day:**
```bash
tkeep --resume myproject --theme dark
```

**Quick restart with prompt:**
```bash
tkeep --restart myproject --prompt "continue where you left off"
```

**Set up a one-command default:**
```bash
tkeep --restart myproject --theme auto --favorite
tkeep  # runs the saved favorite
```

## Safety notes

- `--resume` refuses if the session is still running — suggest `--restart`
- `--kill` pauses 10 seconds with Ctrl+C escape if session wasn't saved
- Session data lives in `~/.tkeep/sessions/*.json`
- Theme changes modify `~/.claude/settings.json` globally
- Uses `cc` alias (not `claude` directly) to respect user's preferred flags

## Notes

- The binary must be built first: `cd /data/projects/flywheel/tools/utilities/human/tkeep && go build -o tkeep .`
- Or install system-wide: `sudo ln -sf /data/projects/flywheel/tools/utilities/human/tkeep/tkeep /usr/local/bin/tkeep`
