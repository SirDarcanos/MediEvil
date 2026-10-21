# Build the runner package

The runtime and importer use Python's standard library. Packaging is an explicit allowlist: no data cache, game art, BIOS, disc, emulator, saves, research, tests, or local configuration is copied.

## Portable source ZIP

Run these commands from the repository’s `LiveMap/` directory:

```
python3 release/build.py --output dist
```

This creates `MediEvil-Minimap-v1-source.zip` plus a SHA-256 checksum. It works with a separately installed Python 3.10+, not with an imaginary bundled interpreter. Launchers are included for Windows, macOS and Linux. The generated cache is always outside the application folder.

## Python-free standalone build

Build **on each target OS/architecture**, using Python 3.12 and PyInstaller 6.22.3 in a dedicated build environment. PyInstaller is a build-only dependency; do not install it into the runner or a user's global Python. The build script never downloads or installs anything.

After provisioning that approved, isolated build environment (the following installs build-only tooling into it and fetches the matching official CPython license):

```
python -m pip install -r release/requirements-build.txt
python release/python_license.py --output build-licenses/PYTHON-LICENSE.txt
python release/build.py --standalone --python-license build-licenses/PYTHON-LICENSE.txt --output native-dist
```

The resulting OS/architecture-specific ZIP includes `MediEvilMinimap[.exe]` and its `_internal` runtime. Keep the entire folder together. macOS archives preserve framework symlinks; extract with an archive tool that preserves them. Cross-compiling Windows binaries on a Mac is not supported. Signing/notarization and publisher identity require the maintainer's own credentials and are not performed by this script.

Standalone archives include the repository GPL license, format-source notices, the matching interpreter license and PyInstaller's license. When publishing binaries, keep the matching full repository source/build scripts available at the release commit under the repository license.

The [repository workflow](../../.github/workflows/livemap-build.yml) builds on each target OS, checks the unpacked executable with its root Python sources removed, verifies bundled setup/marker resources, and uploads ZIPs/checksums. Its actions are pinned to verified release commits, its token is read-only, and it neither uploads game assets nor publishes releases. A successful frozen-startup smoke is **not** live DuckStation gameplay verification.

**Executed:** [CI run 39139164216](https://github.com/SirDarcanos/MediEvil/actions/runs/39139164216), code commit `f4fbabaa9852c03f15113b9ad7838e356dcf1319`: native Windows x64/Linux x64/macOS ARM64 builds and frozen startup/resource checks, plus Python3.10/3.14 source checks. Downloaded archive checksums, contents and required notices were verified locally. The downloaded initial `a8e54aa` Mac candidate, whose runtime code is unchanged by the archive-metadata repair, also completed own-disc extraction, textured rendering and cached restart.

**Stable-release gates still outstanding:** actual Windows/Linux DuckStation gameplay/lifecycle and code signing/notarization decisions. Published previews must retain these limits and their unsigned status. Do not label the source ZIP as standalone or CI startup as full gameplay certification.

## Maintainer release checks (not runner tasks)

- Unzip into a clean folder whose path contains spaces and non-ASCII characters.
- Source package: launch on Python3.10+; standalone: launch with no system Python.
- First run: choose the user's USA data-track BIN/ISO, confirm all25 maps/textures, recover from a wrong region/audio track/interrupted import, and restart without re-importing.
- Check cache location is writable and no game/save files change.
- Windows first: genuine DuckStation shared-memory tracking in the browser, followed by pause/resume, reset, cross-level state loads, level transitions and emulator restart. Repeat on native Linux and macOS's explicit GDB fallback.
- Verify raw XYZ/OOB/wraps and stale-marker suppression. Retain the GDB pause/disconnect disclosure.
- Check ZIP contents and checksums; no generated assets or private research artifacts. The tests and evidence stay outside the runner ZIP.

Developer checks:

```
python3 -m unittest discover -s . -p 'test_*.py'
node --test web/test_*.cjs
for script in web/*.js; do node --check "$script"; done
```
