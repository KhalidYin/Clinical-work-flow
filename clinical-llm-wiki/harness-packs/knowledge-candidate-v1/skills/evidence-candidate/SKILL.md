---
name: evidence-candidate
description: Create one traceable draft Candidate from authorized Evidence.
---

# Evidence Candidate

Read `references/evidence-policy.md` completely before producing output.

1. Call only the Attempt-scoped `read_evidence` tool for source content.
2. Produce one draft Candidate matching the provided output schema.
3. Put every supporting Evidence ID in `evidence_ids`.
4. Represent uncertainty in `confidence`, conditions, exceptions, or advisory
   signals. Do not invent missing facts.
5. Do not approve, publish, release, retry, or choose another workflow Step.
