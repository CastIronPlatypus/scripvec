# Branch — `git bisect`

Use when the bug is a regression: there's a known-good commit, the bug
exists at HEAD, and you don't know which commit introduced it. Reached
from [step 03](../steps/03-quit-guessing-look.md) or
[step 04](../steps/04-divide-and-conquer.md).

`git bisect` is divide-and-conquer applied to commit history. It finds
the breaking commit in O(log N) tests.

## Prerequisites

You need:

1. A **good** commit where the bug is verifiably absent.
2. A **bad** commit where the bug is verifiably present (usually HEAD).
3. A **test command** that exits 0 if the bug is absent, non-zero if
   present. The repro from step 02 — wrapped in a script if needed.

## Manual bisect

```sh
git bisect start
git bisect bad                       # current commit is bad
git bisect good <known-good-sha>     # this commit was fine
```

Git checks out the midpoint commit. Run your test:

- If the bug is present: `git bisect bad`
- If absent: `git bisect good`
- If this commit can't be tested (build broken, irrelevant): `git bisect skip`

Git picks the next midpoint. Repeat until git announces the first bad
commit.

```sh
git bisect reset       # when done, returns to original HEAD
```

## Automated bisect

If your test is a shell command, bisect can drive itself:

```sh
git bisect start
git bisect bad
git bisect good <sha>
git bisect run ./test-the-bug.sh
```

`git bisect run` re-checks out, re-runs the script, and uses the exit
code to mark good/bad until it finds the culprit. Walk away and come
back to the answer.

The test script's exit codes:

- `0` — good (bug absent)
- `1`–`124` or `126`–`127` — bad (bug present)
- `125` — skip (this commit can't be tested)

## Test script template

```sh
#!/usr/bin/env bash
set -e

# Build (skip if commit doesn't build cleanly)
make clean && make all || exit 125

# Run the repro from step 02. Exit non-zero if bug is present.
./repro-the-bug || exit 1   # bug reproduced -> bad
exit 0                       # repro passed   -> good
```

Mark it executable, point `git bisect run` at it, and let it work.

## Pitfalls

- **Tests that depend on rebuilt artifacts:** if your bisect script
  doesn't fully rebuild, you may be testing the new commit's source
  against an old binary. Rebuild explicitly inside the script, or use
  `make clean` before each test.
- **Cached state across runs:** databases, generated files, `.pyc`
  caches. Wipe the relevant state at the top of the test script.
- **Submodules / lockfiles:** `git bisect` does not auto-update
  submodules. Add `git submodule update --init --recursive` at the top
  of the script if your project uses them.
- **Merge commits, large diffs:** the breaking commit may be a merge
  that pulled in 500 changes. You've localized to a commit, not a line.
  Read the diff, then continue with step 04 to localize within it.

## After this branch

You have a single commit (or merge) that introduced the bug. Read its
diff. The breaking change is in there. Return to
[step 04 — Divide and conquer](../steps/04-divide-and-conquer.md) and
narrow within the commit's diff using the techniques there, or jump
straight to [step 05 — Change one thing](../steps/05-change-one-thing.md)
if the diff is small.

Record the SHA in the audit trail under
`steps.divide_and_conquer.work.findings`.
