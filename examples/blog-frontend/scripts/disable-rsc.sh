#!/bin/bash
# Disable React Server Components (RSC) utilities
# Usage: ./scripts/disable-rsc.sh

set -e

echo "🔄 Disabling RSC utilities..."

# Remove RSC directory from lib
if [ -d "src/lib/rsc" ]; then
    rm -rf src/lib/rsc
    echo "   ✓ Removed src/lib/rsc/"
fi

echo ""
echo "✅ RSC utilities disabled!"
echo ""
echo "The original files remain in src/optional/rsc/ for future use."
echo "To re-enable RSC utilities, run: ./scripts/setup-rsc.sh"
