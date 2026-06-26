# Branch — Print / log instrumentation

Use when a debugger is overkill, unavailable, or actively in the way:
embedded systems, parallel/distributed code, race conditions, very fast
inner loops, or production environments where you can't attach a
debugger. Reached from [step 03](../steps/03-quit-guessing-look.md).

## When prints beat a debugger

- **Concurrency.** A debugger pause changes timing enough to mask race
  conditions. Lightweight log calls preserve the timing you're trying
  to study.
- **High-frequency loops.** Stepping through 10,000 iterations is
  worse than dumping a CSV of values and grepping it.
- **Production / can't attach.** No interactive access; logs are all
  you have.
- **Cross-process / cross-host.** Log lines aggregate. Debugger
  sessions don't.

## Conventions for useful instrumentation

1. **Tag every line.** Include a unique marker so you can `grep` for
   exactly your debug output and ignore the rest.

   ```python
   print(f"[DBG-1234] entering process_batch, n={n}, ts={time.time()}")
   ```

2. **Log values, not narratives.** "Got bad value" is useless. "x=-1,
   expected x>=0" is useful.

3. **Include context the failure will need.** Timestamp, thread/PID,
   the loop index, the input identifier. Future-you reading the log
   should be able to localize a single failure without rerunning.

4. **Symmetric instrumentation.** If you log entry to a function, log
   exit too — including the return value. Otherwise you can't tell
   "didn't exit" from "exited fine but next thing crashed."

5. **Use a real logger if the codebase has one.** Standard library
   `logging`, structlog, your project's wrapper — they handle thread
   safety, redirection, and levels. Raw `print()` is fine for a
   throwaway investigation; if the instrumentation needs to live, use
   the logger.

6. **Make removal easy.** Tag with the same marker (`DBG-1234`) so you
   can `grep -r 'DBG-1234' . | wc -l` to count and `git diff` to
   verify before commit. Or wrap with `if DEBUG:` guards.

## Beware: instrumentation IS observation

Adding print statements changes timing, buffering, and sometimes
optimization. Heisenbug rules apply (see step 03). If the bug
disappears once you instrument:

- Try `sys.stderr` (unbuffered on most systems) instead of `sys.stdout`.
- Try writing to a memory buffer or ring buffer and dumping at exit
  instead of writing per-event.
- Try a sampling profiler (`py-spy`, `perf`) for a non-invasive look.

## Useful tricks

- **Tracing decorator** for "log every call to these functions":

  ```python
  def trace(f):
      def wrapper(*a, **kw):
          print(f"[DBG-1234] {f.__name__}({a!r}, {kw!r})")
          r = f(*a, **kw)
          print(f"[DBG-1234] {f.__name__} -> {r!r}")
          return r
      return wrapper
  ```

- **Conditional log** to skip the irrelevant 99%:
  `if i % 1000 == 0 or x < 0: print(...)`.

- **Dump-and-diff.** Log a wide cross-section of state at the failure
  point. Run the bad case and the good case; diff the dumps. The first
  difference is often a strong lead.

- **Environment-gated debug logs.** Wrap noisy lines in
  `if os.environ.get("DEBUG_FOO"):` so they only fire when you opt in.
  Lets you commit the instrumentation without polluting normal output.

## After this branch

Return to [Step 04 — Divide and conquer](../steps/04-divide-and-conquer.md).
The log output itself is your finding pool — quote specific lines into
the audit trail.

**Before exiting:** decide whether the instrumentation stays or goes. If
it stays (real logger, sensible level), note that in the audit trail. If
it goes, search for the marker tag and remove it before commit.
