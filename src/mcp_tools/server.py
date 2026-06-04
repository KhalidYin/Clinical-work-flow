"""
MCP Server for Clinical Statistical Programming Tools.

Provides structured tools for:
  - EDC data import and validation
  - SDTM specification generation
  - ADaM specification generation
  - TFL shell catalog
  - CDISC validation
  - define.xml generation
  - P21 finding triage

These tools are designed to be called by AI agents (Executors + Reviewer)
as part of the clinical workflow pipeline.
"""

import json
import sys
from typing import Any


# Import tools
from .edc_importer import (
    import_edc_data, validate_edc_import, generate_import_report,
    EDCManifest, ImportResult, STANDARD_MANIFEST,
)
from .sdtm_spec_builder import STANDARD_DOMAINS, generate_sdtm_spec, CRF2SDTMMapping
from .adam_spec_builder import generate_adam_spec
from .tfl_renderer import get_tfl_shells, STANDARD_TFL_SHELLS, ONCOLOGY_TFL_SHELLS, TFLType, OutputFormat
from .cdisc_validator import (
    validate_sdtm, validate_adam, triage_pinnacle21_findings,
    generate_define_xml_metadata, CDISC_RULES,
)
from .ctgov_fetcher import (
    search_ctgov, get_study_details, download_study_documents,
    check_document_availability, CTGovClient, CTGovDocument, CTGovStudy,
)


# ── MCP Tool Definitions ────────────────────────────────────────


TOOLS = [
    {
        "name": "edc_import",
        "description": "Import and validate EDC data from CSV/SAS7BDAT/XPT files.",
        "parameters": {
            "manifest_path": "Path to EDC manifest file (YAML/JSON), or 'default' for standard",
            "validate_only": "If true, only validate without importing",
        },
    },
    {
        "name": "sdtm_spec_build",
        "description": "Generate SDTM domain specification from CRF annotations.",
        "parameters": {
            "domain_code": "2-character SDTM domain code (DM, AE, CM, LB, VS, EX, DS, etc.)",
            "crf_mappings": "List of CRF field to SDTM variable mappings",
        },
    },
    {
        "name": "adam_spec_build",
        "description": "Generate ADaM dataset specification from SAP and SDTM.",
        "parameters": {
            "dataset_name": "ADaM dataset name (ADSL, ADAE, ADTTE, ADLB, etc.)",
            "trial_phase": "phase_i | phase_ii | phase_iii",
            "therapeutic_area": "oncology | non_oncology",
        },
    },
    {
        "name": "tfl_shells_list",
        "description": "Get the standard TFL shell catalog for a trial configuration.",
        "parameters": {
            "trial_phase": "phase_i | phase_ii | phase_iii",
            "therapeutic_area": "oncology | non_oncology",
        },
    },
    {
        "name": "cdisc_validate",
        "description": "Run CDISC compliance validation on SDTM or ADaM data.",
        "parameters": {
            "type": "sdtm | adam",
            "domain_or_dataset": "Domain code (SDTM) or dataset name (ADaM)",
            "data": "Dataset metadata or data sample",
        },
    },
    {
        "name": "define_xml_build",
        "description": "Generate define.xml metadata for a dataset.",
        "parameters": {
            "dataset_name": "SDTM domain or ADaM dataset name",
            "variables": "List of variable metadata dicts",
        },
    },
    {
        "name": "triage_p21",
        "description": "AI-powered triage of Pinnacle 21 validation findings.",
        "parameters": {
            "findings": "List of P21 validation findings",
        },
    },
    {
        "name": "ctgov_search",
        "description": "Search ClinicalTrials.gov for clinical trials by condition/phase/status.",
        "parameters": {
            "condition": "Disease/condition (e.g. 'Non-Small Cell Lung Cancer')",
            "phase": "Trial phase (e.g. 'Phase 3')",
            "status": "Overall status (e.g. 'RECRUITING', 'COMPLETED')",
            "term": "Free-text search query",
            "page_size": "Results per page (default 20, max 1000)",
            "max_pages": "Max pages to fetch (default 5)",
        },
    },
    {
        "name": "ctgov_study_detail",
        "description": "Get full details of a single clinical trial, including downloadable documents (Protocol, SAP, ICF).",
        "parameters": {
            "nct_id": "NCT identifier (e.g. 'NCT04205812')",
        },
    },
    {
        "name": "ctgov_download_docs",
        "description": "Download study documents (Protocol, SAP, ICF) from ClinicalTrials.gov to local storage.",
        "parameters": {
            "nct_id": "NCT identifier",
            "doc_types": "Optional list of doc types to download: ['PROTOCOL', 'SAP', 'ICF']. None = all.",
            "output_dir": "Optional output directory. Default: downloads/ctgov/{NCT_ID}/",
        },
    },
    {
        "name": "ctgov_check_docs",
        "description": "Batch check which NCT studies have downloadable Protocol/SAP documents.",
        "parameters": {
            "nct_ids": "List of NCT identifiers to check",
        },
    },
]


# ── Tool handlers ────────────────────────────────────────────────


def handle_tool_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Route tool calls to the correct handler."""
    handlers = {
        "sdtm_spec_build": _handle_sdtm_spec_build,
        "adam_spec_build": _handle_adam_spec_build,
        "tfl_shells_list": _handle_tfl_shells_list,
        "cdisc_validate": _handle_cdisc_validate,
        "define_xml_build": _handle_define_xml_build,
        "triage_p21": _handle_triage_p21,
        "ctgov_search": _handle_ctgov_search,
        "ctgov_study_detail": _handle_ctgov_study_detail,
        "ctgov_download_docs": _handle_ctgov_download_docs,
        "ctgov_check_docs": _handle_ctgov_check_docs,
    }
    handler = handlers.get(tool_name)
    if handler is None:
        raise ValueError(f"Unknown tool: {tool_name}. Available: {list(handlers)}")
    return handler(arguments)


def _handle_sdtm_spec_build(args: dict) -> dict:
    mappings = args.get("crf_mappings", [])
    crf_objects = [CRF2SDTMMapping(**m) for m in mappings]
    return generate_sdtm_spec(args["domain_code"], crf_objects)


def _handle_adam_spec_build(args: dict) -> dict:
    return generate_adam_spec(
        args["dataset_name"],
        args.get("trial_phase", "phase_iii"),
        args.get("therapeutic_area", "non_oncology"),
    )


def _handle_tfl_shells_list(args: dict) -> dict:
    shells = get_tfl_shells(
        args.get("trial_phase", "phase_iii"),
        args.get("therapeutic_area", "non_oncology"),
    )
    return {
        "total_tfls": len(shells),
        "tables": sum(1 for s in shells if s.tfl_type == TFLType.TABLE),
        "figures": sum(1 for s in shells if s.tfl_type == TFLType.FIGURE),
        "listings": sum(1 for s in shells if s.tfl_type == TFLType.LISTING),
        "shells": [
            {
                "id": s.tfl_id,
                "type": s.tfl_type.value,
                "title": s.title,
                "population": s.population,
                "source": s.source_dataset,
                "method": s.analysis_method,
            }
            for s in shells
        ],
    }


def _handle_cdisc_validate(args: dict) -> dict:
    if args["type"] == "sdtm":
        findings = validate_sdtm(args["domain_or_dataset"], args.get("data"))
    else:
        findings = validate_adam(args["domain_or_dataset"], args.get("data"))
    return triage_pinnacle21_findings(findings)


def _handle_define_xml_build(args: dict) -> dict:
    return generate_define_xml_metadata(args["dataset_name"], args["variables"])


def _handle_triage_p21(args: dict) -> dict:
    return triage_pinnacle21_findings(args["findings"])


def _handle_ctgov_search(args: dict) -> dict:
    return search_ctgov(
        condition=args.get("condition"),
        phase=args.get("phase"),
        status=args.get("status"),
        term=args.get("term"),
        page_size=args.get("page_size", 20),
        max_pages=args.get("max_pages", 5),
    )


def _handle_ctgov_study_detail(args: dict) -> dict:
    return get_study_details(args["nct_id"])


def _handle_ctgov_download_docs(args: dict) -> dict:
    return download_study_documents(
        nct_id=args["nct_id"],
        doc_types=args.get("doc_types"),
        output_dir=args.get("output_dir"),
    )


def _handle_ctgov_check_docs(args: dict) -> dict:
    results = check_document_availability(args["nct_ids"])
    return {"checked": len(results), "results": results}


# ── MCP Server entry point ───────────────────────────────────────


def main():
    """MCP server stdio entry point."""
    import asyncio

    async def run():
        for line in sys.stdin:
            request = json.loads(line)
            try:
                result = handle_tool_call(request["name"], request.get("arguments", {}))
                response = {"id": request.get("id"), "result": result}
            except Exception as e:
                response = {"id": request.get("id"), "error": str(e)}
            print(json.dumps(response), flush=True)

    asyncio.run(run())


if __name__ == "__main__":
    main()
