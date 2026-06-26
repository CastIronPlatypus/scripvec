# Branch — pdb++ for Python scripts

Use when the system under investigation is a Python script, CLI, batch
job, notebook cell, or any code you can launch directly. Reached from
[step 03](../steps/03-quit-guessing-look.md).

For Python servers and daemons (where you can't easily relaunch the
process), use [`tool-pdbpp-servers.md`](tool-pdbpp-servers.md) instead.

## What pdb++ is

`pdbpp` is a drop-in replacement for the stdlib `pdb`. Same interface,
plus syntax highlighting, sticky mode (live source view at the prompt),
tab completion, and a few extra commands. Once installed, `import pdb`
and `breakpoint()` automatically use it.

## Install

Run [`scripts/install-pdbpp.sh`](../scripts/install-pdbpp.sh), or:

```sh
pip install pdbpp
```

For per-project use, install into the project's venv. Avoid installing
into the system Python.

Optional: drop a `.pdbrc.py` in your home or project root for per-session
config (sticky mode by default, custom aliases). Example included with
the install script.

## Drop a breakpoint

In code:

```python
breakpoint()        # Python 3.7+, uses pdb++ if installed
```

Run the script normally. Execution stops at the `breakpoint()` call.

For an example file, see
[`scripts/pdbpp-breakpoint-template.py`](../scripts/pdbpp-breakpoint-template.py).

## Common commands

| Command | Action |
|---|---|
| `n` / `next` | Next line in current function |
| `s` / `step` | Step into call |
| `c` / `continue` | Resume until next breakpoint |
| `r` / `return` | Run until current function returns |
| `l` / `list` | Show source around current line |
| `ll` | Show whole current function (pdb++ extension) |
| `p <expr>` | Print value |
| `pp <expr>` | Pretty-print value |
| `w` / `where` | Show stack |
| `u` / `d` | Move up / down stack frame |
| `b <file:line>` / `b <function>` | Set breakpoint |
| `b <file:line>, <cond>` | Conditional breakpoint |
| `cl` | Clear breakpoints |
| `interact` | Drop into a full Python REPL with current frame's scope |
| `sticky` | Toggle sticky mode (live source pane) |
| `q` | Quit |

`!<expr>` runs `<expr>` as Python instead of as a debugger command —
useful when an expression collides with a command name.

## Patterns

- **Inspect a value mid-iteration:** put `breakpoint()` inside the loop
  body, guarded by the iteration count or condition you care about
  (`if i == 1234: breakpoint()`).
- **Post-mortem:** run the script with `python -m pdb -c continue
  myscript.py`. On unhandled exception, you drop into the debugger at
  the failure point. (Works with stdlib `pdb` too; pdb++ inherits.)
- **Interactive exploration:** at any prompt, type `interact` to get
  a real Python REPL with all locals available. Easier for poking at
  rich data structures than the constrained debugger prompt.
- **Conditional break with side effects:** the condition expression is
  re-evaluated every line, so keep it cheap. Don't put a network call
  in there.

## After this branch

Return to [Step 04 — Divide and conquer](../steps/04-divide-and-conquer.md)
with concrete findings (variable values, stack frame, exception
message) from the debugger session.

## Reference

[pdb++ on PyPI](https://pypi.org/project/pdbpp/)
