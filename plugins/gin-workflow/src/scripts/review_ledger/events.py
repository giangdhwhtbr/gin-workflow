import hashlib
import json
import re
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from review_ledger import jcs

class WorkflowIntegrityError(Exception):
    """Raised when ledger verification or replay checks fail."""
    pass

@dataclass
class LedgerEvent:
    event_id: str
    action: str
    timestamp: str
    actor: Dict[str, Any]
    payload: Dict[str, Any]
    previous_event_hash: Optional[str]
    event_hash: Optional[str] = None

    def to_dict(self, exclude_hash: bool = False) -> Dict[str, Any]:
        d = {
            "event_id": self.event_id,
            "action": self.action,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "payload": self.payload,
            "previous_event_hash": self.previous_event_hash
        }
        if not exclude_hash:
            d["event_hash"] = self.event_hash
        return d

    def compute_hash(self) -> str:
        # RFC 8785 canonicalization of the event dictionary, excluding its own hash.
        canonical_str = jcs.serialize(self.to_dict(exclude_hash=True))
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def verify_hash(self) -> bool:
        if not self.event_hash:
            return False
        return self.compute_hash() == self.event_hash

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LedgerEvent":
        # Reject duplicate keys in source dict during JCS parsing (handled at caller, 
        # but we require all fields are present).
        required = {"event_id", "action", "timestamp", "actor", "payload", "previous_event_hash"}
        missing = required - set(d.keys())
        if missing:
            raise WorkflowIntegrityError(f"Missing required event fields: {missing}")
        
        return cls(
            event_id=d["event_id"],
            action=d["action"],
            timestamp=d["timestamp"],
            actor=d["actor"],
            payload=d["payload"],
            previous_event_hash=d["previous_event_hash"],
            event_hash=d.get("event_hash")
        )

def parse_event_id_number(event_id: str) -> Optional[int]:
    """Helper to extract a trailing numeric sequence number from event_id (e.g. CRE-000042 -> 42)."""
    match = re.search(r'(\d+)$', event_id)
    if match:
        return int(match.group(1))
    return None

class EventLog:
    def __init__(self, events: Optional[List[LedgerEvent]] = None):
        self.events: List[LedgerEvent] = events if events is not None else []

    def append(self, event: LedgerEvent):
        # Assign hash based on current chain head
        if not self.events:
            event.previous_event_hash = None
        else:
            event.previous_event_hash = self.events[-1].event_hash
        
        event.event_hash = event.compute_hash()
        self.events.append(event)

    def replay_and_validate(self):
        """
        Replays the event log from start to end, verifying the hash chain,
        uniqueness of event IDs, sequence numbering, and cryptographic hashes.
        Raises WorkflowIntegrityError if any invariant is violated.
        """
        seen_ids = set()
        prev_hash: Optional[str] = None
        prev_num: Optional[int] = None

        for idx, event in enumerate(self.events):
            # 1. Unique event ID check
            if event.event_id in seen_ids:
                raise WorkflowIntegrityError(f"Duplicate event ID detected: {event.event_id}")
            seen_ids.add(event.event_id)

            # 2. Check first event has null previous hash
            if idx == 0:
                if event.previous_event_hash is not None:
                    raise WorkflowIntegrityError("First event must have previous_event_hash set to null")
            else:
                # 3. Hash chain continuity check
                if event.previous_event_hash != prev_hash:
                    raise WorkflowIntegrityError(
                        f"Hash chain broken at event {event.event_id}: "
                        f"expected {prev_hash}, got {event.previous_event_hash}"
                    )

            # 4. Cryptographic integrity check (signature / computed hash check)
            if not event.verify_hash():
                raise WorkflowIntegrityError(
                    f"Cryptographic hash mismatch for event {event.event_id}: "
                    f"stored {event.event_hash}, computed {event.compute_hash()}"
                )

            # 5. Decreasing sequence number check
            num = parse_event_id_number(event.event_id)
            if num is not None and prev_num is not None:
                if num < prev_num:
                    raise WorkflowIntegrityError(
                        f"Decreasing event sequence number detected at {event.event_id} "
                        f"({num} < {prev_num})"
                    )
            
            prev_hash = event.event_hash
            if num is not None:
                prev_num = num

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.events]

    @classmethod
    def from_list(cls, l: List[Dict[str, Any]]) -> "EventLog":
        events = []
        for item in l:
            events.append(LedgerEvent.from_dict(item))
        log = cls(events)
        log.replay_and_validate()
        return log
