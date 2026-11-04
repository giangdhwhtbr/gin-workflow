# TC-AUTH-001: Sign in with a valid password

- **REQ:** REQ-AUTH-001@1a2b3c4d
- **Priority:** high

**Preconditions:**
- user alice@example.com exists

**Test data:**
- Email: alice@example.com
- Password: environment variable `E2E_ALICE_PASSWORD`

**Steps:**
1. Open /login
2. Fill "Email" with the email from Test data

**Expected:**
- The dashboard is shown
