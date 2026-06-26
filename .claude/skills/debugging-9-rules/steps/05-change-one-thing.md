# Step 05 — Change one thing at a time

**Goal:** isolate cause from coincidence by varying exactly one variable
between runs.

## Do

1. Decide on the *one* change to test. Write it down before making it.
2. Capture the current state — both the input/configuration and the
   resulting failure mode. This is your baseline.
3. Apply the change. Re-run the repro from step 02.
4. Compare against baseline. The only differences in observable behavior
   should be attributable to the one change you made.
5. Revert the change before trying the next one — unless it improved
   things and you want to keep it. Either way, never have two
   uncommitted-and-untested experiments in flight at once.

## Why this matters

Two simultaneous changes hide each other. If the bug disappears, you
won't know which change fixed it; if it doesn't, you won't know whether
either change had any effect. You'll have learned nothing, but feel like
you did work.

## Useful framings

- **Compare bad to good.** If a similar input/config/version works,
  diff it against the broken one and study the differences. Each
  difference is a candidate single-thing-to-change.
- **Walk back through recent changes.** What's different since the last
  time it worked? Pick the smallest recent diff, undo it, re-test.

## Update the audit trail

Under `steps.change_one_thing.work`:

- **findings**: the change you tried + the observed effect. e.g.
  "Set `BATCH_SIZE=1` (was 64) → failure no longer reproduces." 1–3.
- **theories**: what that effect implies about the cause. 0–2.
- **disproved**: theories killed by changes that had no effect.

## Exit criteria

You have a change (or sequence of changes) where each one's effect on
the failure was individually observed. You can point to the specific
variable that controls whether the bug occurs.

## Next

→ [Step 06 — Audit trail](06-audit-trail.md)  *(cross-cutting; if you've been keeping it up, just check it.)*
