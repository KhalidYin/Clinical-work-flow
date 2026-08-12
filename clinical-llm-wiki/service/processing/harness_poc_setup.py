"""Prepare the checked-in demo run for the P15 local Harness POC."""

from __future__ import annotations

import json
import os
from typing import Any

from sqlalchemy import select

from service.db.models import (
    Evidence,
    JobStep,
    ModelProfile,
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


POC_MODEL_PROFILE_ID = "p15-internal-mock"
POC_MODEL_PROFILE_VERSION = "1.0.0"


def poc_model_profile_values(*, timeout_seconds: int = 30) -> dict[str, Any]:
    if not 1 <= timeout_seconds <= 3600:
        raise ValueError("P15 model timeout must be between 1 and 3600 seconds")
    return {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "deployment_class": "enterprise_managed",
        "secret_ref": "env://SYNTHETIC_PROVIDER_KEY",
        "endpoint_ref": None,
        "allowed_data_boundaries": ["enterprise_provider_only"],
        "capabilities": ["structured_generation"],
        "timeout_seconds": timeout_seconds,
        "max_output_tokens": 4096,
        "cost_policy": {
            "mode": "p15_internal_mock",
            "network": "internal-only",
        },
    }


def configure_step_for_harness(step: Any, *, attempt_status: str) -> None:
    if step.step_key != ENRICHMENT_STEP_KEY:
        raise RuntimeError("P15 setup may only configure the enrichment step")
    if step.executor_kind == "harness":
        return
    if step.status != "queued" or attempt_status != "queued":
        raise RuntimeError("P15 setup requires a queued, unleased attempt")
    step.executor_kind = "harness"


def configure_p15_harness_poc() -> dict[str, object]:
    engine = create_database_engine(database_url_from_environment())
    sessions = create_session_factory(engine)
    try:
        with sessions.begin() as session:
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
                raise RuntimeError("P15 setup requires the canonical demo run")
            row = session.execute(
                select(JobStep, StepAttempt)
                .join(
                    StepAttempt,
                    (StepAttempt.step_id == JobStep.step_id)
                    & (StepAttempt.run_id == JobStep.run_id),
                )
                .where(
                    JobStep.run_id == run.run_id,
                    JobStep.step_key == ENRICHMENT_STEP_KEY,
                )
                .order_by(StepAttempt.attempt_number.desc())
                .limit(1)
            ).one_or_none()
            if row is None:
                raise RuntimeError("P15 setup requires an enrichment attempt")
            step, attempt = row
            configure_step_for_harness(step, attempt_status=attempt.status)

            profile = session.get(
                ModelProfile,
                (POC_MODEL_PROFILE_ID, POC_MODEL_PROFILE_VERSION),
            )
            timeout_seconds = int(
                os.environ.get("KNOWLEDGE_P15_MODEL_TIMEOUT_SECONDS", "30")
            )
            values = poc_model_profile_values(timeout_seconds=timeout_seconds)
            if profile is None:
                session.add(
                    ModelProfile(
                        profile_id=POC_MODEL_PROFILE_ID,
                        version=POC_MODEL_PROFILE_VERSION,
                        **values,
                    )
                )
            else:
                observed = {name: getattr(profile, name) for name in values}
                if observed != values:
                    raise RuntimeError("P15 ModelProfile configuration drift detected")

            evidence_ids = tuple(
                session.scalars(
                    select(Evidence.evidence_id)
                    .where(Evidence.source_version_id == run.source_version_id)
                    .order_by(Evidence.evidence_id)
                )
            )
            if not evidence_ids:
                raise RuntimeError("P15 setup requires canonical Evidence")
            return {
                "run_id": run.run_id,
                "attempt_id": attempt.attempt_id,
                "evidence_ids": list(evidence_ids),
                "executor_kind": step.executor_kind,
                "model_profile_id": POC_MODEL_PROFILE_ID,
                "model_profile_version": POC_MODEL_PROFILE_VERSION,
            }
    finally:
        engine.dispose()


def main() -> None:
    print(json.dumps(configure_p15_harness_poc(), sort_keys=True))


if __name__ == "__main__":
    main()
