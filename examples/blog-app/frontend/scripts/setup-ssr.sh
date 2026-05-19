#!/bin/bash
# Enable Server-Side Rendering (SSR) for the boilerplate
# Usage: ./scripts/setup-ssr.sh

set -e

echo "🚀 Setting up SSR..."

# Check if optional SSR files exist
if [ ! -d "src/optional/ssr" ]; then
    echo "❌ Error: src/optional/ssr directory not found"
    exit 1
fi

# Install SSR dependencies
echo "📦 Installing SSR dependencies..."
if command -v bun &> /dev/null; then
    bun add express compression sirv
    bun add -d @types/express @types/compression tsx
else
    npm install express compression sirv
    npm install -D @types/express @types/compression tsx
fi

# Copy SSR files to their locations
echo "📁 Copying SSR files..."

# Copy server.ts to root
cp src/optional/ssr/server.ts ./server.ts
echo "   ✓ Copied server.ts"

# Copy vite.config.ssr.ts to root
cp src/optional/ssr/vite.config.ssr.ts ./vite.config.ssr.ts
echo "   ✓ Copied vite.config.ssr.ts"

# Copy entry files to src
cp src/optional/ssr/entry-server.tsx ./src/entry-server.tsx
cp src/optional/ssr/entry-client.tsx ./src/entry-client.tsx
echo "   ✓ Copied entry files"

# Update index.html with SSR outlet
if ! grep -q "<!--ssr-outlet-->" index.html; then
    echo "📝 Updating index.html..."
    sed -i.bak 's/<div id="root"><\/div>/<div id="root"><!--ssr-outlet--><\/div>/' index.html
    rm -f index.html.bak
    echo "   ✓ Added SSR outlet to index.html"
fi

# Add SSR scripts to package.json
echo "📝 Adding SSR scripts to package.json..."
node -e "
const fs = require('fs');
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));

pkg.scripts['dev:ssr'] = 'tsx server.ts';
pkg.scripts['build:ssr'] = 'bun run build:client && bun run build:server';
pkg.scripts['build:client'] = 'vite build --outDir dist/client';
pkg.scripts['build:server'] = 'vite build --outDir dist/server --ssr src/entry-server.tsx --config vite.config.ssr.ts';
pkg.scripts['preview:ssr'] = 'NODE_ENV=production tsx server.ts';

fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2) + '\n');
"
echo "   ✓ Added SSR scripts"

echo ""
echo "✅ SSR setup complete!"
echo ""
echo "Available commands:"
echo "  bun run dev:ssr      - Start SSR dev server"
echo "  bun run build:ssr    - Build for SSR production"
echo "  bun run preview:ssr  - Preview SSR production build"
echo ""
echo "To disable SSR, run: ./scripts/disable-ssr.sh"
