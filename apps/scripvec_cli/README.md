# scripvec_cli

The single MVP deployable — a Typer-backed command-line interface that accepts a query string and returns top-k verses from the Book of Mormon and Doctrine and Covenants.

Allowed in-repo imports: `packages/retrieval` only (per the dependency graph in `docs/specs/adrs/003_accepted_mvp_folder_structure.md`).

---

## `vex` CLI — Command Reference

**Entry point:** `vex` (registered as `scripvec_cli`)

---

### Root

```
vex [--version | -V]
```

Global flag: `--version / -V` — outputs JSON `{cli_version, embedding_model, latest_index_hash}` and exits.

---

### `vex query <TEXT>`

Search scripture verses.

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--k` | `-k` | int | `10` | Number of results |
| `--mode` | `-m` | enum | `hybrid` | `bm25` \| `dense` \| `hybrid` |
| `--format` | `-f` | enum | `json` | `json` \| `text` |
| `--index` | `-i` | str | `"latest"` | Index hash or `"latest"` |
| `--show-scores` | — | bool | `false` | Include scores in output |
| `--floor` | — | float | — | Minimum score threshold [0.0-1.0], mode-dependent |
| `--window` | — | int | config | Include N verses before and after each hit |
| `--dedupe` | — | flag | `true` | Enable proximity deduplication (default) |
| `--no-dedupe` | — | flag | — | Disable proximity deduplication |

**JSON output shape:**
```json
{
  "query": "...",
  "mode": "hybrid",
  "k": 10,
  "index": "<hash>",
  "floor": null,
  "latency_ms": {...},
  "results": [
    {"rank": 1, "verse_id": "...", "ref": "...", "text": "...", "forced": false}
  ]
}
```

**Exit codes:** `0` success · `1` user error · `2` index not found · `3` upstream/embedding error

#### Deduplication and Window Context

**Dedupe runs before window expansion.** When both `--dedupe` (default) and `--window N` are active, the pipeline first deduplicates nearby hits, then attaches context windows to the surviving hits. This order avoids wasting work on windows for hits that would be dropped, and ensures a predictable payload shape.

**Study-flow recommendation:** When using both `--window` and `--dedupe`, consider lower `--k` values (1-3) to get richer context per hit rather than many hits with narrow windows. This is a recommendation, not an enforced rule.

**Default behavior:** Proximity deduplication is on by default. Use `--no-dedupe` when you want raw retrieval order without proximity-based consolidation.

#### Similarity Floor (`--floor`)

The `--floor` flag sets a minimum score threshold for results. Its interpretation depends on the retrieval mode:

| Mode | Interpretation | Behavior |
|------|----------------|----------|
| `dense` | **Absolute** cosine similarity | Drops hits with cosine score < floor |
| `bm25` | **Relative** to top BM25 score | Drops hits with score < floor × top_score |
| `hybrid` | **Relative** to top RRF score | Drops hits with score < floor × top_rrf |

**Valid range:** `[0.0, 1.0]`. Values outside this range return a structured error (exit code 1) naming the flag, mode, and accepted range.

**Floor 0.0:** Acts as a no-op (keeps all hits), but the response's `floor` field is still populated.

**Floor absent:** The response's `floor` field is `null`.

**Response shape with floor:**
```json
{
  "floor": {
    "value": 0.5,
    "interpretation": "relative",
    "effective_threshold": 0.0156
  }
}
```

- `value`: The floor value you passed
- `interpretation`: `"absolute"` (dense) or `"relative"` (bm25/hybrid)
- `effective_threshold`: The concrete cutoff in the mode's native score units

**Example:** With `--mode hybrid --floor 0.5` and a top RRF score of 0.0312, the effective threshold is 0.0156. Hits below this threshold are dropped.

---

### `vex version`

Outputs same JSON as `--version` flag: `{cli_version, embedding_model, latest_index_hash}`

---

### `vex index build`

Build search index from corpus.

| Flag | Default | Description |
|------|---------|-------------|
| `--from-scratch` / `--incremental` | `--from-scratch` | Full rebuild (incremental not yet supported) |
| `--rebuild-corpus` | `false` | Allow corpus drift and rebuild |

**JSON output:** `{"index_hash": "<hex>", "latest": true}`

---

### `vex index list`

List all built indexes.

**JSON output:** array of `{hash, created_at, model, dim, is_latest}`, sorted by hash ascending.

---

### `vex eval run`

Run evaluation suite against an index.

| Flag | Default | Description |
|------|---------|-------------|
| `--queries` | `data/eval/queries.jsonl` | Path to queries JSONL |
| `--judgments` | `data/eval/judgments.jsonl` | Path to judgments JSONL |
| `--index` | `"latest"` | Index hash or `"latest"` |
| `--format` | `"json"` | `json` \| `text` |

**JSON output shape:** `{index_hash, metrics[], recall10_by_bucket, ship{hybrid_beats_bm25_recall10, dense_beats_bm25_recall10, index_size_under_400mb, all_passed}, failures_path}`

---

### `vex feedback feedback`

Record relevance feedback for a query result.

| Flag | Required | Description |
|------|----------|-------------|
| `--query-id` | yes | Query ID |
| `--verse-id` | yes | Verse ID to rate |
| `--grade` | yes | `0`, `1`, or `2` |
| `--note` | no | Optional note string |

**JSON output:** `{"status": "recorded", "query_id": "...", "verse_id": "...", "grade": N}`
