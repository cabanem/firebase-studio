# Configure Firebase for Ruby with Workato extension

## Objective

We need to set up a Workato connector development environment inside Google Firebase Studio (`studio.girebase.google.com`)

**Plan**
1. Verify what's enabled in your workspace
2. Declare a reproducible toolchain with **Nix**
3. Install **Ruby**, **Bundler**, **workato-connector-sdk** (all with native build prerequisites)

--- 

## Configuration

### 1 - Inspect what's enabled
- Open the Terminal and run the command below:
  
  ```bash
  ruby -v
  gem -v
  bundler -v || bundle -v
  
  ls -la .idx || echo "no .idx/ directory found"
  ```
  
### 2 - Declare a reproducible toolchain in `.idx/dev.nix`
**Steps**
1. Create or edit `.idx/dev.nix` at project root and pass in the code below.
2. After saving the file, rebuild the environment
  - Press Ctrl/Cmd + Shift + P &rarr; `Firebase Studio: Rebuild Environment`

**Notes**
- Upadting your `dev.nix` file with the code below will:
  - Select a stable Nix channel
  - Install:
    - **Ruby 3.1** (supported by Workato SDK)
    - Bundler
    - Compilers
    - Native libs required by transitive dependencies (`charlock_holmes`, `nokogiri`)
  - Configure Bundler, Launchy for headless execution within the IDE
- Why these choices?
  - Firebase Studio manages system dependencies through Nix packages
  - ICU (that is, `pkgs.icu`) is required by `charlock_holmes`, and `charlock_holmes` is a Workato SDK runtime dependency.
    - Workato gem docs explicitly require pointing to ICU if auto-detect fails
    - Set `BUNDLE_BUILD__CHARLOCK_HOLMES` so that Bundler passes `--with-icu-dir=..` during compilation
  - `libxml2`/`libxslt`/`zlib` help when `nokogiri` compiles from source (can occur in some CI/containers)
  - BUNDLE_PATH ensures gems install into the repository (`vendor/bundle`) and persist with the project.

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
### 3 - Initialize the project
  1. In the terminal, initialize a Gemfile, add the SDK and common test deps
    - The Workato connector SDK requires Ruby >= 2.7.6 and depends on a number of gems (e.g., `charlock_holmes`, `nokogiri`, `rack`, `webrick`, etc.)
    - Bundler will resolve and install them once system libs are present
     
  ```bash
  bundle init
  bundle add workato-connector-sdk rspec vcr webmock timecop byebug
  ```

  2. Confirm install
     
  ```bash
  bundle exec workato help
  ```

### 4 - Create a skeleton connector
  1. Create a new connector folder structure with specs, fixtures, etc
     
  ```bash
  bundle exec workato new connectors/my_connector
  cd connectors/my_connector
  git init
  ```
  2. Create encrypted settings and master key in the project
     
  ```bash
  EDITOR="nano" bundle exec workato edit settings.yaml.enc
  ```
### 5 - Verify
Confirm that these commands succeed:
```bash
ruby -v
bundle exec workato -v
bundle exec workato help
```
--- 
## Additional Notes

### Handle OAuth in the headless broswer environment

The SDK uses the gem, `Launchy` to open a browser for OAuth code grant. In Cloud IDEs with no GUI, Luanchy can fail unless you force "dry run" (printing URL in the terminal).
  1. In `.idx/dev.nix`, confirm `LAUNCH_DRY_RUN=true` to ensure **copy/paste URL flow**
  2. Start the OAuth flow with the command below, then copy the URL into a browser, and complete consent

  ```bash
  bundle exec workato oauth2
  ```
### Everyday commands
**Verify the toolchain (after rebuild)**
  ```bash
  ruby -v && bundle -v && gem env
  ```
**Install/update gems (persisted in vendor/bundle)**
  ```bash
  bundle install
  bundle update
  ```
**Run the Workato CLI**
  ```bash
  bundle exec workato help
  bundle exec workato exec actions.example_action.execute --input=fixtures/actions/example/input.json
  ```
**Run tests**
  ```bash
  bundle exec rspec
  ```
### Commit to Git

| Component | Description | Commit?
| --- | --- | -- |
| `.idx`/`dev.nix` | environment contract | ✓ |
| `Gemfile`, `Gemfile.lock`, `.bundle/config` | contains `BUNDLE_PATH: vendor/bundle` | ✓ |
| `vendor/bundle` | do not commit, let Bundler restore from `Gemfile.lock` | :x: |
| `master.key` | created when settings are encrypted | :x: |

### Troubleshooting

| Problem | Mitigation |
| --- | --- |
| `Charlock Holmes` won't compile | Check your `dev.nix` and confirm that <ul> <li> `ICU` is present </li> <li> `Bundler` (`BUNDLE_BUILD__CHARLOCK_HOLMES=`) flags are present <ul> <li> `--with-icu-dir=${pkgs.icu.dev}"`</li> <li>  `--with-icu-dir` </li> <li>`--with-cxxflags=-std=c++11` </li> </li> </ul> |
| `Nokogiri` won't build properly | Check your `dev.nix` to be sure that you've added `libxml2`, `libxsit`, `zlib` |
| I can't use `apt-get` | Firebase Studio uses **Nix**; declare packages in `.idx/dev.nix` |
| Where is the editor support for Ruby? | <ul> <li>The preferred editor is `Ruby LSP (Shopify)`. Fetch it from VSX/Studio.</li> <li> If this is unavailable, the legacy `rebornix.ruby` extension is a viable fallback.</li> </uL> |


| How do I rebuild the workspace? | After editing `.idx/dev.nix`, run `Firebase Studio: Rebuild Environment` from the command palette |

---

## References
[Firebase Studio](https://firebase.google.com/docs/studio)
[Workato Connector SDK (repo)](https://github.com/workato/workato-connector-sdk)
[Gem - Workato Connector SDK](https://rubygems.org/gems/workato-connector-sdk/versions/1.3.14?locale=en)
[Gem - Charlock Holmes (repo)](https://github.com/brianmario/charlock_holmes)
[Gem - Nokogiri](https://nokogiri.org/index.html)
[Bundler](https://bundler.io/man/bundle-config.1.html)
