# EDC to SDTM program chain

Reserved language lanes:

- `python/` — current POC executable reference/test lane.
- `r/` — R primary or independent QC lane.
- `sas/` — production target lane; generate-only until SAS execution is configured.

Each executed lane must later produce input hashes, program hash, execution log, validation report, output hash, provenance, and traceability.
