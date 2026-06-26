# Step 06 — Keep an audit trail

**Goal:** maintain a structured, honest record of the investigation so
you don't re-tread dead ends and so you can hand off, resume, or review
the session later.

This step is **cross-cutting**. You don't "do" it at one moment in the
flow — you do it continuously, every time you finish work on any of the
other steps. Read this file once at the start of the session and refer
back to it whenever you're about to write a new entry in the YAML file.

## The discipline

The session's YAML file (copied from
[`templates/debugging-session.yaml`](../templates/debugging-session.yaml))
has one block per step. Each step's `work` array contains three lists:

### `findings` — strict observations

- 1 to 3 entries per step. Each ≤ 2 sentences.
- Must be something you actually saw: log line, command output, file
  content, stack frame, variable value, error message.
- Quote or cite the source. "POST /login returned 500" is fine. "The
  login is broken" is not — that's a paraphrase, not an observation.
- If you cannot point to where you got it, it is not a finding. It's a
  theory. Move it.

### `theories` — current hypotheses

- 0 to 2 active theories per step. Each ≤ 2 sentences.
- Must be falsifiable. "Memory pressure causes the timeout" is testable
  and counts. "Something weird is happening with memory" is not.
- A theory stays in `theories` only as long as it's *actively in
  contention*. The moment evidence rules it out, move it to `disproved`.

### `disproved` — ruled-out theories with reasons

- An array of objects: `{ theory: "...", reason: "..." }`.
- The reason must cite the finding that killed it. "Same payload works
  on staging" is a real reason. "Probably not it" is not.

## Why this is enforced

Bugs go in circles when you forget which theories you already disproved.
A loose, prose-style "I tried some stuff" log doesn't prevent that.
Forcing observations and hypotheses into separate buckets, with explicit
rejection reasons, makes the same wrong path harder to walk twice.

It also stops you from silently upgrading a theory to a fact. Every
sentence in `findings` must answer "where did I see this?" — that
question alone catches a huge amount of self-deception.

## Light-touch when the bug is trivial

If the whole investigation took 5 minutes, the YAML overhead is
overkill. Skip it. The discipline matters when:

- You've been stuck for more than ~15 minutes, or
- More than one engineer is involved, or
- The bug is subtle, intermittent, or environmental, or
- You expect to hand the session off.

## Update the audit trail

Under `steps.audit_trail.work`, record observations *about the
investigation itself* — not about the bug. e.g. "Two theories from
step 03 contradicted each other; both moved to `disproved` after the
step 04 experiment."

## Exit criteria

This step has no exit. It runs to the end of the session. The session
itself exits via step 09.

## Next

→ Continue to whichever step you were on, or:
→ [Step 07 — Check the obvious](07-check-obvious.md) *(if root cause not yet found)*
→ [Step 09 — Verify the fix](09-verify-fix.md) *(if root cause found)*
