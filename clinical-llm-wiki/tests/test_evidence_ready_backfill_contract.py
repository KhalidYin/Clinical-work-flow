from __future__ import annotations

from contextlib import contextmanager


def test_evidence_ready_backfill_selects_only_parsed_runs_without_candidates() -> None:
    from service.maintenance.evidence_ready import (
        RunReadiness,
        select_evidence_ready_run_ids,
    )

    facts = (
        RunReadiness(
            run_id="run-001",
            status="author_confirmation_required",
            evidence_count=2,
            candidate_count=0,
        ),
        RunReadiness(
            run_id="run-002",
            status="author_confirmation_required",
            evidence_count=0,
            candidate_count=0,
        ),
        RunReadiness(
            run_id="run-003",
            status="author_confirmation_required",
            evidence_count=1,
            candidate_count=1,
        ),
        RunReadiness(
            run_id="run-004",
            status="evidence_ready",
            evidence_count=1,
            candidate_count=0,
        ),
    )

    assert select_evidence_ready_run_ids(facts) == ("run-001",)


def test_backfill_pages_by_scanned_run_and_is_idempotent() -> None:
    from service.maintenance.evidence_ready import (
        EvidenceReadyBackfillService,
        RunReadiness,
    )

    class FakeRepository:
        def __init__(self) -> None:
            self.facts = {
                "run-001": RunReadiness(
                    run_id="run-001",
                    status="author_confirmation_required",
                    evidence_count=1,
                    candidate_count=0,
                ),
                "run-002": RunReadiness(
                    run_id="run-002",
                    status="author_confirmation_required",
                    evidence_count=2,
                    candidate_count=0,
                ),
                "run-003": RunReadiness(
                    run_id="run-003",
                    status="author_confirmation_required",
                    evidence_count=0,
                    candidate_count=0,
                ),
            }

        @contextmanager
        def locked_page(
            self,
            *,
            batch_size: int,
            after_key: str | None,
        ):
            eligible_keys = sorted(
                run_id
                for run_id, fact in self.facts.items()
                if fact.status == "author_confirmation_required"
                and (after_key is None or run_id > after_key)
            )
            facts = tuple(self.facts[run_id] for run_id in eligible_keys[:batch_size])
            repository = self

            class Page:
                def __init__(self) -> None:
                    self.facts = facts

                def mark_evidence_ready(self, run_ids: tuple[str, ...]) -> int:
                    for run_id in run_ids:
                        fact = repository.facts[run_id]
                        repository.facts[run_id] = RunReadiness(
                            run_id=run_id,
                            status="evidence_ready",
                            evidence_count=fact.evidence_count,
                            candidate_count=fact.candidate_count,
                        )
                    return len(run_ids)

            yield Page()

    repository = FakeRepository()
    service = EvidenceReadyBackfillService(repository)

    assert service.run_page(batch_size=1, after_key=None) == (1, "run-001")
    assert service.run_page(batch_size=1, after_key="run-001") == (1, "run-002")
    assert service.run_page(batch_size=1, after_key="run-002") == (0, "run-003")
    assert service.run_page(batch_size=1, after_key="run-003") == (0, None)
    assert service.run_page(batch_size=10, after_key=None) == (0, None)
