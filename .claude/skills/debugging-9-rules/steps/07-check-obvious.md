# Step 07 — Check the obvious

**Goal:** when you're stuck, audit the assumptions you've been treating as
ground truth.

You arrive here when steps 03–05 ran their course and the root cause is
still elusive. The bug is probably hiding behind something you took for
granted.

## Do

1. List your unstated assumptions. For each: how do you know? When did
   you last verify it?
2. Sanity-check the most foundational ones first:
   - Is the code you're looking at actually the code that's running?
     (Confirm with a deliberate, observable change — e.g. a new log
     line — and check that it appears.)
   - Is the binary/package up to date? Cache cleared? Module reloaded?
   - Are the env vars / config you think are set actually set in the
     failing process? Read them at runtime, don't trust the config file.
   - Is the process running as the user you think it is? In the
     directory you think it is?
3. Calibrate your tools. Run a known-good test case through the same
   debugger / logger / profiler. If the tool fails to detect the
   known-good case correctly, the tool is suspect.
4. Restart from the beginning. Re-run the repro from a clean state. Don't
   trust state accumulated from earlier debugging attempts.

## Question the bug report

- Is the user's described symptom actually what's happening, or their
  interpretation of what's happening?
- What did they not mention? Operating system, version, recent changes,
  whether anyone else is hitting it.

## Update the audit trail

Under `steps.check_obvious.work`:

- **findings**: assumptions you verified (or invalidated). e.g. "Confirmed
  Python 3.11 in failing process via `sys.version` at runtime; was
  assuming 3.12." 1–3.
- **theories**: new hypotheses raised by invalidated assumptions. 0–2.
- **disproved**: assumptions that turned out to be true after all (still
  worth recording — you ruled them out).

## Exit criteria

Either: an invalidated assumption opened a new investigative path (loop
back to step 03 with the new lead) — or every assumption you can think
of holds up.

## Next

If the obvious checks revealed something → return to [Step 03](03-quit-guessing-look.md) with the new lead.

Otherwise → [Step 08 — Get a fresh view](08-get-fresh-view.md)
