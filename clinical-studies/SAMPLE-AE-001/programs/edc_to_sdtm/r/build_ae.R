# PROGRAM: SDTM AE R artifact
# PURPOSE: Apply the approved metadata-driven AE MappingSpec
# MAPPING SPEC ID: ae-mapping-spec-sample-ae-001-v1
# MAPPING SPEC SHA256: f9ede6b72fccf835d6ca9a0e1f35d4696b3e7e6587e31ee15e9c604f4ebb0ba6
# SOURCE SHA256: 2a6d72e9e5fa4bb8e3cc14b0c412fce3c37e519f3ab9105cdcff33ba031e8749
# TARGET STANDARD: SDTMIG 3.4
# AI GENERATED: YES - HUMAN APPROVAL: RECORDED IN MAPPINGSPEC
# ARBITRARY COMMANDS: NOT ALLOWED

# Review artifact. R execution is outside the P9 reference-result boundary.
library(haven)
library(dplyr)

p9_partial_date_iso <- function(x) {
  # Production implementation must preserve partial dates and is subject to R-side QC.
  trimws(as.character(x))
}

raw <- read_sas("input/edc/ae09jun2025.sas7bdat")
ae <- raw %>%
  group_by(Subject) %>%
  arrange(RecordPosition, .by_group = TRUE) %>%
  mutate(
    STUDYID = "SAMPLE-AE-001",
    DOMAIN = "AE",
    USUBJID = paste0("SAMPLE-AE-001-", trimws(as.character(Subject))),
    AESEQ = row_number(),
    AETERM = trimws(as.character(AETERM)),
    AESTDTC = p9_partial_date_iso(AESTDAT),
    AEENDTC = p9_partial_date_iso(AEENDAT),
    AEDECOD = trimws(as.character(AETERM_PT)),
    AEBODSYS = trimws(as.character(AETERM_SOC)),
    AESOC = trimws(as.character(AETERM_SOC))
  ) %>%
  ungroup() %>%
  select(STUDYID, DOMAIN, USUBJID, AESEQ, AETERM, AESTDTC, AEENDTC, AEDECOD, AEBODSYS, AESOC)
