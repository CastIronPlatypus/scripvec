# Step 01 — Understand the system

**Goal:** know enough about the system to recognize what "wrong" looks like before you go looking for it.

## Do

1. Identify the component under investigation. Locate its README, docs, or
   primary entry point.
2. Read the relevant docs. If the system is large, read at minimum: the
   top-level overview, the module containing the suspected fault, and the
   configuration reference.
3. Run the system in its known-good mode (if one exists). Note what normal
   operation produces — exit codes, log lines, ports, files written.
4. Inventory the tools available for inspecting it: log paths, debugger
   support, profiler hooks, admin endpoints, structured-logging flags.

## Update the audit trail

Under `steps.understand_system.work` in the YAML file:

- **findings**: things you confirmed about how the system is supposed to
  behave (e.g. "Service exposes /healthz returning 200 when ready"). 1–3.
- **theories**: early hunches about where the fault might live, *based on
  the architecture you just learned*. 0–2.
- **disproved**: usually empty at this step.

## Exit criteria

You can describe, in one paragraph, what the system does, where its
interfaces are, and what tools you have to inspect it. If you can't, keep
reading.

## Anti-patterns

- Skipping this step because "I already know this codebase."
- Reading source instead of docs first. Docs tell you *intent*; source tells
  you *implementation*. You need intent first.

## Next

→ [Step 02 — Make it fail](02-make-it-fail.md)
