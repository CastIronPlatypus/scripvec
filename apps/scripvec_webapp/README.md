# scripvec_webapp

Web front-end for scripvec — a thin FastAPI layer over the `scripvec` CLI per CR-010.

The webapp does **not** import `packages/retrieval`. It shells out to the `scripvec`
CLI for retrieval, version, and feedback operations, and reads `data/raw/bcbooks/`
directly for on-demand chapter context (separate axis from CLI `--window`, per CR-010).

## Running

```bash
# from repo root, after `uv sync` has installed the workspace
scripvec-web                       # serves on http://127.0.0.1:8765
scripvec-web --host 0.0.0.0 --port 8000
```

Or programmatically:

```bash
python -m scripvec_webapp
```

The webapp requires:

1. The `scripvec` CLI on the `PATH` (installed via `uv sync` from this workspace).
2. At least one built index (`scripvec index build`) for queries to return results.
3. `data/raw/bcbooks/*.json` present for the details-view chapter loader.

## Endpoints

| Path                | Method | Backed by                         |
|---------------------|--------|-----------------------------------|
| `/`                 | GET    | static UI (`static/index.html`)   |
| `/api/version`      | GET    | `scripvec --version`              |
| `/api/indexes`      | GET    | `scripvec index list`             |
| `/api/query`        | POST   | `scripvec query`                  |
| `/api/chapter`      | GET    | direct read of `data/raw/bcbooks` |
| `/api/feedback`     | POST   | `scripvec feedback feedback`      |

## UI

Four scenes from the wireframe, wired to the real API:

1. **Search-first** — single hero query field + result list.
2. **Split pane** — left filter rail + result list (top-k slider, similarity floor stub).
3. **Research** — turn-based query thread + Notes & Verses list + saved-lists rail (localStorage).
4. **Details view** — clicked verse opens in its full chapter, with a "Semantically similar" auto-search using the verse text as the query.
