# Step 08 — Get a fresh view

**Goal:** break out of tunnel vision by bringing in a perspective that
hasn't been steeped in your current theories.

## Do

1. Write a short report of the situation aimed at someone who has no
   context. Cover:
   - The observable symptom (what fails, how, when).
   - The repro from step 02.
   - What you've ruled out (your `disproved` lists across steps).
   - What's still on the table.
   - Where you got stuck.
2. Hand it to a fresh reader: a teammate, a different AI session, a
   rubber duck, the user themselves.
3. **Report symptoms, not theories.** Lead with what is observed. Save
   your current theory for the end, and label it as a theory.
4. **Don't insist it's not your code.** The fresh reader's first
   suggestions are often things you already considered and dismissed.
   Resist the urge to dismiss them again. List the dismissals; let them
   challenge each one.
5. **Admit your uncertainties** explicitly. "I don't know whether X is
   the cause or a symptom" is more useful information than a confident
   guess.

## What "fresh view" means in an AI session

If you (the AI) have been the sole investigator, treat "fresh view" as:

- Re-read the audit trail from scratch as if you'd never seen it.
- Re-read the repro from step 02 as if you didn't write it.
- List every assumption from step 07 again — the second pass often
  catches things the first missed.

Or, prompt the user to look at the report and weigh in.

## Anti-pattern

Complaining about unrelated long-standing bugs ("oh, that subsystem has
always been flaky") instead of investigating *this* bug. Fix this bug
first. The "well-known" issues may turn out to be the same one.

## Update the audit trail

Under `steps.get_fresh_view.work`:

- **findings**: anything the fresh reader pointed out that you missed.
  1–3.
- **theories**: hypotheses raised by the fresh view. 0–2.
- **disproved**: dismissals you'd been carrying that the fresh view
  invalidated.

## Exit criteria

Either a new investigative thread to pull (return to step 03 with it),
or confirmation from a second perspective that you've genuinely
exhausted the obvious avenues — at which point the bug may need to be
escalated, parked, or solved by a different method (e.g. design change,
not code fix).

## Next

If new lead → [Step 03 — Quit guessing, look](03-quit-guessing-look.md)

If fix in hand → [Step 09 — Verify the fix](09-verify-fix.md)
