# Step 04 — Divide and conquer

**Goal:** narrow the search space with experiments that each eliminate a
large fraction of possible causes.

## Do

1. List the candidate locations or causes implied by your current
   findings. Aim for a list, not a single suspect.
2. Design an experiment whose outcome will eliminate roughly half the
   list, regardless of which way it goes. Bisecting beats single-point
   probing.
3. Run it. Record the result.
4. Cross out the eliminated half. Repeat on what remains.

## Useful techniques

- **Comment out / `#ifdef` out** sections of code to isolate which
  fragment carries the bug.
- **Toggle inputs** at suspected boundaries (config flag, env var,
  alternate input file) to localize whether the issue is data- or
  code-driven.
- **`git bisect`** when the bug is a regression — see
  [`branches/tool-git-bisect.md`](../branches/tool-git-bisect.md).
- **Layer probes** at module boundaries to find which layer the bad
  value first appears in.

## Pre-existing noise

If the system has known unrelated bugs that produce noise (warnings,
spurious failures, flaky tests), fix or silence those first. Otherwise
you'll waste investigation cycles on red herrings.

## Update the audit trail

Under `steps.divide_and_conquer.work`:

- **findings**: experiment + outcome pairs. e.g. "Disabled module X →
  failure still occurs → fault is not in X." 1–3.
- **theories**: what the surviving half implies. 0–2.
- **disproved**: candidates eliminated by this round.

## Exit criteria

The candidate set has been narrowed to one suspect file, function, or
data path — small enough that step 05's "change one thing" makes sense.

## Next

→ [Step 05 — Change one thing at a time](05-change-one-thing.md)
