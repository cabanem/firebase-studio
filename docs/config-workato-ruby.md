# Configure Firebase Studio for Ruby + Workato Connector SDK

## Objective

Set up a Workato connector development environment inside **Google Firebase Studio** (`studio.firebase.google.com`).

**Plan**
1. Verify what’s enabled in your workspace.
2. Declare a reproducible toolchain with **Nix**.
3. Install **Ruby**, **Bundler**, and **workato-connector-sdk** (with native build prerequisites).

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
- Why these choices?
  - Firebase Studio manages system dependencies through **Nix** packages.
  - ICU (`pkgs.icu`) is required by `charlock_holmes`, a Workato SDK runtime dependency.
    - If auto-detection fails, set `BUNDLE_BUILD__CHARLOCK_HOLMES` so Bundler passes `--with-icu-dir=…` during compilation.
  - `libxml2`/`libxslt`/`zlib` help when `nokogiri` compiles from source (common in CI/containers).
  - `BUNDLE_PATH` ensures gems install into the repository (`vendor/bundle`) and persist with the project.

**dev.nix**
```nix
# .idx/dev.nix
{ pkgs, ... }: {

  # Choose an appropriate nixpkgs channel.
  # You may switch to "stable-24.05" or "unstable" if you need newer packages.
  channel = "stable-24.05";

  # System tools and libraries needed to build Ruby gems with native extensions.
  packages = [
    pkgs.ruby_3_1

    # Useful and sometimes necessary tools for native gems
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

    # optional: certificate bundle for TLS if you make HTTPS calls locally
    pkgs.cacert
  ];

  # Editor extensions from Open VSX
  # Prefer Ruby LSP, fall back to the older "rebornix.ruby" if needed.
  idx.extensions = [
    "Shopify.ruby-lsp" # VS Code Ruby LSP (if available in Open VSX)
    "rebornix.ruby"    # fallback, legacy Ruby extension
  ];

  # Environment vars for Bundler and headless browser flows
  env = {
    # Install gems into the project (persisted) instead of global/system gem dir
    BUNDLE_PATH = "vendor/bundle";
    BUNDLE_JOBS = "4";
    BUNDLE_RETRY = "3";

    # Ensure charlock_holmes picks up ICU in this Nix env:
    # Bundler reads env var keys with double underscore as gem-specific build flags.
    BUNDLE_BUILD__CHARLOCK_HOLMES = "--with-icu-dir=${pkgs.icu.dev}";

    # In a headless IDE, Launchy shouldn't try to open a graphical browser.
    # This makes OAuth URLs print in the terminal instead of failing.
    LAUNCHY_DRY_RUN = "true";
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
