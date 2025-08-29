# Firebase Studio for Ruby w/Workato Connector SDK -- Zero to Setup 

## Objective
Set up a Workato connector development environment using Google's browser-based IDE, **Firebase Studio** (`studio.firebase.google.com`).
The environment must be a repeatable, team‑shareable. 

We need to:
* Install Ruby (pinned to a modern version compatible with the SDK),
* Build tools and native libraries that Ruby gems often need,
* Install the `workato-connector-sdk` gem and test tooling (RSpec, VCR),
* Generate a **checked‑in** environment config so any teammate who opens the workspace gets the same setup automatically.

> **Why these steps?**
> Firebase Studio workspaces run on a Linux VM and are configured declaratively with a `.idx/dev.nix` file. Anything we “apt-get” manually isn’t guaranteed to persist; defining it in `dev.nix` is the supported, reproducible way.

---

## 0) What you’re using (quick orientation)

* **Firebase Studio** is Google’s web‑based IDE (Project IDX graduated into it) that uses Nix to describe and reproduce the development environment via `.idx/dev.nix`. We can add packages, environment variables, preview commands, and even services there. 
* “Manual installs” inside the VM are **not** reliably persistent between sessions; define what you need in `dev.nix` instead. ([Firebase][5])

---
## Process
### 1) Create/open a Firebase Studio workspace

1. Go to **studio.firebase.google.com** and sign in with a Google account.
2. Create a **Blank** workspace.
3. In the left file explorer, if a folder called `.idx` does not exist, create it and add a file inside it named **`dev.nix`**. This is the workspace’s environment recipe. 

---

### 2) Paste this `dev.nix`

> This file declares Ruby, common native build deps, and bootstraps the SDK and test tools into the repo (so they persist with the code).

```nix
{ pkgs, ... }: {
  # Pick a modern channel so you get recent runtimes.
  channel = "stable-24.11";

  # System packages for Ruby and common native extensions.
  packages = [
    pkgs.ruby_3_2          # Ruby ≥ 2.7.6 required by the SDK; Ruby 3.2 is a safe modern choice
    pkgs.git
    pkgs.openssl
    pkgs.zlib
    pkgs.libffi
    pkgs.pkg-config
    pkgs.libxml2           # helpful if gems like nokogiri show up
    pkgs.libxslt
    pkgs.icu
    pkgs.gcc
    pkgs.gnumake
    pkgs.cacert
    pkgs.ngrok             # optional, handy for OAuth callback tunneling
  ];

  # Make locally generated binstubs (./bin/workato, ./bin/rspec) auto-resolve.
  env = {
    PATH = [ "./bin" ];
  };

  # First-time bootstrap: install bundler + SDK + test libs into the repo.
  # These files live in the project, so they persist and are shareable.
  idx = {
    extensions = ["shopify.ruby-lsp" ];
    previews = {
      enable = false;
    };
    workspace = {
      onCreate = {
        setup-workato = ''
          set -euxo pipefail
          gem update --system --no-document || true
          gem install --no-document bundler
    
          # Initialize a simple Gemfile if none exists
          if [ ! -f Gemfile ]; then
            cat > Gemfile <<'GEMFILE'
    source "https://rubygems.org"
    
    gem "workato-connector-sdk", "~> 1.3"  # latest line as of Aug 2025 is 1.3.x
    gem "rspec", "~> 3.13"
    gem "vcr", "~> 6.2"
    gem "webmock", "~> 3.19"
    GEMFILE
          fi
    
          # Install gems into vendor/bundle inside the repo
          bundle config set path 'vendor/bundle'
          bundle install
    
          # Create runnable wrappers under ./bin/
          bundle binstubs workato-connector-sdk rspec
        '';
      };
    };
  };
}
```

**Why this works**

* `dev.nix` is the **single source of truth** for the VM packages and env variables in Firebase Studio. When teammates open the workspace and rebuild, they’ll get the same toolchain.
* The SDK gem requires **Ruby ≥ 2.7.6**; Ruby 3.2 satisfies that while staying broadly compatible.
* Installing gems with Bundler into your **repo** (`vendor/bundle`) + generating **binstubs** puts `workato` and `rspec` under `./bin`, which we add to `PATH` via `dev.nix`. That avoids system-level installs (which don’t persist).

> After saving `dev.nix`, open the Command Palette and run **Firebase Studio: Rebuild (Hard restart)** to apply it.
> A rebuild is how we “apply” changes to the environment. 

---

### 3) Sanity checks (Terminal)

Open **Terminal → New Terminal**, then run:

```bash
ruby -v
./bin/workato
./bin/rspec -v
```

* If `./bin/workato` shows help, the SDK gem is installed correctly (the gem’s root command is `workato`). 
* If Ruby or the commands aren’t found, re-run **Rebuild Environment** and check that `./bin` exists (the `onCreate` step generates it). 

---

## 4) Create your first connector skeleton (locally, in Firebase Studio)

From the Terminal at your project root:

```bash
./bin/workato new connectors/my_first_connector
cd connectors/my_first_connector
bundle install
```

* `workato new` scaffolds a standard connector project (it also creates `Gemfile.lock` and specs scaffolding). 

You’ll now have a `connector.rb` and a `spec/` folder. Try a quick executable check:

```bash
# Example: generate unit test skeletons for everything in the connector
../../bin/workato generate test

# Run tests (if any exist), from inside the connector folder:
bundle exec rspec
```

* The CLI’s `generate` and other commands are documented in the **CLI Command Reference**.

---

## 5) Day‑to‑day development loop

Common CLI actions (run from inside connector folder unless noted):

* **Run a specific lambda** in the connector during iteration:

  ```bash
  ../../bin/workato exec actions.some_action.execute --input='input/some_action.json' --verbose
  ```

  See all options for `exec` (e.g., `--settings`, `--connection`, `--output`) in the command reference. 

* **Generate Workato schema** from JSON/CSV:

  ```bash
  ../../bin/workato generate schema --api-token "$WORKATO_API_TOKEN" --json path/to/sample.json
  ```

  (Requires a Workato API client token—more on that below.) 

* **Unit testing**: the SDK works great with **RSpec** and **VCR** to record HTTP interactions for repeatable tests. Use `bundle exec rspec` to run.

---

## 6) Push your connector into a Workato workspace

1. In Workato, create an **API Client** (Developer API) and generate an **API token** with permissions for the SDK push endpoints.

2. Back in Firebase Studio, set it for the session:

   ```bash
   export WORKATO_API_TOKEN="<paste-your-token>"
   ```

3. From connector folder, push:

   ```bash
   ../../bin/workato push --api-token "$WORKATO_API_TOKEN" \
     --folder <optional_folder_id> \
     --title "My Connector" \
     --description README.md
   ```

   (Use `--folder` to land in a specific Workato folder.) Full options are listed in the command reference. 

---

## 7) Handling connections & OAuth2 in a browser IDE

* To store **credentials** locally for testing, use encrypted settings:

  ```bash
  # Creates/edits encrypted settings.yaml.enc and a master.key
  ../../bin/workato edit settings.yaml.enc
  ```

  (The CLI’s `edit` command manages encrypted config files.)

* For **OAuth2** connectors, the CLI can emulate the Authorization Code flow and spins up a small callback webserver:

  ```bash
  ../../bin/workato oauth2 --port 45555 --ip 0.0.0.0 --https
  ```

  In cloud IDEs, 3rd‑party providers can’t reach your local `localhost` directly. If your provider **requires a public https redirect URL**, start a tunnel (we added `ngrok` to the env for convenience) and point your app’s redirect to the tunnel URL:

  ```bash
  # In one terminal
  ngrok http 45555
  # Note the https URL it prints, e.g., https://<id>.ngrok.io

  # In your OAuth app settings, set redirect URL to:
  #   https://<id>.ngrok.io/oauth/callback

  # Then run:
  ../../bin/workato oauth2 --port 45555 --ip 0.0.0.0
  ```

  See the CLI `oauth2` options for details (`--port`, `--ip`, `--https`).

> Tip: Firebase Studio “Previews” are great for app servers you run (web/Android) but aren’t always suitable as public OAuth callback endpoints from third‑party providers. Use a tunnel when you need an externally reachable HTTPS callback.

---

## 8) Team‑ready hardening & quality

1. **Check in** `.idx/dev.nix`, `Gemfile`, `Gemfile.lock`, and (if used) `vendor/bundle` is usually **not** checked in—stick with `bundle config set path 'vendor/bundle'` and let teammates run `bundle install` on rebuild.
2. Add to `.gitignore`: `vendor/`, `bin/rspec`, `bin/rake`, `master.key`, `settings.yaml`, `settings.yaml.enc` (depending on your security policy).
3. Consider adding editor extensions via `idx.extensions` so everyone gets the same language server and formatting. (Extensions are installed from **Open VSX** by listing their IDs in `dev.nix`.)
4. If your connector needs databases/queues for testing, you can enable services like **Postgres**, **Redis**, or **Docker** directly in `dev.nix` under `services.*`. 

---

## 9) Troubleshooting cheatsheet

* **“My manual installs vanished”** → That’s expected. Put packages and env in `dev.nix`, then rebuild. 
* **Ruby version errors** → Ensure Ruby is **≥ 2.7.6**, which the SDK requires (RubyGems shows this on the SDK page). If needed, bump the Ruby package in `dev.nix` (e.g., `pkgs.ruby_3_3`). 
* **`workato` not found** → Rebuild the environment, then confirm `./bin/workato` exists. The `onCreate` hook creates it via `bundle binstubs`.
* **Where does the `workato` CLI come from?** → It’s provided by the `workato-connector-sdk` gem; installing the gem makes the `workato` command available. 

---

## 10) References

| Link | Description|
| ------ | ------------------------- |
| [Firebase: "Introducing Project IDX"](https://firebase.studio/blog/article/introducing-project-idx) | Blog article introducing the in-browser initiative |
| [Firebase: dev.nix](https://firebase.google.com/docs/studio/devnix-reference) | Reference for nix in the context of Firebase/IDX |
| [Project IDX](https://idx.dev) | Link to the IDE |
| [Firebase Studio](https://studio.firebase.google.com) | Link to the platform |
| [Ruby Gem: `workato-connector-sdk 1.3.16`](https://rubygems.org/gems/workato-connector-sdk/versions/1.3.16) | Ruby Gem: Workato Connector SDK |
| [Firebase: Preview your app](https://firebase.google.com/docs/studio/preview-apps) | Guide |
| [Workato: SDK reference](https://docs.workato.com/developing-connectors/sdk/cli/reference/cli-commands.html) | Reference |
| [Firebase: troubleshooting](https://firebase.google.com/docs/studio/troubleshooting) | FAQ |
| [Workato: SDK Quick start](https://docs.workato.com/developing-connectors/sdk/cli/guides/getting-started.html) | Quick start guide |
| [Firebase: customize](https://firebase.google.com/docs/studio/customize-workspace) | Workspace customization |
| [Workato: SDK CLI](https://docs.workato.com/developing-connectors/sdk/cli.html) | Reference |



