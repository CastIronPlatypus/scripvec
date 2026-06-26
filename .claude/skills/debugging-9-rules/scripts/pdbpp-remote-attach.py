"""
pdbpp-remote-attach.py

Minimal example of attaching pdb++ to a running Python process via
remote-pdb. Use this when:

  * You're debugging a server, worker, or daemon whose stdin/stdout
    aren't usable (closed, redirected, supervisor-attached).
  * You need to break inside a long-running process you can't easily
    relaunch.

Setup:

    pip install remote-pdb pdbpp

Run this file:

    python pdbpp-remote-attach.py

Then, from another terminal:

    nc 127.0.0.1 4444

You'll be dropped into a pdb++ prompt with the server's frame. Type `c`
to release the server when you're done.

SAFETY:
  * Bind to 127.0.0.1 only. An open remote-pdb port is a remote code
    execution shell.
  * Strip these calls before shipping. They are not safe in production.
"""

import os
import time


def maybe_remote_breakpoint(host: str = "127.0.0.1", port: int = 4444) -> None:
    """Open a remote pdb++ socket if REMOTE_DEBUG=1 in the environment."""
    if os.environ.get("REMOTE_DEBUG") != "1":
        return
    try:
        from remote_pdb import RemotePdb
    except ImportError:
        print("remote-pdb not installed; skipping breakpoint.")
        return

    print(f"[remote-pdb] Listening on {host}:{port}. "
          f"Connect with: nc {host} {port}")
    RemotePdb(host, port).set_trace()


def long_running_loop() -> None:
    counter = 0
    while True:
        counter += 1

        # Fire the remote breakpoint on a condition you actually care
        # about — the first failing iteration, a specific value, etc.
        if counter == 5:
            maybe_remote_breakpoint()

        time.sleep(1)
        if counter >= 20:
            break


if __name__ == "__main__":
    print("Starting loop. Set REMOTE_DEBUG=1 to break at iteration 5.")
    long_running_loop()
    print("Done.")
