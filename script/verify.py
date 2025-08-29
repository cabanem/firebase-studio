#!/usr/bin/env bash
set -euo pipefail

: "${BUNDLE_PATH:=vendor/bundle}"

echo "==> Working directory: $(pwd)"
echo "==> Ruby version: $(ruby -v)"
echo "==> Bundler version: $(bundle -v)"

echo "==> Bundler config"
bundle config

expected_abs="$(ruby -e 'puts File.expand_path(ENV.fetch("BUNDLE_PATH", "vendor/bundle"))')"
echo "==> Expected install root: $expected_abs"

echo "==> Installed gem paths:"
paths="$(bundle list --paths)"
echo "${paths}"

# Fail if any installed gem path is not under expected_abs
nonmatching="$(printf '%s\n' "${paths}" | awk -v root="${expected_abs}" 'length($0)>0 && index($0, root)!=1 {print}')"
if [[ -n "${nonmatching}" ]]; then
  echo "❌ Found gems not under ${expected_abs}:"
  printf '%s\n' "${nonmatching}"
  exit 2
else
  echo "✅ All gems are under ${expected_abs}"
fi

echo "==> bundle doctor"
bundle doctor

echo "==> Auditing native extension linkage (ldd)"
bad=0
while IFS= read -r so; do
  if ldd "$so" | grep -qE '/usr/(lib|local)'; then
    echo "❌ Non-pinned linkage detected in: $so"
    ldd "$so" | grep -E '/usr/(lib|local)' || true
    bad=1
  fi
done < <(find "${expected_abs}" -type f -name '*.so' 2>/dev/null || true)
if [[ $bad -eq 1 ]]; then
  echo "❌ Found native extensions linked to /usr/lib or /usr/local. Check your dev.nix and Bundler build flags."
  exit 3
else
  echo "✅ Native extensions link only to pinned libraries (no /usr/lib or /usr/local)."
fi

# Optional diagnostics for Nokogiri (if present)
ruby - <<'RUBY'
begin
  require 'nokogiri'
  puts "==> Nokogiri VERSION_INFO"
  puts Nokogiri::VERSION_INFO
rescue LoadError
  puts "==> Nokogiri not in bundle; skipping."
end
RUBY

# Check that vendor/cache exists and has content
if [[ -d vendor/cache ]] && ls vendor/cache/*.gem >/dev/null 2>&1; then
  echo "✅ vendor/cache populated."
else
  echo "⚠️  vendor/cache is empty; consider running: bundle cache --all --all-platforms"
fi

echo "✅ Verify complete."
