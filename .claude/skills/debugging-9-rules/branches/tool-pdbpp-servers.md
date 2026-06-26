# Branch — pdb++ for running Python servers

Use when the bug lives in a long-running Python process you can't easily
relaunch — a web server, worker, daemon, or any service where stopping
to add `breakpoint()` and rerunning is expensive or impossible. Reached
from [step 03](../steps/03-quit-guessing-look.md).

For one-shot scripts and CLIs, use
[`tool-pdbpp-scripts.md`](tool-pdbpp-scripts.md) instead.

## The problem

`breakpoint()` opens a debugger on stdin/stdout — fine for a CLI you ran
in your terminal, useless for a daemon whose stdin/stdout are closed,
redirected, or attached to a process supervisor.

The fix: a *remote* debugger. The process exposes the debugger over a
socket; you connect to it from another terminal.

## Two common approaches

### Option A — `remote_pdb` (simplest)

`remote_pdb` is a small library that opens pdb (or pdb++) on a TCP port
instead of stdin/stdout.

```sh
pip install remote-pdb
```

In the server code, where you'd normally write `breakpoint()`:

```python
from remote_pdb import RemotePdb
RemotePdb('127.0.0.1', 4444).set_trace()
```

The process blocks until you connect:

```sh
nc 127.0.0.1 4444     # or: telnet 127.0.0.1 4444
```

You're now at a pdb++ prompt with the server's frame. `c` to release the
process when done.

For a runnable example, see
[`scripts/pdbpp-remote-attach.py`](../scripts/pdbpp-remote-attach.py).

### Option B — environment variable trigger

If you can't easily edit the server code but can set env vars at
launch, use `PYTHONBREAKPOINT` to redirect the builtin `breakpoint()`
to a remote debugger:

```sh
pip install remote-pdb
PYTHONBREAKPOINT=remote_pdb.set_trace REMOTE_PDB_HOST=127.0.0.1 \
  REMOTE_PDB_PORT=4444 python server.py
```

Now any `breakpoint()` call already in the code — even ones you didn't
write — goes to the remote socket instead of crashing.

## Inserting a breakpoint without restarting

Sometimes you can't restart the server but you can reach it via an admin
endpoint or a signal handler. Two options:

1. **Signal handler trick.** If the server already installs a SIGUSR1
   handler that runs an arbitrary callable (some frameworks do), point
   it at `RemotePdb(...).set_trace()`.
2. **`pyrasite` / `py-spy dump`.** Out-of-process inspection without
   stopping the server. `py-spy dump --pid <PID>` prints stack traces
   for every thread without needing any code change. Less interactive
   than pdb++ but useful for "what is this process doing right now."

## Safety

- Bind remote pdb to **`127.0.0.1` only**. Never `0.0.0.0` on a shared
  host. An open pdb socket is a remote code execution port.
- Strip remote-pdb hooks before deploying. A `breakpoint()` that
  silently exposes a TCP shell is not something you ship.
- In production, prefer logging + py-spy over remote pdb. Remote pdb is
  for staging and dev environments.

## Common commands

Once connected, the prompt is a normal pdb++ session — see
[`tool-pdbpp-scripts.md`](tool-pdbpp-scripts.md) for the command table.

## After this branch

Return to [Step 04 — Divide and conquer](../steps/04-divide-and-conquer.md)
with the observations you captured at the prompt — current request,
worker state, queue depth, whatever the bug touches.

## Reference

- [remote-pdb on PyPI](https://pypi.org/project/remote-pdb/)
- [py-spy](https://github.com/benfred/py-spy) — sampling profiler with
  `dump` and `top` subcommands for live inspection
