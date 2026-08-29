import unittest
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../plugins/gin-workflow/src/scripts')))

from review_ledger.projections import LeaseProjection, ReviewProjection
from review_ledger.lease import (
    is_lease_active,
    is_lease_expired,
    validate_lease_for_write,
    LeaseError,
    parse_utc_timestamp,
    format_utc_timestamp
)

class TestLease(unittest.TestCase):
    def test_timestamp_utils(self):
        dt = datetime(2026, 7, 18, 17, 30, 0, tzinfo=timezone.utc)
        ts = format_utc_timestamp(dt)
        self.assertEqual(ts, "2026-07-18T17:30:00Z")
        self.assertEqual(parse_utc_timestamp(ts), dt)

    def test_lease_activity(self):
        now = datetime.now(timezone.utc)
        future = now + timedelta(minutes=10)
        past = now - timedelta(minutes=10)
        
        lease = LeaseProjection("lease-123", "reviewer", "rev-1", "ts1", format_utc_timestamp(future), 5)
        self.assertTrue(is_lease_active(lease, now))
        self.assertFalse(is_lease_expired(lease, now))
        
        lease_expired = LeaseProjection("lease-123", "reviewer", "rev-1", "ts1", format_utc_timestamp(past), 5)
        self.assertFalse(is_lease_active(lease_expired, now))
        # 10 minutes past is > 5 minutes default grace (300s)
        self.assertTrue(is_lease_expired(lease_expired, now))
        # 10 minutes past is not > 15 minutes grace (900s)
        self.assertFalse(is_lease_expired(lease_expired, now, grace_seconds=900))

    def test_validate_lease_for_write(self):
        now = datetime.now(timezone.utc)
        future = now + timedelta(minutes=10)
        
        proj = ReviewProjection()
        proj.ledger_revision = 5
        proj.active_lease = LeaseProjection("lease-123", "reviewer", "rev-1", "ts1", format_utc_timestamp(future), 5)
        
        # Valid write
        validate_lease_for_write(proj, "lease-123", now)
        
        # Mismatched ID
        with self.assertRaises(LeaseError):
            validate_lease_for_write(proj, "lease-999", now)
            
        # Ledger revision difference does not block write (decision b for gin-workflow-0qh)
        proj.ledger_revision = 6
        validate_lease_for_write(proj, "lease-123", now)
            
        # Expired lease
        proj.ledger_revision = 5
        past = now - timedelta(minutes=1)
        proj.active_lease.expires_at = format_utc_timestamp(past)
        with self.assertRaises(LeaseError):
            validate_lease_for_write(proj, "lease-123", now)

if __name__ == "__main__":
    unittest.main()
