#!/bin/bash
# Disable Server-Side Rendering (SSR)
# Usage: ./scripts/disable-ssr.sh

set -e

echo "🔄 Disabling SSR..."

# Remove SSR files from root
echo "🗑️  Removing SSR files..."

[ -f "server.ts" ] && rm server.ts && echo "   ✓ Removed server.ts"
[ -f "vite.config.ssr.ts" ] && rm vite.config.ssr.ts && echo "   ✓ Removed vite.config.ssr.ts"
[ -f "src/entry-server.tsx" ] && rm src/entry-server.tsx && echo "   ✓ Removed entry-server.tsx"
[ -f "src/entry-client.tsx" ] && rm src/entry-client.tsx && echo "   ✓ Removed entry-client.tsx"

# Remove SSR outlet from index.html
if grep -q "<!--ssr-outlet-->" index.html; then
    echo "📝 Updating index.html..."
    sed -i.bak 's/<!--ssr-outlet-->//' index.html
    rm -f index.html.bak
    echo "   ✓ Removed SSR outlet from index.html"
fi

# Remove SSR scripts from package.json
echo "📝 Removing SSR scripts from package.json..."
node -e "
const fs = require('fs');
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));

delete pkg.scripts['dev:ssr'];
delete pkg.scripts['build:ssr'];
delete pkg.scripts['build:client'];
delete pkg.scripts['build:server'];
delete pkg.scripts['preview:ssr'];

fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2) + '\n');
"
echo "   ✓ Removed SSR scripts"

echo ""
echo "✅ SSR disabled!"
echo ""
echo "Note: SSR dependencies (express, compression, sirv) are still installed."
echo "Run 'bun remove express compression sirv' to remove them."
echo ""
echo "To re-enable SSR, run: ./scripts/setup-ssr.sh"
