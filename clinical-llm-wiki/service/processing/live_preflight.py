"""Fail-closed preflight for the single P2-B3 live enrichment vertical."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
import os
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from service.db.models import (
    Evidence,
    JobStep,
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

from .enrichment import ENRICHMENT_STEP_KEY, load_enrichment_profiles
from .model_profiles import (
    LiveModelAuthorization,
    live_model_authorization_from_environment,
    validate_live_model_authorization,
)
from .model_provider import DataBoundary, ModelProfile, PromptProfile, enforce_data_boundary


class LiveVerticalPreflightError(RuntimeError):
    """The selected run is not safe and ready for one live model call."""


def preflight_live_vertical(
    session_factory: sessionmaker[Session],
    *,
    run_id: str,
    model_profile: ModelProfile,
    prompt_profile: PromptProfile,
    authorization: LiveModelAuthorization,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Validate one target run without resolving secrets or invoking a provider."""

    values = os.environ if environ is None else environ
    validate_live_model_authorization(
        model_profile=model_profile,
        authorization=authorization,
    )
    if model_profile.provider in {"fake", "replay"}:
        raise LiveVerticalPreflightError(
            "P2-B3 live vertical requires a non-fixture model provider"
        )
    if authorization.max_calls != 1:
        raise LiveVerticalPreflightError(
            "P2-B3 live vertical requires KNOWLEDGE_LIVE_MODEL_MAX_CALLS=1"
        )
    _require_configured_environment_reference(model_profile.secret_ref, values)
    if model_profile.endpoint_ref is not None:
        _require_configured_environment_reference(model_profile.endpoint_ref, values)

    with session_factory() as session:
        run = session.get(ProcessingRun, run_id)
        if run is None:
            raise LiveVerticalPreflightError("target processing run does not exist")
        if run.status != "evidence_ready":
            raise LiveVerticalPreflightError(
                "target processing run must be in evidence_ready status"
            )
        source_version = session.get(SourceVersion, run.source_version_id)
        if source_version is None:
            raise LiveVerticalPreflightError("target run has no source version")
        boundary = DataBoundary(source_version.data_boundary)
        if boundary not in authorization.allowed_data_boundaries:
            raise LiveVerticalPreflightError(
                "target source data boundary is not included in the live authorization"
            )
        try:
            enforce_data_boundary(model_profile, boundary)
        except ValueError as exc:
            raise LiveVerticalPreflightError(str(exc)) from None

        evidence_count = session.scalar(
            select(func.count(Evidence.evidence_id)).where(
                Evidence.source_version_id == source_version.source_version_id
            )
        )
        if not evidence_count:
            raise LiveVerticalPreflightError("target run has no canonical Evidence")

        step = session.scalar(
            select(JobStep).where(
                JobStep.run_id == run_id,
                JobStep.step_key == ENRICHMENT_STEP_KEY,
            )
        )
        if step is None or step.status != "queued":
            raise LiveVerticalPreflightError(
                "target enrichment step must be explicitly queued"
            )
        attempt = session.scalar(
            select(StepAttempt)
            .where(
                StepAttempt.run_id == run_id,
                StepAttempt.step_id == step.step_id,
                StepAttempt.status == "queued",
            )
            .order_by(StepAttempt.attempt_number.desc())
        )
        if attempt is None:
            raise LiveVerticalPreflightError(
                "target enrichment step has no queued StepAttempt"
            )
        invocation_count = session.scalar(
            select(func.count(ModelInvocation.invocation_id)).where(
                ModelInvocation.run_id == run_id
            )
        )
        if invocation_count:
            raise LiveVerticalPreflightError(
                "target run already has a model invocation; choose a fresh P2-B3 run"
            )

    return {
        "ready": True,
        "run_id": run_id,
        "source_version_id": source_version.source_version_id,
        "data_boundary": boundary.value,
        "evidence_count": int(evidence_count),
        "step_id": step.step_id,
        "attempt_id": attempt.attempt_id,
        "attempt_number": attempt.attempt_number,
        "model_profile_id": model_profile.profile_id,
        "model_profile_version": model_profile.version,
        "prompt_profile_id": prompt_profile.profile_id,
        "prompt_profile_version": prompt_profile.version,
        "output_schema_sha256": prompt_profile.output_schema_sha256,
        "max_calls": authorization.max_calls,
        "secret_reference": "configured",
        "endpoint_reference": (
            "configured" if model_profile.endpoint_ref is not None else "not_required"
        ),
    }


def _require_configured_environment_reference(
    reference: str,
    values: Mapping[str, str],
) -> None:
    scheme, name = reference.split("://", 1)
    if scheme != "env":
        raise LiveVerticalPreflightError(
            "embedded live adapter currently requires env:// secret references"
        )
    if not values.get(name):
        raise LiveVerticalPreflightError(
            "a required live model environment reference is not configured"
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if os.environ.get("KNOWLEDGE_ENRICHMENT_PROVIDER_MODE") != "live":
        raise LiveVerticalPreflightError(
            "KNOWLEDGE_ENRICHMENT_PROVIDER_MODE=live is required"
        )
    engine = create_database_engine(database_url_from_environment())
    sessions = create_session_factory(engine)
    try:
        model_profile, prompt_profile = load_enrichment_profiles(
            sessions,
            model_profile_id=os.environ.get(
                "KNOWLEDGE_ENRICHMENT_MODEL_PROFILE_ID",
                "demo-extractor",
            ),
            model_profile_version=os.environ.get(
                "KNOWLEDGE_ENRICHMENT_MODEL_PROFILE_VERSION",
                "1.0.0",
            ),
            prompt_profile_id=os.environ.get(
                "KNOWLEDGE_ENRICHMENT_PROMPT_PROFILE_ID",
                "atomic-candidate",
            ),
            prompt_profile_version=os.environ.get(
                "KNOWLEDGE_ENRICHMENT_PROMPT_PROFILE_VERSION",
                "1.1.0",
            ),
        )
        result = preflight_live_vertical(
            sessions,
            run_id=args.run_id,
            model_profile=model_profile,
            prompt_profile=prompt_profile,
            authorization=live_model_authorization_from_environment(),
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
