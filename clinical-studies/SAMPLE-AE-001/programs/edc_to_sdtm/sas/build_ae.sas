/* PROGRAM: SDTM AE SAS artifact */
/* PURPOSE: Apply the approved metadata-driven AE MappingSpec */
/* MAPPING SPEC ID: ae-mapping-spec-sample-ae-001-v1 */
/* MAPPING SPEC SHA256: f9ede6b72fccf835d6ca9a0e1f35d4696b3e7e6587e31ee15e9c604f4ebb0ba6 */
/* SOURCE SHA256: 2a6d72e9e5fa4bb8e3cc14b0c412fce3c37e519f3ab9105cdcff33ba031e8749 */
/* TARGET STANDARD: SDTMIG 3.4 */
/* AI GENERATED: YES - HUMAN APPROVAL: RECORDED IN MAPPINGSPEC */
/* ARBITRARY COMMANDS: NOT ALLOWED */

/* Review artifact only. SAS runtime is not configured in this POC. */
libname raw "<REGISTERED_STUDY_INPUT_LIBRARY>";
libname out "<REGISTERED_STUDY_OUTPUT_LIBRARY>";

proc sort data=raw.ae_source out=work.ae_source;
  by Subject RecordPosition;
run;

data out.ae;
  set work.ae_source;
  by Subject RecordPosition;
  length STUDYID DOMAIN USUBJID $200 AETERM $1000;
  STUDYID = "SAMPLE-AE-001";
  DOMAIN = "AE";
  USUBJID = cats("SAMPLE-AE-001-", strip(vvalue(Subject)));
  if first.Subject then AESEQ=1; else AESEQ+1;
  AETERM = strip(vvalue(AETERM));
  AESTDTC = strip(vvalue(AESTDAT)); /* partial-date normalization pending SAS QC */
  AEENDTC = strip(vvalue(AEENDAT)); /* partial-date normalization pending SAS QC */
  AEDECOD = strip(vvalue(AETERM_PT));
  AEBODSYS = strip(vvalue(AETERM_SOC));
  AESOC = strip(vvalue(AETERM_SOC));
  keep STUDYID DOMAIN USUBJID AESEQ AETERM AESTDTC AEENDTC AEDECOD AEBODSYS AESOC;
run;
