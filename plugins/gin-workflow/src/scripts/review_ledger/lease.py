from datetime import datetime, timezone
from typing import Optional, Dict, Any
from review_ledger.projections import LeaseProjection, ReviewProjection

class LeaseError(ValueError):
    """Raised when a lease operation is invalid or unauthorized."""
    pass

def parse_utc_timestamp(ts_str: str) -> datetime:
    """Parses an RFC 3339 timestamp with UTC indicator (Z)."""
    # handle Z suffix representing UTC
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return datetime.fromisoformat(ts_str).astimezone(timezone.utc)

def format_utc_timestamp(dt: datetime) -> str:
    """Formats a datetime object to RFC 3339 UTC format."""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def is_lease_active(lease: Optional[LeaseProjection], current_time: datetime) -> bool:
    """Checks if a lease exists and is not yet expired."""
    if not lease:
        return False
    expiry = parse_utc_timestamp(lease.expires_at)
    return current_time < expiry

def is_lease_expired(lease: Optional[LeaseProjection], current_time: datetime, grace_seconds: int = 300) -> bool:
    """Checks if a lease exists and has expired beyond the grace period."""
    if not lease:
        return False
    expiry = parse_utc_timestamp(lease.expires_at)
    elapsed = (current_time - expiry).total_seconds()
    return elapsed > grace_seconds

def validate_lease_for_write(
    projection: ReviewProjection,
    lease_id: str,
    current_time: datetime
) -> None:
    """
    Verifies that the provided lease_id is the active holder, the lease is not expired,
    and the ledger revision matches the lease revision.
    """
    lease = projection.active_lease
    if not lease:
        raise LeaseError("No active lease exists on this ledger.")

    if lease.lease_id != lease_id:
        raise LeaseError(f"Lease ID mismatch. Active: {lease.lease_id}, Provided: {lease_id}")

    if not is_lease_active(lease, current_time):
        raise LeaseError(f"Lease {lease_id} has expired (expiry: {lease.expires_at}).")

    if projection.ledger_revision != lease.current_ledger_revision:
        raise LeaseError(
            f"Ledger revision mismatch. Expected {lease.current_ledger_revision}, "
            f"got {projection.ledger_revision}."
        )
