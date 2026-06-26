# Branch — GDB (compiled binaries)

Use when the system under investigation is a compiled C, C++, or Rust
binary. Reached from [step 03](../steps/03-quit-guessing-look.md).

## Prerequisites

- Build with debug symbols: `gcc -g` (or `cc -g`, `clang -g`).
- Disable optimization for the file or function in question: `-O0`.
  Optimized code reorders, inlines, and elides — debugger output gets
  confusing fast.
- For Rust: `cargo build` (debug profile by default), or
  `RUSTFLAGS="-g" cargo build --release` if you need an optimized but
  debuggable binary.

## Launch

```sh
gdb <executable>             # interactive
gdb --args <executable> arg1 arg2   # pass args to inferior
gdb -p <pid>                 # attach to running process
```

## Core commands

| Command | Action |
|---|---|
| `run` / `r [args]` | Start the program |
| `start` | Run and break at start of `main()` |
| `break <file:line>` / `b` | Set breakpoint at location |
| `break <function>` | Break on function entry |
| `watch <expr>` | Break when expression's value changes |
| `next` / `n` | Step to next source line (over function calls) |
| `step` / `s` | Step into the next function |
| `continue` / `c` | Resume until next breakpoint |
| `finish` | Run until current function returns |
| `print <expr>` / `p` | Print a value |
| `backtrace` / `bt` | Show the call stack |
| `up` / `down` | Move up/down stack frames |
| `info locals` | Show local variables in current frame |
| `info breakpoints` | List breakpoints |
| `quit` / `q` | Exit |

## Text User Interface

Combined source + debug pane:

- `Ctrl-X 1` — TUI with source only
- `Ctrl-X 2` — TUI with source + assembly
- `Ctrl-L` — refresh the screen if it glitches
- `Ctrl-X a` — toggle TUI off

## Common patterns

- **Crash investigation:** run the program, let it crash, then `bt` to
  get the failing stack. `frame N` to drop into a specific frame, then
  `info locals` and `print` to inspect state.
- **Conditional breakpoint:** `break file.c:42 if x > 100` — only
  trips when the condition holds. Saves you from stepping past
  thousands of irrelevant iterations.
- **Watchpoint on a struct field:** `watch *((SomeStruct*)ptr)->field`
  — catches the line that writes to it.
- **Core dump analysis:** `gdb <executable> <corefile>` — replays the
  crash without re-running. Useful when the crash is hard to reproduce
  live.

## After this branch

Return to [Step 04 — Divide and conquer](../steps/04-divide-and-conquer.md).
Use what you observed under `gdb` (variable values, stack frames) as
findings, and let those drive the next bisection experiment.

## Reference

[GDB quick reference card (UT Austin)](http://users.ece.utexas.edu/~adnan/gdb-refcard.pdf)
