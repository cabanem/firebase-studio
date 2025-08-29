# Configure Firebase Studio for Ruby + Workato Connector SDK

## Objective

Set up a Workato connector development environment inside **Google Firebase Studio** (`studio.firebase.google.com`).

**Plan**
1. Verify what’s enabled in your workspace.
2. Declare a reproducible toolchain with **Nix**.
3. Install **Ruby**, **Bundler**, and **workato-connector-sdk** (with native build prerequisites).
4. Make installs **deterministic** and **auditable** (known locations, vendored gems, lockfile hygiene).
5. Provide verification scripts and CI guardrails.

---

## Configuration

### 1 — Inspect what’s enabled
Open the **Terminal** and run:

```bash
ruby -v
gem -v
bundler -v || bundle -v

ls -la .idx || echo "no .idx/ directory found"
```

### 2 — Declare a reproducible toolchain in `.idx/dev.nix`

**Steps**
1. Create or edit `.idx/dev.nix` at the project root and use the code below.
2. After saving the file, rebuild the environment:
   - Press **Ctrl/Cmd + Shift + P** → `Firebase Studio: Rebuild Environment`

**Notes**
- Updating your `dev.nix` file with the code below will:
  - Select a stable Nix channel.
  - Install:
    - **Ruby 3.1** (supported by the Workato SDK)
    - Bundler
    - Compilers
    - Native libraries required by transitive dependencies (e.g., `charlock_holmes`, `nokogiri`)
  - Configure Bundler and Launchy for headless execution within the IDE.
- Rationale
  - Firebase Studio manages system dependencies through **Nix** packages.
  - ICU (`pkgs.icu`) is required by `charlock_holmes`, a Workato SDK runtime dependency.
    - If auto-detection fails, set `BUNDLE_BUILD__CHARLOCK_HOLMES` so Bundler passes `--with-icu-dir=…` during compilation.
  - `libxml2`/`libxslt`/`zlib` help when `nokogiri` compiles from source (common in CI/containers).
  - `BUNDLE_PATH` ensures gems install into the repository (`vendor/bundle`) and persist with the project.

**dev.nix**
```nix
# .idx/dev.nix
{ pkgs, ... }: {

  # Choose an appropriate nixpkgs channel, "unstable" for newest packages
  channel = "stable-24.05";

  # System tools and libraries needed to build Ruby gems with native extensions.
  packages = [
    pkgs.ruby_3_1

    # For native gems
    pkgs.bundler
    pkgs.git
    pkgs.gcc
    pkgs.gnumake
    pkgs.pkg-config

    # Native libraries for transitive deps:
    # - charlock_holmes  -> ICU
    # - nokogiri         -> libxml2, libxslt (and zlib)
    pkgs.icu
    pkgs.libxml2
    pkgs.libxslt
    pkgs.zlib
    pkgs.openssl

    # Certificate bundle for TLS (i.e., local HTTP calls)
    pkgs.cacert
  ];

  # Editor extensions from Open VSX
  idx.extensions = [
    "Shopify.ruby-lsp" # VS Code Ruby LSP (if available in Open VSX)
    "rebornix.ruby"    # fallback, legacy Ruby extension
  ];

  # Environment vars for Bundler and headless browser flows
  env = {
    # Install gems into the project (persisted) instead of global/system gem dir
    BUNDLE_PATH = "vendor/bundle";
    BUNDLE_BIN = "bin";
    BUNDLE_JOBS = "4";
    BUNDLE_RETRY = "3";

    # === Native builds use our pinned Nix libraries ===

    # Nokogiri: compile against system libxml2/libxslt from Nix (not vendor copies)
    NOKOGIRI_USE_SYSTEM_LIBRARIES = "1";
    BUNDLE_BUILD__NOKOGIRI =
      "--use-system-libraries " +
      "--with-xml2-include=${pkgs.libxml2.dev}/include/libxml2 " +
      "--with-xml2-lib=${pkgs.libxml2.out}/lib " +
      "--with-xslt-include=${pkgs.libxslt.dev}/include " +
      "--with-xslt-lib=${pkgs.libxslt.out}/lib";

    # charlock_holmes: link to Nix ICU
    BUNDLE_BUILD__CHARLOCK_HOLMES = "--with-icu-dir=${pkgs.icu.dev}";

    # In a headless IDE, Launchy shouldn't open a graphical browser (OAuth URLs print in the terminal instead of failing.)
    LAUNCHY_DRY_RUN = "true";

    # === Optional (enable after Gemfile.lock exists) ===
    # BUNDLE_DEPLOYMENT = "true";  # stricter, uses vendor/bundle; fails on lockfile drift
    # BUNDLE_FROZEN     = "true";  # refuse to change Gemfile.lock
    # BUNDLE_LOCKFILE_CHECKSUMS = "true"; # Bundler 2.6+: stronger supply-chain checks
    # BUNDLE_FORCE_RUBY_PLATFORM = "true"; # prefer compiling native gems locally
  };

  # (Optional) Enable web previews if you have a local server to run.
  # idx.previews = {
  #   enable = true;
  #   previews.web = {
  #     manager = "web";
  #     command = ["bash" "-lc" "rackup -p $PORT -o 0.0.0.0"];
  #   };
  # };
}
```

### 3 — Initialize the project
1. In the terminal, initialize a Gemfile and add the SDK plus common test dependencies.
   - The Workato Connector SDK requires Ruby >= 2.7.6 and depends on several gems (e.g., `charlock_holmes`, `nokogiri`, `rack`, `webrick`, etc.).
   - Bundler will resolve and install them once system libraries are present.

   ```bash
   bundle init
   bundle add workato-connector-sdk rspec vcr webmock timecop byebug
   ```

2. Confirm the install:

   ```bash
   bundle exec workato help
   ```

### 4 — Create a skeleton connector
1. Create a new connector folder structure with specs, fixtures, etc.

   ```bash
   bundle exec workato new connectors/my_connector
   cd connectors/my_connector
   git init
   ```

2. Create encrypted settings and a master key in the project:

   ```bash
   EDITOR="nano" bundle exec workato edit settings.yaml.enc
   ```

### 5 — Verify
Confirm that these commands succeed:

```bash
ruby -v
bundle exec workato -v
bundle exec workato help
```

## Make installs deterministic (i.e., in known locations)
The following steps ensure that gems and native extensions always install to known paths and compile against pinned libraries, with no surprises across machines.

### 6 — Vendor and lock gems
Run these to make installs reproducible and network-optional:
```bash
# Add platforms once so the lockfile works across x86_64 and arm64 Linux
bundle lock --add-platform ruby x86_64-linux aarch64-linux

# Backfill checksums for existing lockfiles (Bundler 2.6+)
bundle lock --add-checksums

# Cache every dependency into vendor/cache (including all platforms)
bundle cache --all --all-platforms
```
> `vendor/cache` will contain the .gem files so teammates/CI can install offline and from a known source.
> After the first successful install (Gemfile.lock exists), consider enabling stricter settings by uncommenting in .idx/dev.nix:
> - `BUNDLE_DEPLOYMENT=true`
> - `BUNDLE_FROZEN=true`

### 7 - One-commmand bootstrap
1. Create script/bootstrap so every developer and CI uses the same bootstrap:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Ensure lockfile captures all relevant platforms & checksums
bundle lock --add-platform ruby x86_64-linux aarch64-linux
bundle lock --add-checksums

# Vendor dependencies to known location
bundle cache --all --all-platforms

# Install exactly what's in Gemfile.lock, from the cache, into vendor/bundle
bundle install --local
```
2. Then run:
```bash
chmod +x script/bootstrap
./script/bootstrap
```

### 8 - Verify install are in the correct location
1. Add script/verify to assert that everything landed under vendor/bundle and looks healthy:
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "== Bundler settings =="
bundle config

echo "== Paths of installed gems =="
bundle list --paths

echo "== Path of a specific gem (example: nokogiri) =="
bundle info nokogiri --path || true

echo "== Doctor =="
bundle doctor || { echo "bundle doctor found issues"; exit 1; }

echo "== Ensure everything landed under vendor/bundle =="
if bundle list --paths | grep -v "vendor/bundle" | grep -E "[^ ]"; then
  echo "❌ Found gems not under vendor/bundle"; exit 2
else
  echo "✅ All gems are under vendor/bundle"
fi
```
2. Run:
```bash
chmod +x script/verify
./script/verify
```
### 9 - Audit native linkage (optional but recommended)
1. Ensure native extensions link to Nix store paths, not /usr/lib:
```bash
#!/usr/bin/env bash
set -euo pipefail
bad=0
for so in $(find vendor/bundle -name '*.so'); do
  if ldd "$so" | grep -qE '/usr/(lib|local)'; then
    echo "❌ Non-Nix linkage: $so"
    bad=1
  fi
done
exit $bad
```
2. Also consider adding helpful checks:
```bash
# See what Nokogiri linked against
ruby -r nokogiri -e 'puts Nokogiri::VERSION_INFO'

# Inspect compile logs
find vendor/bundle -type f -name mkmf.log -print -exec sed -n '1,80p' {} \; | less
```

### 10 - CI Recipe

**For Cloud Build**
```yaml
# cloudbuild.yaml — Bootstrap and verify Workato connector with Nix in Cloud Build
# Trigger via Cloud Build with your repo as the source.
steps:
  - name: 'nixos/nix:2.18.1'
    entrypoint: bash
    args:
      - -lc
      - |
        set -euo pipefail
        export BUNDLE_PATH=vendor/bundle
        export BUNDLE_BIN=bin
        export NOKOGIRI_USE_SYSTEM_LIBRARIES=1

        # Launch a Nix shell that mirrors the dev toolchain declared in .idx/dev.nix
        nix shell           nixpkgs/nixos-24.05#ruby_3_1           nixpkgs/nixos-24.05#bundler           nixpkgs/nixos-24.05#gcc           nixpkgs/nixos-24.05#gnumake           nixpkgs/nixos-24.05#pkg-config           nixpkgs/nixos-24.05#icu           nixpkgs/nixos-24.05#libxml2           nixpkgs/nixos-24.05#libxslt           nixpkgs/nixos-24.05#zlib           nixpkgs/nixos-24.05#openssl           nixpkgs/nixos-24.05#cacert           --command bash -lc '
            set -euo pipefail
            # Resolve include/lib paths from pkg-config inside the Nix shell
            LIBXML2_INC="$(pkg-config --variable=includedir libxml-2.0)/libxml2"
            LIBXML2_LIB="$(pkg-config --variable=libdir libxml-2.0)"
            XSLT_INC="$(pkg-config --variable=includedir libxslt)"
            XSLT_LIB="$(pkg-config --variable=libdir libxslt)"
            ICU_DEV="$(pkg-config --variable=prefix icu-i18n)"

            export BUNDLE_BUILD__NOKOGIRI="--use-system-libraries --with-xml2-include=${LIBXML2_INC} --with-xml2-lib=${LIBXML2_LIB} --with-xslt-include=${XSLT_INC} --with-xslt-lib=${XSLT_LIB}"
            export BUNDLE_BUILD__CHARLOCK_HOLMES="--with-icu-dir=${ICU_DEV}"

            chmod +x script/bootstrap script/verify || true
            ./script/bootstrap
            ./script/verify
          '
```


### 11 - Stict Nix pinning
To achieve bit-for-bit reproducibility, pin nixpkgs to a commit and draw packages from that set. For example:
```bash
# .idx/dev.nix (snippet)
{ pkgs, ... }:
let
  pinnedPkgs = import (builtins.fetchTarball
    "https://github.com/NixOS/nixpkgs/archive/<commit>.tar.gz") {};
in {
  packages = [
    pinnedPkgs.ruby_3_1
    pinnedPkgs.bundler
    pinnedPkgs.gcc pinnedPkgs.gnumake pinnedPkgs.pkg-config
    pinnedPkgs.icu pinnedPkgs.libxml2 pinnedPkgs.libxslt pinnedPkgs.zlib pinnedPkgs.openssl
    pinnedPkgs.cacert
  ];
}
```
---

## Additional Notes

### Handle OAuth in a headless browser environment

The SDK uses the `launchy` gem to open a browser for OAuth code grant. In cloud IDEs with no GUI, Launchy can fail unless you force a “dry run” (which prints the URL in the terminal).

1. In `.idx/dev.nix`, confirm `LAUNCHY_DRY_RUN=true` to enable a **copy/paste URL** flow.
2. Start the OAuth flow, copy the printed URL into a local browser, complete consent, and return to the terminal if prompted:

   ```bash
   bundle exec workato oauth2
   ```

### Everyday commands

**Verify the toolchain (after rebuild):**
```bash
ruby -v && bundle -v && gem env
```

**Install/update gems (persisted in `vendor/bundle`):**
```bash
bundle install
bundle update
```

**Run the Workato CLI:**
```bash
bundle exec workato help
bundle exec workato exec actions.example_action.execute --input=fixtures/actions/example/input.json
```

**Run tests:**
```bash
bundle exec rspec
```

### Commit to Git

| Component             | Description                                   | Commit? |
|----------------------|-----------------------------------------------|:-------:|
| `.idx/dev.nix`       | Environment contract                           |    ✓    |
| `Gemfile`, `Gemfile.lock`, `.bundle/config` | Contains `BUNDLE_PATH: vendor/bundle` |    ✓    |
| `vendor/cache` | Vendored gem tarballs for offline/known-source installs | ✓  |
| `.bundle/config` | Local machine config (redundance with env in dev.nix | ✗ |
| `vendor/bundle`      | Do not commit; let Bundler restore from `Gemfile.lock` |    ✗    |
| `master.key`         | Created when settings are encrypted            |    ✗    |

### Troubleshooting
<table>
  <thead>
    <tr>
      <th style="min-width: 150px;">Problem</th>
      <th>Mitigation</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>`charlock_holmes` won’t compile </td>
      <td> Ensure ICU is present in <code>packages</code> and verify that Bundler flag is set:<br> -<code>BUNDLE_BUILD__CHARLOCK_HOLMES="--with-icu-dir=${pkgs.icu.dev}"</code> <br> - If necessary, try <code>--with-cxxflags=-std=c++11</code></td>
    </tr>
    <tr>
      <td><code>nokogiri</code> won’t build</td>
      <td>Confirm <code>libxml2</code>, <code>libxslt</code>, and <code>zlib</code> are included in <code>packages</code></td>
    </tr>
    <tr>
      <td>I can’t use <code>apt-get</code></td>
      <td>Firebase Studio uses **Nix**; <br> declare packages in <code>.idx/dev.nix</code></td>
    </tr>
    <tr>
      <td>Editor support for Ruby </td>
      <td>Prefer **Ruby LSP (Shopify)** via Open VSX/Studio; <br> If unavailable, use the legacy <code>rebornix.ruby</code> extension</td>
    </tr>
    <tr>
      <td>How do I rebuild the workspace? </td>
      <td>Run **`Firebase Studio: Rebuild Environment`** from the Command Palette</td>
    </tr>
  </tbody>
</table>

---

## References
- [Firebase Studio](https://firebase.google.com/docs/studio)
- [Workato Connector SDK (repo)](https://github.com/workato/workato-connector-sdk)
- [Gem – Workato Connector SDK](https://rubygems.org/gems/workato-connector-sdk/)
- [Gem – charlock_holmes (repo)](https://github.com/brianmario/charlock_holmes)
- [Nokogiri](https://nokogiri.org/index.html)
- [Bundler: `bundle config`](https://bundler.io/man/bundle-config.1.html)
