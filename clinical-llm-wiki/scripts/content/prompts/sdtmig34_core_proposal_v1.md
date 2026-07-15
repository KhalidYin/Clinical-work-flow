# SDTMIG 3.4 Core Knowledge Proposal Prompt v1

You are extracting governed atomic knowledge proposals from a small Core
calibration batch of SDTMIG 3.4 source units. Use only the supplied source units
and locator metadata.

## Output Contract

Return JSON only. The caller will inject evidence objects, statement IDs,
coverage ledger entries, source hashes, and review status. Do not invent source
unit IDs or locator IDs.

Each proposal must contain:

- `proposal_key`: stable kebab-case semantic key.
- `source_unit_ids`: one or more supplied candidate source unit IDs.
- `knowledge_type`: one of definition, requirement, permission, prohibition,
  assumption, exception, example, variable_rule, cross_reference.
- `subject`: the specific SDTM concept, domain, dataset, variable, or rule.
- `statement`: one atomic paraphrased statement.
- `modality`: one of must, should, may, must_not, descriptive, not_applicable.
- `scope`: model, implementation_guide, domains, variables.
- `conditions`: explicit conditions required by the source.
- `exceptions`: explicit exceptions required by the source.
- `relations`: typed relation proposals using supplied source unit IDs.

## Extraction Rules

1. Preserve the distinction between definitions, conformance requirements,
   variable rules, cross-references, and explanatory context.
2. Do not promote introductory lead-in text or table-layout context into an
   atomic knowledge statement.
3. Do not use SDTM v2.0, controlled terminology, FDA guidance, or organization
   practice to fill gaps in SDTMIG 3.4.
4. A proposal may cite multiple source units when one sentence continues across
   PDF text blocks or when a rule requires a context sentence plus a formula.
5. Keep statement text as a concise paraphrase. Structural fields must remain
   exact and machine-verifiable.
