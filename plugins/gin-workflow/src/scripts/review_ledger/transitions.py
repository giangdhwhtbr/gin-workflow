import uuid
from typing import Dict, Any, Optional
from review_ledger.events import WorkflowIntegrityError

def generate_transition_id() -> str:
    """Generates a unique transition ID in the format CRT-<UUID-HEX-8>."""
    return f"CRT-{uuid.uuid4().hex[:8].upper()}"

def reconcile_transition_states(
    bead_status: str,
    ledger_state: str,
    pending_transition: Optional[Dict[str, Any]]
) -> str:
    """
    Compares the Beads status and ledger state. If they differ, applies recovery rules
    from spec §11.2. Returns one of: 'ok', 'replay_bead', or raises WorkflowIntegrityError.
    """
    # Normalize state names (Beads uses in_progress, ledger uses implementation-in-progress, etc.)
    # Map Beads status to ledger state names for comparison
    beads_to_ledger_map = {
        "open": "implementation-complete",
        "in_progress": "implementation-in-progress",
        "closed": "closed",
        "blocked": "blocked-human"
    }
    
    # Reverse mapping for common statuses or standard translation
    normalized_bead = beads_to_ledger_map.get(bead_status, bead_status)
    
    # Special normalization matches:
    # 'implementation-complete' can map to 'open' in Beads
    # 'implementation-in-progress' is 'in_progress'
    # 'review-requested', 'review-in-progress', 'changes-requested', 'review-approved', 
    # 'verification-in-progress', 'ready-to-ship', 'shipping-failed' all map to 'in_progress' or 'open' in Beads.
    # Wait, in §2.2: "Beads owns runtime task state... Review ledger owns findings... Git owns source code."
    # So Beads status is simpler: open, in_progress, blocked, closed.
    # Therefore, multiple ledger review states map to a single Beads status.
    # E.g. 'implementation-in-progress', 'changes-requested', 'verification-in-progress' -> 'in_progress' in Beads.
    # 'review-requested', 'review-approved', 'ready-to-ship', 'shipping-failed' -> 'open' or 'in_progress'.
    # Let's check how we match them.
    # A transition is valid if the mapping holds.
    # Let's define the mapping:
    valid_mappings = {
        "implementation-in-progress": {"in_progress"},
        "implementation-complete": {"open", "in_progress"},
        "review-requested": {"open"},
        "review-in-progress": {"in_progress"},
        "changes-requested": {"in_progress"},
        "blocked-human": {"blocked"},
        "review-approved": {"open", "in_progress"},
        "verification-in-progress": {"in_progress"},
        "ready-to-ship": {"open"},
        "shipping-failed": {"open", "in_progress"},
        "closed": {"closed"}
    }

    # If the states align under standard mapping:
    if normalized_bead == ledger_state or (ledger_state in valid_mappings and bead_status in valid_mappings[ledger_state]):
        return "ok"

    # Recovery checks
    if pending_transition:
        # Ledger ahead, Beads behind:
        # The ledger has transitioned (or is transition-requested), but Beads is still at the previous state.
        trans_from = pending_transition.get("from")
        trans_to = pending_transition.get("to")
        
        # Check if the current Beads state matches the 'from' mapping,
        # and the current ledger state matches the 'to' mapping.
        from_matches = (trans_from in valid_mappings and bead_status in valid_mappings[trans_from])
        to_matches = (ledger_state == trans_to)
        
        if from_matches and to_matches:
            return "replay_bead"

    # Beads ahead, ledger missing or unrecognized mismatch: fail closed
    raise WorkflowIntegrityError(
        f"Workflow integrity mismatch: Beads is '{bead_status}', ledger is '{ledger_state}'. "
        f"No matching pending transition found."
    )
