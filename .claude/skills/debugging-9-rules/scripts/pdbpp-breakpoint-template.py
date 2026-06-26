"""
pdbpp-breakpoint-template.py

Minimal example of using `breakpoint()` with pdb++ for a Python script.
Run with:

    python pdbpp-breakpoint-template.py

When execution hits the breakpoint, you'll get a pdb++ prompt with the
current frame's locals available. Common moves:

    n           next line
    s           step into call
    c           continue
    p x         print value of x
    pp data     pretty-print data
    ll          list the whole current function
    interact    open a real Python REPL with current scope
    q           quit

If pdb++ is not installed, this falls back to stdlib pdb (same
interface, fewer niceties). Install with `scripts/install-pdbpp.sh`.
"""

import argparse


def process_item(item: dict) -> dict:
    """Pretend this is the function you suspect is misbehaving."""
    # Drop a breakpoint here when you want to inspect each item as it's
    # processed. Guard with a condition so you don't stop on every one.
    if item.get("id") == "suspect-id":
        breakpoint()  # <-- pdb++ stops here

    item["processed"] = True
    return item


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=5, help="number of items")
    args = parser.parse_args(argv)

    items = [{"id": f"item-{i}"} for i in range(args.n)]
    items.insert(args.n // 2, {"id": "suspect-id"})

    for it in items:
        process_item(it)

    print(f"Processed {len(items)} items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
