# Step 03 — Quit guessing, look

**Goal:** observe the actual failure with the right tool, instead of
speculating about it.

## Do

1. Pick an investigation tool. The choice depends on the system:

   | System | Branch |
   |---|---|
   | Compiled C/C++/Rust binary | [`branches/tool-gdb.md`](../branches/tool-gdb.md) |
   | Python script (CLI, job, batch) | [`branches/tool-pdbpp-scripts.md`](../branches/tool-pdbpp-scripts.md) |
   | Running Python server/daemon | [`branches/tool-pdbpp-servers.md`](../branches/tool-pdbpp-servers.md) |
   | No debugger available, or overkill | [`branches/tool-print-instrumentation.md`](../branches/tool-print-instrumentation.md) |
   | Used to work, regressed in history | [`branches/tool-git-bisect.md`](../branches/tool-git-bisect.md) |

2. Read the chosen branch file. Apply it.
3. Capture concrete data: actual values of variables at the failure point,
   actual stack at the crash, actual log line that immediately precedes
   the symptom. **Numbers, strings, or paths — not paraphrases.**

## Beware

- **Heisenbugs.** Adding instrumentation can change timing, memory layout,
  or scheduling enough to mask the bug. If the bug disappears the moment
  you start watching, the instrumentation itself is part of the problem.
  Note this in the audit trail and try a less-invasive observation method
  (logs, core dumps, snapshots).
- **Confirmation bias.** It's tempting to look for evidence of your
  current theory. Look at *all* the data near the failure, not just what
  you expected to see.

## Update the audit trail

Under `steps.quit_guessing_look.work`:

- **findings**: literal observations from the tool. Variable values,
  stack frames, log timestamps. Quote them. 1–3.
- **theories**: refined hypotheses *grounded in those observations*. 0–2.
- **disproved**: prior theories killed by what you just saw.

## Exit criteria

You have at least one concrete, cited observation about the failure point
— not a theory.

## Next

→ [Step 04 — Divide and conquer](04-divide-and-conquer.md)
