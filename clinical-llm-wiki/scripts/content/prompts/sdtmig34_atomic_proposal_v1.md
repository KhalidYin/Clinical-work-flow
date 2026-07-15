# SDTMIG 3.4 Atomic Knowledge Proposal Prompt v1

You are extracting governed atomic knowledge proposals from SDTMIG 3.4 source
units. Use only the supplied source units and locator metadata.

## Output Contract

Return JSON only. The caller will inject evidence objects, statement IDs,
coverage ledger entries, and source hashes. Do not invent locator IDs.

Each proposal must contain:

- `proposal_key`: stable kebab-case semantic key.
- `source_unit_ids`: one or more supplied source unit IDs.
- `knowledge_type`: one of definition, requirement, permission, prohibition,
  assumption, exception, example, variable_rule, cross_reference.
- `subject`: the specific concept, domain, dataset, variable, or erratum.
- `statement`: one atomic paraphrased statement.
- `modality`: one of must, should, may, must_not, descriptive, not_applicable.
- `scope`: model, implementation_guide, domains, variables.
- `conditions`: explicit conditions required by the source.
- `exceptions`: explicit exceptions required by the source.
- `relations`: typed relation proposals using supplied source unit IDs.

## Extraction Rules

1. Preserve the distinction between normative rules, definitions, examples,
   cross-references, and errata.
2. Do not promote examples into universal requirements.
3. Do not use SDTM v2.0, controlled terminology, FDA guidance, or organization
   practice to fill gaps in SDTMIG 3.4.
4. A proposal may cite multiple source units when the semantic claim requires
   both PDF narrative and XLSX metadata.
5. Keep statement text as a concise paraphrase. Structural fields must remain
   exact and machine-verifiable.
