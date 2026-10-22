# Architecture

## Component boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                     Control Plane (untrusted network)        │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ daemon-fleet│  │ daemon-      │  │ API /v1            │  │
│  │ inventory   │  │ provision    │  │ (auth required)    │  │
│  └──────┬──────┘  └──────┬───────┘  └─────────┬──────────┘  │
│         │                │                    │             │
│         └────────────────┼────────────────────┘             │
│                          ▼                                  │
│                 ┌─────────────────┐                         │
│                 │  Task Store +   │                         │
│                 │  Runtime        │                         │
│                 └────────┬────────┘                         │
└──────────────────────────┼──────────────────────────────────┘
                           │ capability tokens, task contracts
┌──────────────────────────┼──────────────────────────────────┐
│              Device / Execution Plane                        │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ daemon-core │  │ daemon-flash │  │ daemon-images      │  │
│  │ (lifecycle, │  │ (backends,   │  │ (manifests,        │  │
│  │  evidence)  │  │  dry-run)    │  │  compatibility)    │  │
│  └─────────────┘  └──────────────┘  └────────────────────┘  │
│                                                              │
│  Simulated backend (this milestone) | Future real backends   │
└──────────────────────────────────────────────────────────────┘
```

Control plane and trusted local execution are deliberately separated. The public API never exposes an unrestricted remote shell.

## Execution lifecycle

1. **Submit** — Client presents a `TaskSpec` + capability token. Idempotency key deduplicates.
2. **Accept** — Control plane validates auth and capability; transitions `pending → accepted`.
3. **Assign** — A healthy enrolled node is selected (or explicitly targeted).
4. **Run** — Backend executes; produces `TaskResult` + `ExecutionEvidence`.
5. **Complete** — Terminal state (`succeeded` / `failed` / `cancelled` / `timed_out`).
6. **Verify** — `result.verified` is true only when an independent verification method succeeded. Command success alone is never treated as verified outcome.

Invalid transitions raise `InvalidTransitionError`.

## Ownership vs related repos

| Concern | Owner |
|---------|--------|
| Multi-arm head, 42-node topology, Aurora bridge | Octopie |
| Sensing / field / MetaField | Aurora / metafield-engine / throne-room |
| Execution contracts, provisioning, fleet OS | **DaemonOS** |

DaemonOS does not import or fork those repositories. Future adapters may translate contracts without merging codebases.
