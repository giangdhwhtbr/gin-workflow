#!/usr/bin/env bash
# Bisection script to find which test creates unwanted files/state
# Usage: ./find-polluter.sh <file_or_dir_to_check> <test_pattern>
# Example: ./find-polluter.sh '.git' 'src/**/*.test.ts'

set -e

if [ $# -ne 2 ]; then
  echo "Usage: $0 <file_to_check> <test_pattern>"
  echo "Example: $0 '.git' 'src/**/*.test.ts'"
  exit 1
fi

POLLUTION_CHECK="$1"
TEST_PATTERN="$2"

echo "🔍 Searching for test that creates: $POLLUTION_CHECK"
echo "Test pattern: $TEST_PATTERN"
echo ""

# Check baseline pollution target
if [ -e "$POLLUTION_CHECK" ]; then
  echo "❌ Error: Pollution target '$POLLUTION_CHECK' already exists before test run." >&2
  echo "   Please clean up the target before running polluter bisection." >&2
  exit 1
fi

# Get list of test files using globstar
shopt -s globstar nullglob 2>/dev/null || true
RAW_FILES=($TEST_PATTERN)
if [ ${#RAW_FILES[@]} -gt 0 ]; then
  TEST_FILES=$(printf "%s\n" "${RAW_FILES[@]}" | sort -u)
else
  NORM_PATTERN="${TEST_PATTERN#./}"
  TEST_FILES=$(find . -type f \( -path "./$NORM_PATTERN" -o -path "$NORM_PATTERN" -o -name "$TEST_PATTERN" \) | sort)
fi

if [ -z "$TEST_FILES" ]; then
  echo "❌ Error: No test files found matching pattern '$TEST_PATTERN'" >&2
  exit 1
fi

TOTAL=$(echo "$TEST_FILES" | wc -l | tr -d ' ')
echo "Found $TOTAL test files"
echo ""

COUNT=0
for TEST_FILE in $TEST_FILES; do
  COUNT=$((COUNT + 1))
  echo "[$COUNT/$TOTAL] Testing: $TEST_FILE"

  # Run the test
  npm test "$TEST_FILE" > /dev/null 2>&1 || true

  # Check if pollution appeared
  if [ -e "$POLLUTION_CHECK" ]; then
    echo ""
    echo "🎯 FOUND POLLUTER!"
    echo "   Test: $TEST_FILE"
    echo "   Created: $POLLUTION_CHECK"
    echo ""
    echo "Pollution details:"
    ls -la "$POLLUTION_CHECK"
    echo ""
    echo "To investigate:"
    echo "  npm test $TEST_FILE    # Run just this test"
    echo "  cat $TEST_FILE         # Review test code"
    exit 1
  fi
done

echo ""
echo "✅ No polluter found - all tests clean!"
exit 0
