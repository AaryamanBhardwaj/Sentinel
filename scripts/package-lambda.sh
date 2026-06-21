#!/usr/bin/env bash
set -euo pipefail

# Builds dist/lambda.zip containing the backend code + dependencies + corpus.
# Run from the project root: ./scripts/package-lambda.sh

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/dist/lambda-build"
OUTPUT="$PROJECT_ROOT/dist/lambda.zip"

echo "==> Cleaning previous build..."
rm -rf "$BUILD_DIR" "$OUTPUT"
mkdir -p "$BUILD_DIR" "$PROJECT_ROOT/dist"

echo "==> Installing Python dependencies..."
pip install \
  --target "$BUILD_DIR" \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.11 \
  --only-binary=:all: \
  -r "$PROJECT_ROOT/backend/requirements.txt" \
  --quiet 2>/dev/null || \
pip install \
  --target "$BUILD_DIR" \
  -r "$PROJECT_ROOT/backend/requirements.txt" \
  --quiet

echo "==> Copying backend code..."
cp -r "$PROJECT_ROOT/backend" "$BUILD_DIR/backend"

echo "==> Copying corpus (patterns + embeddings)..."
cp -r "$PROJECT_ROOT/corpus" "$BUILD_DIR/corpus"

echo "==> Cleaning up unnecessary files..."
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -name "*.pyc" -delete 2>/dev/null || true

echo "==> Creating zip..."
cd "$BUILD_DIR"
zip -r "$OUTPUT" . -x "*.pyc" -q

SIZE=$(du -sh "$OUTPUT" | cut -f1)
echo "==> Built $OUTPUT ($SIZE)"
