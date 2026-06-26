# Step 02 — Make it fail

**Goal:** produce a reliable, minimal way to trigger the bug on demand.

## Do

1. Capture the exact invocation, input, or sequence of actions the user
   reports causes the failure.
2. Run it. Confirm you see the same failure mode they described.
3. Reduce. Strip away anything that isn't necessary to reproduce the bug:
   simpler input, fewer steps, smaller dataset. Stop reducing the moment
   the failure stops reproducing — the previous reduction was the last safe
   one.
4. Run the reduced repro at least 3 times. Note whether it's deterministic
   or intermittent.

## Special cases

- **Intermittent:** record the failure rate (e.g. "fails 3/10 runs"). Do
  not proceed as if it's deterministic.
- **Cannot reproduce:** stop. Without a repro, every later step is
  guessing. Loop back to the user for more detail (logs, screenshots,
  environment, exact steps), or escalate to step 08.
- **"Impossible" failure** (the code can't possibly do that): trust the
  observation. The code is doing it. Your model of the code is wrong.

## Update the audit trail

Under `steps.make_it_fail.work`:

- **findings**: the exact repro command/steps, observed failure mode,
  determinism rate, environment specifics that matter (OS, version, env
  vars). 1–3 entries.
- **theories**: candidate explanations for *why* the failure mode looks
  the way it does. 0–2.
- **disproved**: any "I bet it's X" you ruled out while building the
  repro.

## Exit criteria

You have a command, script, or step list that reproduces the failure on
demand (or with a recorded rate, for intermittent bugs). It's saved
somewhere durable, not just in your head.

## Next

→ [Step 03 — Quit guessing, look](03-quit-guessing-look.md)
