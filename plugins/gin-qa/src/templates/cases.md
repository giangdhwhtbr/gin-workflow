# Test cases: auth

### TC-AUTH-001: Sign in with a valid password
REQ: REQ-AUTH-001@1a2b3c4d
Type: e2e
Priority: high

Preconditions:
- user alice@example.com exists

Steps:
1. Open /login
2. Fill "Email" with alice@example.com
3. Fill "Password" with the valid password
4. Click "Sign in"

Expected:
- The dashboard is shown
