class EventActions:
    LEDGER_CREATED = "ledger-created"
    REVIEW_SCOPE_ESTABLISHED = "review-scope-established"
    REVIEW_SCOPE_CHANGE_REQUESTED = "review-scope-change-requested"
    LEASE_ACQUIRED = "lease-acquired"
    LEASE_RENEWED = "lease-renewed"
    LEASE_RELEASED = "lease-released"
    LEASE_BROKEN = "lease-broken"
    LEASE_RESYNCED = "lease-resynced"
    SOURCE_CHECKPOINT_CREATED = "source-checkpoint-created"
    REVIEW_STARTED = "review-started"
    FINDING_CREATED = "finding-created"
    FINDING_REOPENED = "finding-reopened"
    FINDING_FIXED = "finding-fixed"
    FINDING_DISPUTED = "finding-disputed"
    CLARIFICATION_REQUESTED = "clarification-requested"
    CLARIFICATION_PROVIDED = "clarification-provided"
    DEFERRAL_PROPOSED = "deferral-proposed"
    DEFERRAL_APPROVED = "deferral-approved"
    FINDING_VERIFIED = "finding-verified"
    FINDING_WITHDRAWN = "finding-withdrawn"
    FINDING_ACCEPTED_AS_IS = "finding-accepted-as-is"
    HUMAN_DECISION_REQUIRED = "human-decision-required"
    HUMAN_DECISION_RECORDED = "human-decision-recorded"
    FINDING_WAIVED = "finding-waived"
    REVIEW_APPROVED = "review-approved"
    REVIEW_APPROVAL_INVALIDATED = "review-approval-invalidated"
    VERIFICATION_STARTED = "verification-started"
    VERIFICATION_PASSED = "verification-passed"
    VERIFICATION_FAILED = "verification-failed"
    TRANSITION_REQUESTED = "transition-requested"
    TRANSITION_COMPLETED = "transition-completed"
    SHIPPING_STARTED = "shipping-started"
    SHIPPING_FAILED = "shipping-failed"
    SHIPPING_COMPLETED = "shipping-completed"
    RECOVERY_PERFORMED = "recovery-performed"

    ALL_ACTIONS = {
        LEDGER_CREATED, REVIEW_SCOPE_ESTABLISHED, REVIEW_SCOPE_CHANGE_REQUESTED,
        LEASE_ACQUIRED, LEASE_RENEWED, LEASE_RELEASED, LEASE_BROKEN, LEASE_RESYNCED,
        SOURCE_CHECKPOINT_CREATED, REVIEW_STARTED,
        FINDING_CREATED, FINDING_REOPENED, FINDING_FIXED, FINDING_DISPUTED,
        CLARIFICATION_REQUESTED, CLARIFICATION_PROVIDED,
        DEFERRAL_PROPOSED, DEFERRAL_APPROVED,
        FINDING_VERIFIED, FINDING_WITHDRAWN, FINDING_ACCEPTED_AS_IS,
        HUMAN_DECISION_REQUIRED, HUMAN_DECISION_RECORDED, FINDING_WAIVED,
        REVIEW_APPROVED, REVIEW_APPROVAL_INVALIDATED,
        VERIFICATION_STARTED, VERIFICATION_PASSED, VERIFICATION_FAILED,
        TRANSITION_REQUESTED, TRANSITION_COMPLETED,
        SHIPPING_STARTED, SHIPPING_FAILED, SHIPPING_COMPLETED,
        RECOVERY_PERFORMED
    }


SOURCE_IDENTITY_FIELDS = (
    "repository_path",
    "checkpoint_ref",
    "checkpoint_sha",
    "source_scope_hash",
    "source_tree_hash",
)


def has_complete_source_identity(repository):
    return all(
        isinstance(repository.get(field), str) and bool(repository[field].strip())
        for field in SOURCE_IDENTITY_FIELDS
    )
