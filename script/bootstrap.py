#!/usr/bin/env bash
set -euo pipefail

# Known, repeatable install locations
: "${BUNDLE_PATH:=vendor/bundle}"
: "${BUNDLE_BIN:=bin}"

echo "==> Working directory: $(pwd)"
echo "==> Ruby version: $(ruby -v || echo 'ruby not found')"
echo "==> Bundler version: $(bundle -v || echo 'bundler not found')"

if [[ ! -f "Gemfile" ]]; then
  echo "❌ Gemfile not found in $(pwd)"
  exit 1
fi

# If there is no lockfile yet, do an initial resolve (network) to create one.
if [[ ! -f "Gemfile.lock" ]]; then
  echo "==> No Gemfile.lock found. Performing initial resolve to create lockfile..."
  bundle install --path "$BUNDLE_PATH"
fi

echo "==> Ensuring lockfile supports common Linux platforms"
bundle lock --add-platform ruby x86_64-linux aarch64-linux || true

echo "==> Adding checksums to lockfile (Bundler 2.6+)"
bundle lock --add-checksums || true

echo "==> Vendoring all gems for offline/known-source installs"
bundle cache --all --all-platforms

# Stricter deployment behavior once a lockfile exists
export BUNDLE_DEPLOYMENT="${BUNDLE_DEPLOYMENT:-true}"
export BUNDLE_FROZEN="${BUNDLE_FROZEN:-true}"

echo "==> Installing from local cache into $BUNDLE_PATH"
if ! bundle install --local --path "$BUNDLE_PATH"; then
  echo "==> Local cache incomplete. Fetching from network once, then caching and retrying..."
  bundle install --path "$BUNDLE_PATH"
  bundle cache --all --all-platforms
  bundle install --local --path "$BUNDLE_PATH"
fi

echo "==> Generating binstubs in $BUNDLE_BIN (optional)"
bundle binstubs --all --path "$BUNDLE_BIN" || true

abs_bundle_path="$(ruby -e 'puts File.expand_path(ENV.fetch("BUNDLE_PATH", "vendor/bundle"))')"
echo "✅ Bootstrap complete. Gems installed under: $abs_bundle_path"
