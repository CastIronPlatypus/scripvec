# Step 09 — If you didn't fix it, it ain't fixed

**Goal:** confirm that the change actually fixed the bug, that *your*
change is what fixed it, and that nothing else broke.

You arrive here with a candidate fix in hand. Do not skip any of the
checks below — most "fixed" bugs that come back came back because one of
these was skipped.

## Do

1. **Confirm the bug reproduces without the fix.** Revert the change.
   Run the repro from step 02. The failure must still occur. If it
   doesn't, the bug "fixed itself" — meaning it's still there, hidden,
   waiting to resurface. Stop and figure out why before re-applying
   your change.
2. **Confirm the fix resolves the bug.** Re-apply the change. Run the
   repro. The failure must not occur.
3. **Confirm it's *your* fix doing the work.** Do steps 1 and 2 a second
   time on a clean checkout if the codebase has any caching, generated
   files, or in-memory state. Builds lie.
4. **Run the `done_when` check** from `session.done_when` exactly as
   written. Record the result.
5. **Run the broader regression suite.** Tests, linters, smoke tests,
   anything available. Your fix must not break anything else.
6. **Address the root cause, not the symptom.** If the fix masks the
   underlying problem instead of correcting it (e.g. catching an
   exception that should never have been raised), file it as a known
   workaround and open a follow-up for the real fix. Do not pretend
   masking is fixing.
7. **Add a regression test.** Whatever repro you used in step 02 should
   become a permanent test case so the bug can't sneak back unnoticed.

## Suspicion checklist

- The bug "just went away" → step 1 above probably didn't reproduce it.
  The bug is still there.
- The fix is "obviously correct" but you didn't see it run → step 3.
  Builds, caches, stale containers, hot reloaders, browser caches all
  lie about what code is running.
- A different test now fails → your fix broke something. Don't ship.

## Update the audit trail

Under `steps.verify_fix.work`:

- **findings**: results of each check above (revert reproduces, fix
  resolves, done_when passes, regression suite passes). 1–3.
- **theories**: 0 — by this point you should be operating on facts.
- **disproved**: any "I'm sure that's the fix" theories that didn't
  survive verification.

Then fill `resolution`:

- `root_cause`: the concrete cause, not the symptom.
- `fix`: the change made, including the file or commit reference.
- `verified_by`: the literal command/test result that proves it.

## Exit criteria

`session.status: fixed`. All three resolution fields populated. Regression
test added. Anything you couldn't fully resolve (root cause unclear,
fix is a workaround, design issue exposed) is captured as a follow-up
note in the YAML before closing the session.

## Done

The session is closed. Archive the YAML file alongside the bug report,
post-mortem, or commit message that references it.
