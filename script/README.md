# Configuration Scripts

Run the files, `script/bootstrap.py` and `script/verify.py` from project root
```bash
chmod +x script/bootstrap script/verify   # (already executable in the downloads)
./script/bootstrap
./script/verify
```
---

## Functionality

**Bootstrap**

> File: `script/bootstrap.py`

- Ensures a Gemfile.lock exists (creates one on first run).
- Adds multi‑platform entries and checksums to the lockfile.
- Vendors all gems into vendor/cache for offline/known‑source installs.
- Installs from the local cache to vendor/bundle (or $BUNDLE_PATH).
- Falls back to a single online install if the cache is incomplete, then re‑caches and retries.
- Generates binstubs into ./bin for consistent execution.

**Verify**

> File: `script/verify.py`

- Prints Bundler config and the expected install root.
- Fails if any gem path is not under vendor/bundle (or $BUNDLE_PATH).
- Runs bundle doctor.
- Audits all compiled .so files with ldd and fails if they link to /usr/lib or /usr/local (i.e., outside your pinned Nix libs).
- Shows Nokogiri’s VERSION_INFO if present and warns if vendor/cache is empty.
