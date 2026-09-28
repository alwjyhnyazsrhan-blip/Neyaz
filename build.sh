#!/usr/bin/env bash
# ==============================================================================
# Webook Auto-Booker - Render Native Environment Build Script
# ==============================================================================
set -o errexit

echo "🚀 [1/3] Updating pip and installing Python libraries..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🌐 [2/3] Installing Playwright Chromium browser..."
playwright install chromium

echo "✅ [3/3] Ready for production on Render!"
