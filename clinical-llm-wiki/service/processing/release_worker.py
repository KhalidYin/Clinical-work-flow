"""Release-pool handler for building, but never publishing, P17 candidates."""

from __future__ import annotations

from hashlib import sha256
from typing import Callable, Mapping, Protocol

from service.auth import ActorContext
from service.object_store import ObjectIntegrityError, ObjectStorePort
from service.releases import ReleaseBuildCommand, ReleaseBuilder

from .contracts import (
    ArtifactManifest,
    ClaimedStepAttempt,
    ExecutorKind,
    StepDefinition,
    StepOutcome,
)


RELEASE_BUILD_STEP_KEY = "release.build_candidate"


class ReleaseStepContext(Protocol):
    claim: ClaimedStepAttempt


class ReleaseWorkerService:
    def __init__(
        self,
        *,
        actor: ActorContext,
        repository,
        object_store: ObjectStorePort,
    ) -> None:
        self._actor = actor
        self._objects = object_store
        self._builder = ReleaseBuilder(
            repository=repository,
            object_store=object_store,
        )

    def build_candidate(self, context: ReleaseStepContext) -> StepOutcome:
        claim = context.claim
        object_key = f"release-requests/{claim.input_sha256}.json"
        content = self._objects.get_bytes(object_key)
        if sha256(content).hexdigest() != claim.input_sha256:
            raise ObjectIntegrityError("Release build request hash mismatch")
        command = ReleaseBuildCommand.model_validate_json(content)
        prepared = self._builder.build(actor=self._actor, command=command)
        return StepOutcome(
            output_sha256=prepared.manifest_descriptor.sha256,
            artifact_manifest=ArtifactManifest(
                artifacts=(
                    prepared.index_descriptor,
                    prepared.manifest_descriptor,
                )
            ),
        )


def build_release_step_definition(*, input_sha256: str) -> StepDefinition:
    return StepDefinition(
        step_key=RELEASE_BUILD_STEP_KEY,
        pool="release",
        input_sha256=input_sha256,
        executor_kind=ExecutorKind.DETERMINISTIC_HANDLER.value,
    )


def release_step_handlers(
    service: ReleaseWorkerService,
) -> Mapping[str, Callable[[ReleaseStepContext], StepOutcome]]:
    return {RELEASE_BUILD_STEP_KEY: service.build_candidate}


__all__ = [
    "RELEASE_BUILD_STEP_KEY",
    "ReleaseWorkerService",
    "build_release_step_definition",
    "release_step_handlers",
]
