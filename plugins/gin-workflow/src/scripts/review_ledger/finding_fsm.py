from typing import Set

class InvalidTransitionError(ValueError):
    """Raised when a finding transition violates FSM state or actor rules."""
    def __init__(self, message: str, current_status: str, next_status: str, severity: str, actor_role: str):
        super().__init__(message)
        self.current_status = current_status
        self.next_status = next_status
        self.severity = severity
        self.actor_role = actor_role

# Set of valid terminal statuses
TERMINAL_STATUSES: Set[str] = {
    "verified",
    "withdrawn",
    "accepted-as-is",
    "deferred-verified",
    "human-waived"
}

def validate_finding_transition(
    current_status: str,
    next_status: str,
    severity: str,
    actor_role: str,
    clarification_count: int,
    max_clarifications: int = 1
) -> None:
    """
    Validates a state transition for a finding against the spec FSM state table.
    `max_clarifications` caps how many clarification rounds a dispute may take;
    the default of 1 is the spec §5.1 limit.
    Raises InvalidTransitionError if the transition is invalid.
    """
    severity = severity.upper()
    actor_role = actor_role.lower()

    # Base finding transition table from spec §5.1
    # Maps (current_status, next_status) -> set of allowed actor roles
    transition_roles = {
        ("open", "fixed-awaiting-verification"): {"worker"},
        ("open", "disputed"): {"worker"},
        ("open", "deferral-proposed"): {"worker"},
        ("open", "human-waived"): {"human"},
        
        ("fixed-awaiting-verification", "verified"): {"reviewer"},
        ("fixed-awaiting-verification", "open"): {"reviewer"},
        
        ("disputed", "withdrawn"): {"reviewer"},
        ("disputed", "accepted-as-is"): {"reviewer"},
        ("disputed", "clarification-requested"): {"reviewer"},
        ("disputed", "human-decision-required"): {"reviewer"},
        
        ("clarification-requested", "clarification-provided"): {"worker"},
        
        ("clarification-provided", "withdrawn"): {"reviewer"},
        ("clarification-provided", "accepted-as-is"): {"reviewer"},
        ("clarification-provided", "open"): {"reviewer"},
        ("clarification-provided", "human-decision-required"): {"reviewer"},
        
        ("human-decision-required", "human-decision-recorded"): {"human"},
        ("human-decision-required", "human-waived"): {"human"},
        
        ("human-decision-recorded", "fixed-awaiting-verification"): {"worker"},
        ("human-decision-recorded", "deferred-awaiting-verification"): {"worker"},
        
        # Deferrals
        ("deferral-proposed", "deferred-verified"): {"reviewer"},          # Shortcut for Minor/Suggestion
        ("deferral-proposed", "human-decision-required"): {"reviewer"},     # Path for Important
        ("deferred-awaiting-verification", "deferred-verified"): {"reviewer"}, # Final verification of deferrals
    }

    pair = (current_status, next_status)
    if pair not in transition_roles:
        raise InvalidTransitionError(
            f"Transition from '{current_status}' to '{next_status}' is not supported.",
            current_status, next_status, severity, actor_role
        )

    allowed_roles = transition_roles[pair]
    if actor_role not in allowed_roles:
        raise InvalidTransitionError(
            f"Actor '{actor_role}' is not allowed to transition '{current_status}' to '{next_status}'. "
            f"Allowed roles: {allowed_roles}",
            current_status, next_status, severity, actor_role
        )

    # Severity-aware checks from spec §5.2
    if severity == "CRITICAL":
        if next_status in ("deferral-proposed", "deferred-verified", "deferred-awaiting-verification"):
            raise InvalidTransitionError(
                "CRITICAL findings cannot be deferred.",
                current_status, next_status, severity, actor_role
            )
            
    elif severity == "IMPORTANT":
        # Cannot bypass human approval (human-decision-recorded) for Important deferrals
        if current_status == "deferral-proposed" and next_status == "deferred-verified":
            raise InvalidTransitionError(
                "IMPORTANT findings cannot be deferred directly. Deferral requires human authorization.",
                current_status, next_status, severity, actor_role
            )

    # Clarification request limit check from spec §5.1 (max 1 clarification by default)
    if current_status == "disputed" and next_status == "clarification-requested":
        if clarification_count >= max_clarifications:
            raise InvalidTransitionError(
                f"Clarification has already been requested {clarification_count} time(s). "
                f"Maximum {max_clarifications} request(s) allowed.",
                current_status, next_status, severity, actor_role
            )
