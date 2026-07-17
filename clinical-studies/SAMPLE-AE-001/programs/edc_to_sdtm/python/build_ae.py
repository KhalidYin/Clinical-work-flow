# PROGRAM: SDTM AE PYTHON artifact
# PURPOSE: Apply the approved metadata-driven AE MappingSpec
# MAPPING SPEC ID: ae-mapping-spec-sample-ae-001-v1
# MAPPING SPEC SHA256: f9ede6b72fccf835d6ca9a0e1f35d4696b3e7e6587e31ee15e9c604f4ebb0ba6
# SOURCE SHA256: 2a6d72e9e5fa4bb8e3cc14b0c412fce3c37e519f3ab9105cdcff33ba031e8749
# TARGET STANDARD: SDTMIG 3.4
# AI GENERATED: YES - HUMAN APPROVAL: RECORDED IN MAPPINGSPEC
# ARBITRARY COMMANDS: NOT ALLOWED

"""Transparent launcher; execution is routed through the registered P9 adapter."""
from pathlib import Path
from src.codegen.ae_programs import run_python_reference

if __name__ == "__main__":
    # Study root is explicit; no command or script path is accepted by the adapter.
    run_python_reference(Path(__file__).resolve().parents[4])

# Mapping target order: ['STUDYID', 'DOMAIN', 'USUBJID', 'AESEQ', 'AETERM', 'AESTDTC', 'AEENDTC', 'AEDECOD', 'AEBODSYS', 'AESOC']
