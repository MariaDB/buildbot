# master-nonlatent

Server builders on non-latent workers, for the platforms that don't run in Docker, and the tests of the official Docker image.

| Builder | Workers | Does |
| --- | --- | --- |
| `amd64-windows` | `bbw4-windows` | Debug build and tests; reports to GitHub |
| `amd64-windows-packages` | `bbw3-windows` | MSI and zip packages; reports to GitHub |
| `aarch64-macos`, `aarch64-macos-compile-only` | `bbw1-mac`, `bbw2-mac` | Build and tests; compile only, reporting to GitHub |
| `amd64-freebsd-14` | `hz-freebsd-bbw1`, `hz-freebsd-bbw2` | Build and tests |
| `ppc64be-aix-71` | `aix-worker` | Build and tests |
| `amd64-rhel8-dockerlibrary` (`rhel9` on dev) | `MASTER_NONLATENT_DOCKERLIBRARY_WORKER` | Builds and tests the [official Docker image](https://github.com/MariaDB/mariadb-docker) with the packages of an `-autobake` build |
| `amd64-rhel8-wordpress` (`rhel9` on dev) | the same | WordPress tests |

Each worker's `max_builds` and `jobs` are set in [master.cfg](master.cfg), its password in `worker_pass` in `master-private.cfg`.

The Docker Library builder downloads its scripts from [scripts/](../scripts/) on GitHub, from `main` on production and `dev` on dev: a change to them is live as soon as it is merged. It pushes the images it builds only on production.
