# Study Template

Copy this directory to the controlled Study container and rename it to the
actual Study ID.  The copied Study is its own filesystem state and is normally
its own Git repository.  Do not run work directly from this template.

## Responsibilities

- `project.yaml` holds Study facts, review assignments and configured
  input/output/review/audit paths.
- `runtime-manifest.yaml` is the immutable execution lock for the Engine
  contract, Workflow/Domain Wiki snapshots and toolchain.
- `workflow/` holds current-Study workflow decisions; `knowledge/` holds
  current-Study domain decisions.  Neither directory is a general Wiki.
- `.review_queue/` and `audit_trail.jsonl` are local to this Study.  They use
  the shared Engine Review Protocol but are never shared with the Wiki queue.

The runtime receives a Knowledge Service endpoint by explicit configuration.
It must not locate a sibling Wiki directory from the Study path.  When the
service is unavailable, it may only use the exact snapshot paths locked by the
manifest; otherwise it must fail closed.

## Directory contract

```text
{STUDY-ID}/
├── project.yaml
├── runtime-manifest.yaml
├── workflow/
│   ├── overrides/             # proposed/current workflow-specific adjustments
│   ├── decisions/             # approved DecisionReceipt-backed workflow rules
│   ├── snapshots/             # manifest-locked workflow context snapshots
│   └── promotion_candidates/  # de-identified candidates; never auto-promoted
├── knowledge/                 # same four directories for domain knowledge
├── input/{protocol,sap,edc,external}/
├── output/{protocol,sap,sdtm,adam,tfl,qc,submission}/
├── .review_queue/
└── audit_trail.jsonl
```

`workflow/decisions/` and `knowledge/decisions/` hold only current Study rules
with review evidence.  An override or prior-Study reference is not executable
until the Runtime resolves it into the P2 `ExecutionContext` and validates the
Engine Action Policy.  Promotion candidates remain local until they are
de-identified, proposed to the Wiki, and separately approved there.

## Initialisation

1. Replace the illustrative values in `project.yaml` and
   `runtime-manifest.yaml` with the actual Study ID and published hashes.
2. Write the two approved-only Wiki snapshots into the exact manifest fallback
   locations and verify their hashes before first execution.
3. Configure the Wiki service endpoint outside this repository (for example,
   through the Engine runtime configuration).
4. Commit the initial manifest, then record every execution, review receipt,
   fallback and promotion proposal in the Study audit trail.

The placeholder snapshots exist only to make the scaffold path-complete.  They
are not valid production knowledge and must never be used for an execution.
