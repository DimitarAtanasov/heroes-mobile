# Reverse-engineering loop graph

Clean-room rules: no original game assets or code are committed. Tools read the
user's own legally owned game files at runtime. Specs are written from public
documentation of the formats and observable game mechanics.

```mermaid
flowchart LR
    A[Opus advisor: review state, pick next targets, assign model + file ownership] --> R{Complexity}
    R -->|mechanical, well-documented| H[Haiku worker]
    R -->|format parsing, moderate logic| So[Sonnet worker]
    R -->|architecture, ambiguity| O[Opus worker]
    H --> V[Lead verifies: full test suite]
    So --> V
    O --> V
    V -->|fail| A
    V -->|pass| C[Checkpoint: commit + push + update log]
    C --> N{Backlog empty or stop?}
    N -->|no| A
    N -->|yes| D[Done]
```

## Checkpoint log
| # | Checkpoint | Agent | Status |
|---|-----------|-------|--------|
| 0 | Repo scaffold + graph | lead | done |
| 1 | LOD archive reader | Haiku (stride fixed by lead) | done |
| 2 | DEF sprite + H3M map parsers | Sonnet | done (H3M stops after teams; unverified vs real files) |
| 3 | Combat/economy rules spec + engine design | Opus | done (uncertain items listed in rules.md, 12 experiments to verify) |
| 4 | CI workflow + README | Haiku | done |
| 5 | H3M sections after teams | Sonnet | done (layouts unverified; ban-bit semantics assumed) |
