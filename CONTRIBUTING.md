# Contributing to orch

orch is intentionally small. Keep changes focused, include a regression test, and keep the
installer from touching a real home during verification.

## Getting set up

```bash
git clone https://github.com/smkamranqadri/orch-skill.git
cd orch-skill
./tests/run.sh
```

The test suite uses temporary homes and a fake Herdr command. It does not invoke model CLIs or
install into the developer's home.

## What a good change includes

- One behavior change and its test.
- Literal mutation checks for new safety or selection guards, with byte-identical restoration.
- No new runtime dependencies. The plugin uses Python 3.11 or newer and the standard library.
- Documentation for user-visible installer or CLI changes.
- No pushes, releases, or live Herdr config edits as part of local tests.

## Where things live

```text
plugin/                 Herdr manifest, CLI, hook, board, and shared library
skills/orch/            Installed skill and host command files
scripts/                Installer and plugin path resolver
tests/                  Unit and temp-home installer tests
docs/                   Release documentation and images
kis/                    Project-specific planning and state
```

Run the complete suite with `./tests/run.sh`. The release installer can be checked without
changing a real home by setting `HOME` to a temporary directory and putting the fake Herdr
fixture on `PATH`.
