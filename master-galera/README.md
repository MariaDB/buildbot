# master-galera

Builds the [Galera](https://github.com/MariaDB/galera) packages for every server platform and saves them to ci.mariadb.org, where the release takes them from.

## Builders

- `trigger-galera-builds` is the entry point, for pushes to `mariadb-3.x`, `mariadb-4.x` and `bb-*`, and for pull requests, on MariaDB/galera (a fork on dev). It builds the source archive, saves it on a push, and triggers the package builders.
- `gal-<arch>-<os>`, one per platform in [os_info.yaml](../os_info.yaml) (see [Server builders](../docs/server-builders.md#platforms-os_infoyaml)), builds the deb or rpm packages.

## Saved files

Under `<ARTIFACTS_URL>/galera/`, from `GALERA_PACKAGES_DIR`:

| What | Where |
| --- | --- |
| Source archive | `<branch>/<revision>/galera-*.tar.gz` |
| A builder's packages, with a `galera.sources` or `galera.repo` file | `<branch>/<revision>/<builder>/` |
| The packages of the last build of a branch | `<branch>-latest-<builder>.sources` or `.repo`, a link to the above |

## Galera in the server's build images

The server builders need `galera-4` in their container to run the Galera MTR suites. The [build images](../ci_build_images/README.md) install it from `mariadb-4.x-latest-gal-<arch>-<os>-<version>`, so a new Galera build reaches the server builders when their images are next rebuilt. The image of a new platform can't install Galera until a `gal-` build has run for it on `mariadb-4.x`: build it with `nogalera: true` until then.
