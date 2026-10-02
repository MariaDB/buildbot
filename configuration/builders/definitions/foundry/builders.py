from dataclasses import replace

from configuration.builders.base import GenericBuilder
from configuration.builders.common import docker_config
from configuration.builders.definitions.foundry import sources
from configuration.builders.definitions.foundry.settings import (
    ARCH_OVERRIDES,
    ARTIFACTS_URL,
    CI_URL,
    DISPATCHER_IMAGE,
    DISPATCHER_NAME,
    MARIADB_VERSIONS,
    MIRROR_URL,
    PACKAGE_TYPES,
    PACKAGES_DIR,
    RUN_DIR,
    TARGETS_BY_TYPE,
    TRIGGERED_RUN_DIR,
    PackageTarget,
    Target,
)
from configuration.builders.sequences.foundry import autobake, dispatcher


def _docker_config(storage_dir: str, **kwargs):
    # Foundry's containers mount only storage_dir of its storage, at the same
    # path under /packages, in place of docker_config's /packages and ccache
    # mounts; see settings.py.
    config = docker_config(artifacts_url=ARTIFACTS_URL, **kwargs)
    return replace(
        config,
        bind_mounts=[(f"{PACKAGES_DIR}/{storage_dir}", f"/packages/{storage_dir}")]
        + [m for m in config.bind_mounts if m[1] not in ("/packages", "/mnt/ccache")],
        env_vars=[e for e in config.env_vars if e[0] != "CCACHE_DIR"],
    )


def _base_image_config(target: PackageTarget, arch_override):
    # The target's plain upstream image, where rpm/deb packages are tested. A
    # full image reference, hence the empty repository.
    image = target.base_image
    if "base_image_prefix" in arch_override:
        image = arch_override["base_image_prefix"] + image.rsplit("/", 1)[-1]
    config = _docker_config(
        TRIGGERED_RUN_DIR,
        image=image,
        platform=arch_override.get("platform"),
        additional_bind_mounts=target.base_mounts,
        # A bare image has no debconf defaults; keep apt from prompting.
        # systemd isn't PID 1 here, so have systemctl skip its calls instead
        # of failing MariaDB-server's %posttrans (zypper exits 107 on it).
        additional_env_vars=[
            ("DEBIAN_FRONTEND", "noninteractive"),
            ("SYSTEMD_OFFLINE", "1"),
        ],
    )
    return replace(config, repository="")


def _builder(package_type: str, target: Target, arch: str) -> GenericBuilder:
    type_config = PACKAGE_TYPES[package_type]
    arch_override = ARCH_OVERRIDES.get(arch, {})
    container_config = _docker_config(
        TRIGGERED_RUN_DIR,
        image=f"{target.image}{arch_override.get('image_suffix', '')}",
        platform=arch_override.get("platform"),
    )
    # The server builder this one mirrors, e.g. amd64-debian-12-deb-autobake.
    server_builder = f"{arch}-{target.name}"
    if package_type == "bintar":
        sequence = autobake.bintar(
            container_config,
            ci_bintar_url=f"{CI_URL}/%(prop:tarbuildnum)s/{server_builder}",
            mirror_url=MIRROR_URL,
            mirror_bintar=type_config["mirror_bintar"],
        )
    else:
        # CI publishes a galera repo file per platform: the server builder's
        # name without "-<type>-autobake".
        galera_platform = server_builder.removesuffix(f"-{package_type}-autobake")
        sequence = autobake.packages(
            package_type.upper(),
            container_config,
            base_config=_base_image_config(target, arch_override),
            repo_file_url=(
                f"{CI_URL}/%(prop:tarbuildnum)s/{server_builder}"
                f"/{type_config['repo_file']}"
            ),
            mirror_repo_url=(
                f"{MIRROR_URL}/{type_config['mirror_path']}/%(prop:mariadb_version)s"
            ),
            galera_repo_url=(
                f"{CI_URL}/galera/mariadb-4.x-latest-gal-"
                f"{galera_platform}.{type_config['galera_repo_suffix']}"
            ),
            build_packages=type_config["build_packages"],
            test_packages=type_config["test_packages"],
        )
    return GenericBuilder(name=f"foundry-{server_builder}", sequences=[sequence])


# One builder per target and arch.
FOUNDRY_BUILDERS_BY_ARCH = {}
FOUNDRY_BUILDERS_BY_PACKAGE = {}
for package_type, targets in TARGETS_BY_TYPE.items():
    for target in targets:
        for arch in target.arch:
            builder = _builder(package_type, target, arch)
            FOUNDRY_BUILDERS_BY_ARCH.setdefault(arch, []).append(builder)
            FOUNDRY_BUILDERS_BY_PACKAGE.setdefault(target.name, []).append(builder)


def _builder_names(packages):
    return [
        builder.name
        for package in packages
        for builder in FOUNDRY_BUILDERS_BY_PACKAGE[package]
    ]


# Builders per Triggerable, keyed by scheduler name: one for a version's
# targets, if it has any, and one for its ci_only targets, if it has any.
FOUNDRY_TRIGGERABLE_BUILDERS = {}
for version, version_config in MARIADB_VERSIONS.items():
    if version_config.targets:
        FOUNDRY_TRIGGERABLE_BUILDERS[sources.scheduler_name(version)] = _builder_names(
            version_config.targets
        )
    if version_config.ci_only:
        FOUNDRY_TRIGGERABLE_BUILDERS[sources.ci_only_scheduler_name(version)] = (
            _builder_names(version_config.ci_only)
        )


DISPATCHER_BUILDER = GenericBuilder(
    name=DISPATCHER_NAME,
    sequences=[
        dispatcher.trigger_foundry(
            _docker_config(RUN_DIR, image=DISPATCHER_IMAGE),
            MARIADB_VERSIONS,
            scheduler_names=list(FOUNDRY_TRIGGERABLE_BUILDERS),
            ci_url=CI_URL,
            # Per version, the builders the status report lists.
            report_builders={
                version: {
                    scheduler: FOUNDRY_TRIGGERABLE_BUILDERS[scheduler]
                    for scheduler in (
                        sources.scheduler_name(version),
                        sources.ci_only_scheduler_name(version),
                    )
                    if scheduler in FOUNDRY_TRIGGERABLE_BUILDERS
                }
                for version in MARIADB_VERSIONS
            },
        )
    ],
)
