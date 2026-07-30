# P12 P2-A Parser Selection Gate

Date: 2026-07-30
Scope: deterministic Source → derived artifact → Evidence only

## Decision

Do **not** lock Docling or Unstructured as a product dependency in P2-A.

The current adapter set (`PyMuPDF`, `python-docx`, `openpyxl`, and the
Markdown/text parser) passes the P2-A synthetic contract for stable locators,
source/parser provenance, formula preservation, derived hashes, conditional DAG
fan-in, and fail-closed scanned PDF handling. Docling was not installed or
measured against the same controlled clinical fixtures, so there is no evidence
that it improves locator, table, or formula fidelity enough to justify adding it
to the locked runtime.

This is a fail-closed selection decision, not a claim that the current adapters
cover production clinical documents.

## Measured P2-A Baseline

The benchmark used in-memory synthetic fixtures and ten parses per case on the
local development machine. Times and peak allocations are directional only;
they are not production capacity targets.

| Adapter path | Fixture bytes | Mean time | Peak allocation | Output |
|---|---:|---:|---:|---:|
| Markdown | 27 | 0.08 ms | 4.4 KiB | 1 fragment |
| PDF text | 852 | 2.97 ms | 142.9 KiB | 1 fragment |
| DOCX text | 587 | 0.80 ms | 143.1 KiB | 3 fragments |
| DOCX table | 587 | 0.52 ms | 78.1 KiB | 1 fragment |
| XLSX table/formula | 4,902 | 13.24 ms | 1,325.8 KiB | 1 fragment |

Contract and integration tests additionally prove:

- every Evidence record carries source version/hash, parser profile/version,
  locator, and derived object hash;
- XLSX formulas are preserved as formula text rather than silently replaced by
  cached values;
- a PDF with no extractable text fails with an explicit OCR-required result;
- parser branches declare dependencies and create Evidence only after fan-in;
- retry reuses committed derived artifacts and does not create duplicate
  Evidence or candidate/release objects.

## Gaps

- No licensed SDTM IG multi-column/cross-page fixture was available in this
  slice.
- No controlled ADaM mathematical-layout fixture was compared across engines.
- OCR, images, attachments, and cloud connectors are outside P2-A.
- Complex merged-cell, footnote, reading-order, and cross-page table fidelity
  are not established by the synthetic fixtures.
- Docling and Unstructured have no comparable measurements in this report.

## Reopen Criteria

Reopen the parser dependency decision only when a legally usable fixture pack
contains all of the following:

1. a multi-column and cross-page SDTM-style table with expected page/cell
   locators;
2. an ADaM-style formula sample with expected symbols and reading order;
3. a Controlled Terminology workbook with merged cells, formulas, footnotes,
   and expected sheet/range locators;
4. a scanned PDF with an explicit OCR quality baseline;
5. expected-output manifests that permit the same fidelity, latency, memory,
   package-size, and failure-mode comparison for every adapter.

Docling may be selected only if that comparison shows a material fidelity
benefit with acceptable resource and deployment cost. Unstructured remains a
format-specific fallback candidate, not a canonical knowledge model.
