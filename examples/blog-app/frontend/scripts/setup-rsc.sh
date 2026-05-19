#!/bin/bash
# Enable React Server Components (RSC) utilities
# Usage: ./scripts/setup-rsc.sh

set -e

echo "🚀 Setting up RSC utilities..."

# Check if optional RSC files exist
if [ ! -d "src/optional/rsc" ]; then
    echo "❌ Error: src/optional/rsc directory not found"
    exit 1
fi

# Create lib/rsc directory if it doesn't exist
mkdir -p src/lib/rsc

# Copy RSC files
echo "📁 Copying RSC files..."
cp src/optional/rsc/index.ts src/lib/rsc/index.ts
cp src/optional/rsc/server-actions.ts src/lib/rsc/server-actions.ts
echo "   ✓ Copied RSC utilities to src/lib/rsc/"

echo ""
echo "✅ RSC utilities setup complete!"
echo ""
echo "Usage:"
echo "  import { isServer, isClient, cache, serverOnly } from '@/lib/rsc';"
echo ""
echo "Note: Full RSC support requires Next.js App Router."
echo "These utilities help prepare your codebase for migration."
echo ""
echo "To disable RSC utilities, run: ./scripts/disable-rsc.sh"
