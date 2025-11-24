#!/bin/bash
# Check for incorrect dates in documentation
# Run before committing docs

CURRENT_YEAR=$(date +%Y)
WRONG_DATES=$(grep -r "2024-11-24\|2024-11-25\|2024-11-26" --include="*.md" . 2>/dev/null | wc -l)

if [ "$WRONG_DATES" -gt 0 ]; then
    echo "❌ ERROR: Found outdated 2024 dates in documentation!"
    echo ""
    echo "Files with wrong dates:"
    grep -r "2024-11-24\|2024-11-25\|2024-11-26" --include="*.md" .
    echo ""
    echo "Current year is: $CURRENT_YEAR"
    echo "Please fix dates to use 2025"
    exit 1
else
    echo "✅ All dates look correct (no 2024 dates found)"
    exit 0
fi

