from typing import List, Dict

class InvalidTransitionError(ValueError):
    """Raised when a Bead status transition violates FSM state or actor rules."""
    def __init__(self, message: str, current_state: str, next_state: str, actor_role: str):
        super().__init__(message)
        self.current_state = current_state
        self.next_state = next_state
        self.actor_role = actor_role

# Set of terminal finding statuses from finding_fsm
TERMINAL_FINDING_STATUSES = {
    "verified",
    "withdrawn",
    "accepted-as-is",
    "deferred-verified",
    "human-waived"
}

def validate_bead_transition(
    current_state: str,
    next_state: str,
    actor_role: str,
    finding_statuses: List[str] = None
) -> None:
    """
    Validates a Bead status transition according to spec §4.
    If next_state is 'review-approved', verifies all finding_statuses are terminal.
    Raises InvalidTransitionError if validation fails.
    """
    actor_role = actor_role.lower()

    # Map of (current_state, next_state) -> set of allowed actor roles
    transition_roles = {
        ("implementation-in-progress", "implementation-complete"): {"worker"},
        ("implementation-in-progress", "review-requested"): {"worker"},
        ("implementation-complete", "review-requested"): {"worker"},
        ("review-requested", "review-in-progress"): {"reviewer"},
        ("review-in-progress", "changes-requested"): {"reviewer"},
        ("review-in-progress", "blocked-human"): {"reviewer"},
        ("review-in-progress", "review-approved"): {"reviewer"},
        ("changes-requested", "implementation-in-progress"): {"worker"},
        ("blocked-human", "changes-requested"): {"human"},
        ("review-approved", "verification-in-progress"): {"verifier"},
        ("review-approved", "implementation-in-progress"): {"reviewer"},
        ("verification-in-progress", "ready-to-ship"): {"verifier"},
        ("verification-in-progress", "implementation-in-progress"): {"verifier"},
        ("ready-to-ship", "closed"): {"shipping", "orchestrator"},
        ("ready-to-ship", "shipping-failed"): {"shipping", "orchestrator"},
        ("shipping-failed", "ready-to-ship"): {"shipping", "orchestrator"},
        ("shipping-failed", "implementation-in-progress"): {"worker"},
        ("shipping-failed", "closed"): {"human"}
    }

    pair = (current_state, next_state)
    if pair not in transition_roles:
        raise InvalidTransitionError(
            f"Transition from state '{current_state}' to '{next_state}' is not supported.",
            current_state, next_state, actor_role
        )

    allowed_roles = transition_roles[pair]
    if actor_role not in allowed_roles:
        raise InvalidTransitionError(
            f"Actor '{actor_role}' is not allowed to transition state '{current_state}' to '{next_state}'. "
            f"Allowed roles: {allowed_roles}",
            current_state, next_state, actor_role
        )

    # Validate review-approved requirements: all findings must be terminal
    if next_state == "review-approved" and finding_statuses is not None:
        for status in finding_statuses:
            if status not in TERMINAL_FINDING_STATUSES:
                raise InvalidTransitionError(
                    f"Cannot approve review: finding status '{status}' is non-terminal.",
                    current_state, next_state, actor_role
                )
