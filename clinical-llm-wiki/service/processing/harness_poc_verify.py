"""Verify the P15 Candidate through the authenticated Knowledge API."""

from __future__ import annotations

from http.cookiejar import CookieJar
import json
import os
from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from sqlalchemy import select

from service.db.models import (
    CandidateEvidence,
    JobStep,
    KnowledgeCandidate,
    ModelInvocation,
    ProcessingRun,
    SourceVersion,
    StepAttempt,
)
from service.db.session import (
    create_database_engine,
    create_session_factory,
    database_url_from_environment,
)
from service.demo_runtime import DEMO_SOURCE_ID

from .enrichment import ENRICHMENT_STEP_KEY


def validate_api_candidate(
    *,
    summary: Mapping[str, Any],
    detail: Mapping[str, Any],
) -> dict[str, str]:
    if (
        summary.get("status") != "author_confirmation_required"
        or detail.get("status") != "author_confirmation_required"
    ):
        raise RuntimeError("P15 Candidate must stop at author confirmation")
    candidate_id = summary.get("candidateId")
    invocation_id = detail.get("originModelInvocationId")
    evidence = detail.get("evidence")
    if (
        not isinstance(candidate_id, str)
        or detail.get("candidateId") != candidate_id
        or summary.get("candidateGroupId") != "candidate-poc-001"
        or summary.get("evidenceCount") != 1
        or not isinstance(invocation_id, str)
        or not isinstance(evidence, list)
        or len(evidence) != 1
        or not isinstance(evidence[0], dict)
        or not isinstance(evidence[0].get("evidenceId"), str)
    ):
        raise RuntimeError("P15 Candidate API lineage is invalid")
    return {
        "candidate_id": candidate_id,
        "evidence_id": evidence[0]["evidenceId"],
        "origin_model_invocation_id": invocation_id,
        "status": "author_confirmation_required",
    }


def _require_mapping(value: object, message: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(message)
    return value


def validate_loop_snapshot(
    *,
    snapshot: Mapping[str, Any],
    api_candidate: Mapping[str, str],
    expected_pack_sha256: str,
) -> dict[str, object]:
    """Validate one canonical POC result without creating another authority."""

    counts = _require_mapping(snapshot.get("counts"), "P15 counts are unavailable")
    if counts.get("attempts") != 1:
        raise RuntimeError("P15 loop requires exactly one enrichment attempt")
    if counts.get("model_invocations") != 1:
        raise RuntimeError("P15 loop requires exactly one model invocation")
    if counts.get("candidates") != 1:
        raise RuntimeError("P15 loop requires exactly one Candidate")
    if counts.get("candidate_evidence") != 1:
        raise RuntimeError("P15 loop requires exactly one Candidate Evidence link")

    required_statuses = {
        "run_status": "author_confirmation_required",
        "step_status": "succeeded",
        "attempt_status": "succeeded",
        "invocation_status": "succeeded",
        "candidate_status": "author_confirmation_required",
    }
    if any(snapshot.get(key) != value for key, value in required_statuses.items()):
        raise RuntimeError("P15 loop canonical statuses are invalid")

    candidate_id = snapshot.get("candidate_id")
    invocation_id = snapshot.get("invocation_id")
    evidence_ids = snapshot.get("evidence_ids")
    if (
        not isinstance(candidate_id, str)
        or not isinstance(invocation_id, str)
        or not isinstance(evidence_ids, list)
        or len(evidence_ids) != 1
        or not isinstance(evidence_ids[0], str)
        or snapshot.get("candidate_origin_model_invocation_id") != invocation_id
        or api_candidate.get("candidate_id") != candidate_id
        or api_candidate.get("origin_model_invocation_id") != invocation_id
        or api_candidate.get("evidence_id") != evidence_ids[0]
    ):
        raise RuntimeError("P15 loop API and PostgreSQL lineage differ")

    execution = _require_mapping(
        snapshot.get("execution_receipt"),
        "P15 ExecutionReceipt is unavailable",
    )
    validation = _require_mapping(
        snapshot.get("validation_receipt"),
        "P15 ValidationReceipt is unavailable",
    )
    pack = _require_mapping(execution.get("pack_identity"), "P15 Pack identity is invalid")
    if (
        pack.get("pack_id") != "knowledge-candidate-v1"
        or pack.get("version") != "1.0.0"
        or pack.get("sha256") != expected_pack_sha256
    ):
        raise RuntimeError("P15 Pack identity does not match the checked-in Pack")
    if execution.get("advertised_skills") != ["evidence-candidate"]:
        raise RuntimeError("P15 ExecutionReceipt does not prove the Pack Skill")
    if execution.get("allowed_mcp_capabilities") != ["knowledge.read-evidence"]:
        raise RuntimeError("P15 ExecutionReceipt does not prove the MCP capability")
    tool_summary = execution.get("tool_call_summary")
    if not isinstance(tool_summary, list) or not any(
        isinstance(item, Mapping)
        and item.get("tool") == "read_evidence"
        and item.get("calls") == 1
        for item in tool_summary
    ):
        raise RuntimeError("P15 ExecutionReceipt does not prove one read_evidence call")
    network = _require_mapping(
        execution.get("network_policy"),
        "P15 ExecutionReceipt network policy is unavailable",
    )
    if (
        network.get("policy_id") != "none"
        or network.get("kind") != "none"
        or network.get("allowed_endpoints") not in ([], ())
    ):
        raise RuntimeError("P15 loop must use the none network policy")
    if (
        execution.get("status") != "succeeded"
        or execution.get("exit_classification") != "succeeded"
        or execution.get("retryable") is not False
        or execution.get("execution_id") != snapshot.get("provider_request_id")
        or validation.get("result") != "passed"
    ):
        raise RuntimeError("P15 execution or validation Receipt is invalid")

    return {
        "attempt_id": snapshot["attempt_id"],
        "candidate_id": candidate_id,
        "evidence_id": evidence_ids[0],
        "model_invocation_id": invocation_id,
        "run_id": snapshot["run_id"],
        "status": "author_confirmation_required",
        "counts": dict(counts),
        "receipt": {
            "network_policy_id": "none",
            "pack_sha256": expected_pack_sha256,
            "skill": "evidence-candidate",
            "mcp_tool": "read_evidence",
            "validation": "passed",
        },
    }


def validate_failure_snapshot(
    *,
    snapshot: Mapping[str, Any],
    expected_scenario: str,
    expected_pack_sha256: str,
) -> dict[str, object]:
    """Validate a terminal failure without treating the verifier as state authority."""

    expected_error_types = {
        "schema_invalid": "structured_output_invalid",
        "timeout": "timeout",
    }
    error_type = expected_error_types.get(expected_scenario)
    if error_type is None:
        raise ValueError("unsupported P15 failure scenario")
    counts = _require_mapping(snapshot.get("counts"), "P15 counts are unavailable")
    if counts.get("attempts") != 1 or counts.get("model_invocations") != 1:
        raise RuntimeError("P15 failure requires one Attempt and ModelInvocation")
    if counts.get("candidates") != 0 or counts.get("candidate_evidence") != 0:
        raise RuntimeError("P15 failure requires zero Candidate and Evidence links")
    if any(
        snapshot.get(key) != "failed"
        for key in (
            "run_status",
            "step_status",
            "attempt_status",
            "invocation_status",
        )
    ):
        raise RuntimeError("P15 failure canonical statuses are invalid")
    if (
        snapshot.get("attempt_error_type") != error_type
        or snapshot.get("invocation_error_type") != error_type
    ):
        raise RuntimeError("P15 failure classification is invalid")

    execution = _require_mapping(
        snapshot.get("execution_receipt"),
        "P15 failure ExecutionReceipt is unavailable",
    )
    pack = _require_mapping(execution.get("pack_identity"), "P15 Pack identity is invalid")
    if (
        pack.get("pack_id") != "knowledge-candidate-v1"
        or pack.get("version") != "1.0.0"
        or pack.get("sha256") != expected_pack_sha256
        or execution.get("advertised_skills") != ["evidence-candidate"]
        or execution.get("allowed_mcp_capabilities") != ["knowledge.read-evidence"]
    ):
        raise RuntimeError("P15 failure Pack capability identity is invalid")
    network = _require_mapping(
        execution.get("network_policy"),
        "P15 failure network policy is unavailable",
    )
    if (
        network.get("policy_id") != "none"
        or network.get("kind") != "none"
        or network.get("allowed_endpoints") not in ([], ())
    ):
        raise RuntimeError("P15 failure must use the none network policy")
    if (
        execution.get("execution_id") != snapshot.get("provider_request_id")
        or execution.get("retryable") is not False
    ):
        raise RuntimeError("P15 failure Receipt identity or retry policy is invalid")

    validation = snapshot.get("validation_receipt")
    if expected_scenario == "schema_invalid":
        tool_summary = execution.get("tool_call_summary")
        if (
            execution.get("status") != "succeeded"
            or execution.get("exit_classification") != "succeeded"
            or not isinstance(tool_summary, list)
            or not any(
                isinstance(item, Mapping)
                and item.get("tool") == "read_evidence"
                and item.get("calls") == 1
                for item in tool_summary
            )
        ):
            raise RuntimeError("P15 schema failure did not preserve Harness capability evidence")
        validation_mapping = _require_mapping(
            validation,
            "P15 schema failure ValidationReceipt is unavailable",
        )
        if (
            validation_mapping.get("result") != "failed"
            or validation_mapping.get("findings") != ["structured_output_invalid"]
        ):
            raise RuntimeError("P15 schema failure ValidationReceipt is invalid")
    elif (
        execution.get("status") != "timed_out"
        or execution.get("exit_classification") != "timed_out"
        or validation is not None
    ):
        raise RuntimeError("P15 timeout Receipt is invalid")

    return {
        "scenario": expected_scenario,
        "run_id": snapshot["run_id"],
        "attempt_id": snapshot["attempt_id"],
        "model_invocation_id": snapshot["invocation_id"],
        "error_type": error_type,
        "candidate_count": 0,
        "retryable": False,
        "receipt": {
            "execution_status": execution["status"],
            "network_policy_id": "none",
            "pack_sha256": expected_pack_sha256,
            "validation": (
                validation.get("result") if isinstance(validation, Mapping) else None
            ),
        },
    }


def read_p15_database_snapshot() -> dict[str, object]:
    engine = create_database_engine(database_url_from_environment())
    sessions = create_session_factory(engine)
    try:
        with sessions() as session:
            run = session.scalar(
                select(ProcessingRun)
                .join(
                    SourceVersion,
                    SourceVersion.source_version_id == ProcessingRun.source_version_id,
                )
                .where(SourceVersion.source_id == DEMO_SOURCE_ID)
                .order_by(ProcessingRun.created_at.desc())
                .limit(1)
            )
            if run is None:
                raise RuntimeError("P15 canonical demo run is unavailable")
            step = session.scalar(
                select(JobStep).where(
                    JobStep.run_id == run.run_id,
                    JobStep.step_key == ENRICHMENT_STEP_KEY,
                )
            )
            if step is None:
                raise RuntimeError("P15 enrichment step is unavailable")
            attempts = tuple(
                session.scalars(
                    select(StepAttempt)
                    .where(StepAttempt.step_id == step.step_id)
                    .order_by(StepAttempt.attempt_number)
                )
            )
            invocations = tuple(
                session.scalars(
                    select(ModelInvocation)
                    .where(ModelInvocation.run_id == run.run_id)
                    .order_by(ModelInvocation.created_at)
                )
            )
            candidates = tuple(
                session.scalars(
                    select(KnowledgeCandidate)
                    .where(KnowledgeCandidate.run_id == run.run_id)
                    .order_by(KnowledgeCandidate.created_at)
                )
            )
            candidate_ids = [item.candidate_id for item in candidates]
            evidence_links = (
                tuple(
                    session.scalars(
                        select(CandidateEvidence).where(
                            CandidateEvidence.candidate_id.in_(candidate_ids)
                        )
                    )
                )
                if candidate_ids
                else ()
            )
            attempt = attempts[0] if len(attempts) == 1 else None
            invocation = invocations[0] if len(invocations) == 1 else None
            candidate = candidates[0] if len(candidates) == 1 else None
            return {
                "run_id": run.run_id,
                "run_status": run.status,
                "step_status": step.status,
                "attempt_id": attempt.attempt_id if attempt is not None else None,
                "attempt_status": attempt.status if attempt is not None else None,
                "attempt_error_type": (
                    attempt.error_type if attempt is not None else None
                ),
                "invocation_id": (
                    invocation.invocation_id if invocation is not None else None
                ),
                "invocation_status": invocation.status if invocation is not None else None,
                "invocation_error_type": (
                    invocation.error_type if invocation is not None else None
                ),
                "provider_request_id": (
                    invocation.provider_request_id if invocation is not None else None
                ),
                "candidate_id": candidate.candidate_id if candidate is not None else None,
                "candidate_status": candidate.status if candidate is not None else None,
                "candidate_origin_model_invocation_id": (
                    candidate.origin_model_invocation_id if candidate is not None else None
                ),
                "evidence_ids": [item.evidence_id for item in evidence_links],
                "counts": {
                    "attempts": len(attempts),
                    "model_invocations": len(invocations),
                    "candidates": len(candidates),
                    "candidate_evidence": len(evidence_links),
                },
                "execution_receipt": (
                    invocation.execution_receipt if invocation is not None else None
                ),
                "validation_receipt": (
                    invocation.validation_receipt if invocation is not None else None
                ),
            }
    finally:
        engine.dispose()


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _json_request(
    opener: Any,
    *,
    url: str,
    method: str = "GET",
    payload: Mapping[str, str] | None = None,
    origin: str,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json", "Origin": origin}
    if body is not None:
        headers.update(
            {
                "Content-Type": "application/json",
                "X-CSRF-Protection": "1",
            }
        )
    request = Request(url, data=body, headers=headers, method=method)
    with opener.open(request, timeout=10) as response:
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise RuntimeError("P15 API returned a non-object response")
    return decoded


def _authenticated_api_context() -> tuple[Any, str, str, list[dict[str, Any]]]:
    origin = os.environ.get("KNOWLEDGE_P15_API_ORIGIN", "http://p15-api:8788")
    prefix = f"{origin}/api/prerelease/v1"
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    username = _required("KNOWLEDGE_ADMIN_USERNAME")
    initial_password = _required("KNOWLEDGE_ADMIN_PASSWORD")
    verifier_password = _required("KNOWLEDGE_P15_VERIFIER_PASSWORD")

    def login(password: str) -> dict[str, Any]:
        return _json_request(
            opener,
            url=f"{prefix}/auth/login",
            method="POST",
            payload={"username": username, "password": password},
            origin=origin,
        )

    try:
        login_response = login(initial_password)
        active_password = initial_password
    except HTTPError as error:
        if error.code != 401:
            raise
        login_response = login(verifier_password)
        active_password = verifier_password
    if login_response.get("data", {}).get("mustChangePassword") is True:
        _json_request(
            opener,
            url=f"{prefix}/auth/password/change",
            method="POST",
            payload={
                "currentPassword": active_password,
                "newPassword": verifier_password,
            },
            origin=origin,
        )
    collection = _json_request(
        opener,
        url=f"{prefix}/candidates",
        origin=origin,
    )
    items = collection.get("data", {}).get("items", [])
    if not isinstance(items, list):
        raise RuntimeError("P15 Candidate collection is invalid")
    return (
        opener,
        origin,
        prefix,
        [item for item in items if isinstance(item, dict)],
    )


def verify_p15_api() -> dict[str, str]:
    opener, origin, prefix, items = _authenticated_api_context()
    matches = [
        item
        for item in items
        if item.get("candidateGroupId") == "candidate-poc-001"
    ]
    if len(matches) != 1:
        raise RuntimeError("P15 API must expose exactly one POC Candidate")
    candidate_id = matches[0].get("candidateId")
    detail_response = _json_request(
        opener,
        url=f"{prefix}/candidates/{candidate_id}",
        origin=origin,
    )
    detail = detail_response.get("data")
    if not isinstance(detail, dict):
        raise RuntimeError("P15 Candidate detail is unavailable")
    return validate_api_candidate(summary=matches[0], detail=detail)


def verify_p15_api_candidate_absent() -> None:
    _opener, _origin, _prefix, items = _authenticated_api_context()
    matches = [
        item
        for item in items
        if item.get("candidateGroupId") == "candidate-poc-001"
    ]
    if matches:
        raise RuntimeError("P15 failure API must expose zero POC Candidate")


def verify_p15_loop() -> dict[str, object]:
    expected_pack_sha256 = _required("KNOWLEDGE_P15_PACK_SHA256")
    return validate_loop_snapshot(
        snapshot=read_p15_database_snapshot(),
        api_candidate=verify_p15_api(),
        expected_pack_sha256=expected_pack_sha256,
    )


def verify_p15_failure() -> dict[str, object]:
    expected_pack_sha256 = _required("KNOWLEDGE_P15_PACK_SHA256")
    expected_scenario = _required("KNOWLEDGE_P15_EXPECTED_FAILURE")
    verify_p15_api_candidate_absent()
    return validate_failure_snapshot(
        snapshot=read_p15_database_snapshot(),
        expected_scenario=expected_scenario,
        expected_pack_sha256=expected_pack_sha256,
    )


def main() -> None:
    if os.environ.get("KNOWLEDGE_P15_EXPECTED_FAILURE"):
        result = verify_p15_failure()
    else:
        result = verify_p15_loop()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
