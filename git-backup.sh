#!/bin/bash
# InstantTransmission Auto Backup to GitHub
# Quick script to commit and push all changes

cd "/mnt/vulkan2/Creation/Python/Instant Transmission"

echo "=========================================="
echo "  InstantTransmission GitHub Backup"
echo "=========================================="
echo ""

# Show what changed
echo "📝 Changes detected:"
git status --short

echo ""
echo "🔄 Adding all changes..."
git add .

echo ""
echo "💾 Creating backup commit..."
git commit -m "Backup: $(date '+%Y-%m-%d %H:%M:%S')"

echo ""
echo "☁️  Pushing to GitHub..."
git push

echo ""
echo "✅ Backup complete!"
echo ""
echo "View at: https://github.com/Sky-Wright/InstantTransmission"
