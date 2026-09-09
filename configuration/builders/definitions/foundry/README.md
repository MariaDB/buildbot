# Foundry build pipeline

[MariaDB/foundry](https://github.com/MariaDB/foundry) holds a set of MariaDB server plugins, one per top-level directory, all built through a single `cmake -P run.cmake` entry point.

This pipeline takes that repository and, for every supported MariaDB version, builds each plugin as a native package on every supported OS and architecture, installs it, and runs the plugin's own MTR suites against a matching MariaDB server.

Two things vary per run and are decided at run time rather than baked into the builders: **which plugins** get built, and **where the MariaDB server packages come from**. The MariaDB version is carried into the build as a property, so the same builders serve every version instead of the matrix gaining a dimension.

Currently 16 OS targets across 3 architectures (amd64, aarch64, x86) make 28 builders, of which 20 run for 11.4.

## Pipeline

```text
  trigger                dispatcher                per version           per OS/arch
  ------------------     --------------------      -----------------     ------------------
  Force button       \   foundry-trigger-builders   foundry_11_4_...      foundry-amd64-...
                      >  clone Foundry,          >  fan out with       >  build, install,
  GitHub pull req.   /   discover plugins           plugins + source       MTR, save
```

1. **Trigger** — someone presses Force, or GitHub sends a pull request event for the Foundry repository.
1. **Discover** — the dispatcher clones Foundry and reads the plugin list out of it: all plugins, or just the ones a pull request touches.
1. **Fan out** — one `Triggerable` per supported MariaDB version, carrying the plugin list and the chosen package source.
1. **Build and test** — per OS and architecture, in that target's own container.

Bintar targets (centos7, almalinux8) have no `-devel` packages to install against, so they link the plugin against an unpacked MariaDB server tarball and run that tarball's bundled MTR instead of installing system packages.

## Starting a run

### Force build

For each supported MariaDB version the force scheduler asks where the server packages should come from:

- **Use MariaDB Server mirrors** — the default; released packages from `mirror.mariadb.org`.
- **Use a ci.mariadb.org tarball** — build against a specific `tarbuildnum`, for testing against an unreleased server.
- **Skip this version** — no builders triggered for it.

There is no plugin picker: the dispatcher discovers what to build.

### Pull request

Fully automatic, and deliberately narrower than a force build:

- Only the plugins the pull request changes. A pull request touching the top-level `CMakeLists.txt` or `run.cmake` rebuilds everything, since those affect every plugin.
- Mirrors only; there is no CI tarball to choose.
- Packages are not saved.
- A pull request touching no plugin passes without building anything.

Changed files are read with `git` from the checkout, diffing against the merge base with the pull request's target branch. Buildbot's own Changed Files are not populated for pull request events on this deployment.

## Several plugins in one run

A run builds every discovered plugin in one `run.cmake` invocation, which keeps going after a plugin fails (`message(SEND_ERROR)`, not `FATAL_ERROR`). One broken plugin must not hide the others' results, so the build and install steps report a three-state outcome:

| Outcome | Step shows | Run result | What happens next |
| --- | --- | --- | --- |
| Every plugin succeeded | `SUCCESS` | pass | Continues |
| Some succeeded, some did not | `WARNINGS` | **fail** | Continues with the survivors; the step names the plugins that failed |
| None succeeded | `FAILURE` | **fail** | Stops — there is nothing left to install or test |

The partial case is a warning on the step so you can open it and see which plugin failed, but `flunkOnWarnings` still fails the run: a partly working build is never reported green.

Each stage narrows the list it hands to the next — requested, then built, then installed. MTR only runs suites belonging to plugins that installed, because a suite MariaDB cannot find aborts the entire test run. With a single plugin in scope, the common case for a pull request, any failure is simply a failure.

## Configured vs. discovered

`foundry.yaml` holds:

- the OS × architecture matrix and each target's package family (rpm, deb, bintar);
- the supported MariaDB versions, and which targets each one builds.

Discovered at run time:

- the plugins — every top-level directory in Foundry with a `CMakeLists.txt`;
- which plugins a pull request changed;
- which plugins built, and which of those installed;
- each plugin's MTR suite names, read off the built packages;
- the newest release on the mirrors for a MariaDB version.

Adding a plugin to Foundry therefore needs no change here. Adding an OS target or a MariaDB version does.

A MariaDB version's package list must only name targets the mirrors actually publish for that version, since those differ per branch — 11.4 has no sles-15.7/16.0 or opensuse-16.0 repository, while 11.8 does.

## Saved packages

```text
/packages/foundry/<mariadb_version>-<tarbuildnum|mirror>/<plugin>/<foundry_revision>/<buildername>/
```

One directory per plugin, taken from that plugin's own `<plugin>.build/` rather than the workspace root, where `run.cmake` pools every plugin's packages together. MTR logs from a failed run are saved per run rather than per plugin, since one MTR invocation covers every plugin's suites:

```text
/packages/foundry/<mariadb_version>-<tarbuildnum|mirror>/<foundry_revision>/logs/<buildername>/
```

Pull request builds save nothing.

## Design decisions

- **Plugins are discovered, not listed.** Foundry already defines what a plugin is; duplicating that list here would make every new plugin a two-repository change, and the lists would drift.
- **The public mirrors are the default source.** A run should be possible without a fresh server CI build to point at. Choosing a `tarbuildnum` stays available for testing against an unreleased server.
- **MariaDB version is a property, not a builder.** Keeps the matrix one dimension smaller, and adding a version costs no new builders.
- **Best effort on build and install, strict on the result.** Engineers need every plugin's outcome from one run, not just the first failure — but a partly working run must never be reported green.
- **Pull requests are read-only.** A contributor's branch validates a change; it should not publish installable packages or pin CI builds.
- **Every step runs in the target's own container.** A plugin package is only meaningful on the distribution it was built for, which is what makes the install test real.

## Where the code lives

| Path | What it holds |
| --- | --- |
| `foundry.yaml` | The OS matrix and the supported MariaDB versions |
| `builders.py` | Turns that config into builders and schedulers |
| `sources.py` | The three package-source choices and their property names |
| `../../sequences/foundry/` | Step sequences: `autobake.py` (deb/rpm/bintar), `dispatcher.py` |
| `../../../steps/commands/foundry.py` | The commands each step runs |
| `../../../schedulers/foundry.py` | Force scheduler, pull request scheduler, Triggerables |

The force and pull request schedulers are loaded by `master-web`, which serves the UI and receives the GitHub webhook. The dispatcher and package builders run on `master-migration`, which owns their workers.
