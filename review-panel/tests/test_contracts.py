from __future__ import annotations

from review_panel.contracts import ReviewLifecycleStatus, derive_review_status


def test_review_status_is_derived_from_files_not_database_state():
    assert (
        derive_review_status(
            packet_valid=True,
            partial_errors=False,
            decision_receipt_count=0,
            confirmation_present=False,
        )
        == ReviewLifecycleStatus.PENDING
    )
    assert (
        derive_review_status(
            packet_valid=True,
            partial_errors=False,
            decision_receipt_count=1,
            confirmation_present=False,
        )
        == ReviewLifecycleStatus.DECIDED_WAITING_CONFIRMATION
    )
    assert (
        derive_review_status(
            packet_valid=True,
            partial_errors=False,
            decision_receipt_count=1,
            confirmation_present=True,
        )
        == ReviewLifecycleStatus.CONFIRMED
    )
    assert (
        derive_review_status(
            packet_valid=False,
            partial_errors=False,
            decision_receipt_count=1,
            confirmation_present=True,
        )
        == ReviewLifecycleStatus.INVALID
    )
    assert (
        derive_review_status(
            packet_valid=True,
            partial_errors=True,
            decision_receipt_count=0,
            confirmation_present=False,
        )
        == ReviewLifecycleStatus.PARTIAL
    )

