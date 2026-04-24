#!/bin/bash
# Package each Lambda's source + pip dependencies into a deployable zip.
# CDK reads these zips (infra/lambda_packages/{name}.zip) via from_asset().
#
# Usage:
#   ./scripts/package_lambdas.sh
#
# Run before `cdk deploy`. Mirrors the packaging step in .github/workflows/deploy.yml
# so local deploys and CI deploys behave identically.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PACKAGES_DIR="$REPO_ROOT/infra/lambda_packages"
LAMBDAS=(entry retrieval story_generation image_generation pdf_assembly)

echo "Packaging Lambdas..."
rm -rf "$PACKAGES_DIR"
mkdir -p "$PACKAGES_DIR"

for lambda in "${LAMBDAS[@]}"; do
    echo "--- $lambda ---"
    BUILD_DIR=$(mktemp -d)

    # Install pip dependencies into the build dir (if requirements.txt exists).
    # --platform/--only-binary forces Linux ARM64 wheels even when running
    # pip on macOS — otherwise we'd bundle .dylib/.so files compiled for
    # the build machine's OS, which Lambda can't load.
    REQ_FILE="$REPO_ROOT/lambdas/$lambda/requirements.txt"
    if [ -s "$REQ_FILE" ]; then
        pip install \
            --platform manylinux2014_aarch64 \
            --implementation cp \
            --python-version 3.11 \
            --only-binary=:all: \
            --upgrade \
            --target "$BUILD_DIR" \
            -r "$REQ_FILE" \
            --quiet
    fi

    # Copy Lambda source (handler.py, service.py, config files, etc.).
    # Skip tests/ — no reason to deploy them.
    (cd "$REPO_ROOT/lambdas/$lambda" && \
        find . -maxdepth 1 -mindepth 1 ! -name tests ! -name __pycache__ \
        -exec cp -r {} "$BUILD_DIR/" \;)

    # Zip (from inside BUILD_DIR so paths are relative, as Lambda requires).
    (cd "$BUILD_DIR" && zip -r -q "$PACKAGES_DIR/$lambda.zip" .)
    rm -rf "$BUILD_DIR"

    SIZE=$(du -h "$PACKAGES_DIR/$lambda.zip" | cut -f1)
    echo "  -> $PACKAGES_DIR/$lambda.zip ($SIZE)"
done

echo "Done. CDK will pick up these zips via from_asset()."