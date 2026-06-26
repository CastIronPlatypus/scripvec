---
name: debugging-9-rules
description: >-
  Use when the user is stuck on a bug, regression, or "this should work but
  doesn't" problem and wants disciplined investigation rather than guesswork.
  Adapts David Agans' 9 Rules of Debugging into a step-by-step branching
  protocol with mandatory audit-trail notes. Trigger phrases: "/debug",
  "help me debug", "I'm stuck on a bug", "this isn't working and I don't
  know why", "find the root cause".
---

# debugging-9-rules

A protocol for systematic debugging. Adapted from David Agans' framework.

## How this skill works

This skill is a state machine, not a checklist. You walk through 9 steps in
order, branch at step 03 to pick an investigation tool, and loop back to
steps 07–08 when stuck. You exit through step 09 only after the fix is
verified against an explicit `done_when` check.

Throughout the session you maintain a YAML audit trail. This is mandatory —
it forces the discipline of separating what you've observed from what you're
guessing.

## Setup (do this first, before any step)

1. Copy `templates/debugging-session.yaml` to a session-specific file.
   Suggested location: alongside the code being debugged, named
   `debug-<bug-id>.yaml`.
2. Fill in `session.id`, `session.summary`, and `session.started`.
3. **Fill in `session.target_behavior` and `session.done_when` before
   investigating.** If you can't articulate what "working" looks like and
   how you'll verify it, you don't yet understand the problem well enough
   to debug it. Loop back to the user.

## The audit trail discipline

Every step you execute must update its corresponding entry in the YAML
file. The rules:

- **`findings`**: 1–3 entries per step, each ≤ 2 sentences. *Strict
  observations only* — log lines, command output, file content, stack
  frames. If you can't cite a source for it, it's not a finding.
- **`theories`**: 0–2 active hypotheses per step, each ≤ 2 sentences.
  These are guesses about what's happening. They must be falsifiable.
- **`disproved`**: when a theory is ruled out, move it here with a
  one-line reason. This prevents you from re-treading the same dead end.

See `steps/06-audit-trail.md` for the full discipline.

## The flow

```
01 understand-system  →  02 make-it-fail  →  03 quit-guessing-look
                                                        ↓
                                            (pick a branch in branches/)
                                                        ↓
                              04 divide-and-conquer  →  05 change-one-thing
                                                        ↓
                                                  06 audit-trail
                                                        ↓
                                            root cause found?
                                                  ↙        ↘
                                                yes        no
                                                  ↓         ↓
                                                  ↓    07 check-obvious
                                                  ↓         ↓
                                                  ↓    found?  ↙ ↘  no → 08 get-fresh-view
                                                  ↓     yes ↓             ↓
                                                  ↓        ↓              ↓
                                                  ↓        ↓              ↓
                                                09 verify-fix ←———————————┘
```

## Steps

Read the step file for the step you're currently on. Do not skip ahead.

1. [`steps/01-understand-system.md`](steps/01-understand-system.md)
2. [`steps/02-make-it-fail.md`](steps/02-make-it-fail.md)
3. [`steps/03-quit-guessing-look.md`](steps/03-quit-guessing-look.md) — branches here
4. [`steps/04-divide-and-conquer.md`](steps/04-divide-and-conquer.md)
5. [`steps/05-change-one-thing.md`](steps/05-change-one-thing.md)
6. [`steps/06-audit-trail.md`](steps/06-audit-trail.md) — cross-cutting; read once, apply throughout
7. [`steps/07-check-obvious.md`](steps/07-check-obvious.md)
8. [`steps/08-get-fresh-view.md`](steps/08-get-fresh-view.md)
9. [`steps/09-verify-fix.md`](steps/09-verify-fix.md)

## Tool branches (chosen at step 03)

Pick the one that matches the system under investigation. Read the file,
apply it, then return to step 04.

- [`branches/tool-gdb.md`](branches/tool-gdb.md) — compiled C/C++/Rust binaries
- [`branches/tool-pdbpp-scripts.md`](branches/tool-pdbpp-scripts.md) — Python scripts (CLIs, jobs, notebooks)
- [`branches/tool-pdbpp-servers.md`](branches/tool-pdbpp-servers.md) — running Python servers/daemons (remote attach)
- [`branches/tool-print-instrumentation.md`](branches/tool-print-instrumentation.md) — when a debugger is overkill or unavailable
- [`branches/tool-git-bisect.md`](branches/tool-git-bisect.md) — regressions where a previous version worked

## Helper scripts

- [`scripts/install-pdbpp.sh`](scripts/install-pdbpp.sh) — install pdb++ and a baseline `~/.pdbrc.py`
- [`scripts/pdbpp-breakpoint-template.py`](scripts/pdbpp-breakpoint-template.py) — minimal `breakpoint()` example
- [`scripts/pdbpp-remote-attach.py`](scripts/pdbpp-remote-attach.py) — attach to a running Python server

## Exit criteria

You may close the session (`session.status: fixed`) only when:

1. `resolution.root_cause` is filled in with a concrete, observable cause.
2. `resolution.fix` describes the change that addressed it.
3. `resolution.verified_by` records the result of running `session.done_when`.

If any of those is missing or vague, you are not done. Either go back to
step 09 or set `session.status: abandoned` with a note.

## References

- David Agans, *Debugging: The 9 Indispensable Rules for Finding Even the Most Elusive Software and Hardware Problems* — ISBN-13: 978-0814474570 — [debuggingrules.com](https://www.debuggingrules.com)
- [GDB quick reference card (UT Austin)](http://users.ece.utexas.edu/~adnan/gdb-refcard.pdf)
- [pdb++ on PyPI](https://pypi.org/project/pdbpp/)
