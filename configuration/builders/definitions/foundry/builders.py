from dataclasses import replace
from pathlib import Path

import yaml

from configuration.builders.base import GenericBuilder
from configuration.builders.common import docker_config
from configuration.builders.definitions.foundry import sources
from configuration.builders.sequences.foundry import autobake, dispatcher, storage

with open(Path(__file__).parent / "foundry.yaml") as f:
    _FOUNDRY_CONFIG = yaml.safe_load(f)

FOUNDRY_REPOSITORY = _FOUNDRY_CONFIG["repository"]
_CI_URL = _FOUNDRY_CONFIG["server"]["ci_url"]
_MIRROR_URL = _FOUNDRY_CONFIG["server"]["mirror_url"]
_ARCH_OVERRIDES = _FOUNDRY_CONFIG["arch"]


def _docker_config(**kwargs):
    # Foundry's containers mount its own storage as /packages; see storage.py.
    return docker_config(
        packages_dir=storage.PACKAGES_DIR, artifacts_url=storage.ARTIFACTS_URL, **kwargs
    )


def _base_image_config(package_config, arch_override):
    # The target's plain upstream image, where rpm/deb packages are tested. A
    # full image reference, hence the empty repository.
    image = package_config["base_image"]
    if "base_image_prefix" in arch_override:
        image = arch_override["base_image_prefix"] + image.rsplit("/", 1)[-1]
    config = _docker_config(
        image=image,
        platform=arch_override.get("platform"),
        additional_bind_mounts=[
            tuple(mount) for mount in package_config.get("base_mounts", [])
        ],
        # A bare image has no debconf defaults; keep apt from prompting.
        # systemd isn't PID 1 here, so have systemctl skip its calls instead
        # of failing MariaDB-server's %posttrans (zypper exits 107 on it).
        additional_env_vars=[
            ("DEBIAN_FRONTEND", "noninteractive"),
            ("SYSTEMD_OFFLINE", "1"),
        ],
    )
    return replace(config, repository="")


# (package type, its settings, target, target settings) from foundry.yaml.
_TARGETS = [
    (package_type, type_config, package, package_config)
    for package_type, type_config in _FOUNDRY_CONFIG["packages"].items()
    for package, package_config in type_config["targets"].items()
]


FOUNDRY_BUILDERS_BY_ARCH = {}
FOUNDRY_BUILDERS_BY_PACKAGE = {}
for package_type, type_config, package, package_config in _TARGETS:
    for arch in package_config["arch"]:
        arch_override = _ARCH_OVERRIDES.get(arch, {})
        platform = arch_override.get("platform")
        container_config = _docker_config(
            image=f"{package_config['image']}{arch_override.get('image_suffix', '')}",
            platform=platform,
        )
        # The server builder this one mirrors, e.g. amd64-debian-12-deb-autobake.
        server_builder = f"{arch}-{package}"
        if package_type == "bintar":
            sequence = autobake.bintar(
                container_config,
                ci_bintar_url=f"{_CI_URL}/%(prop:tarbuildnum)s/{server_builder}",
                mirror_url=_MIRROR_URL,
                mirror_bintar=type_config["mirror_bintar"],
            )
        else:
            # CI publishes a galera repo file per platform: the server
            # builder's name without "-<type>-autobake".
            galera_platform = server_builder.removesuffix(f"-{package_type}-autobake")
            galera_file_suffix = "repo" if package_type == "rpm" else "sources"
            sequence = autobake.packages(
                package_type.upper(),
                container_config,
                base_config=_base_image_config(package_config, arch_override),
                repo_file_url=(
                    f"{_CI_URL}/%(prop:tarbuildnum)s/{server_builder}"
                    f"/{type_config['repo_file']}"
                ),
                mirror_repo_url=(
                    f"{_MIRROR_URL}/{type_config['mirror_path']}"
                    "/%(prop:mariadb_version)s"
                ),
                galera_repo_url=(
                    f"{_CI_URL}/galera/mariadb-4.x-latest-gal-"
                    f"{galera_platform}.{galera_file_suffix}"
                ),
                build_packages=type_config["build_packages"],
                test_packages=type_config["test_packages"],
            )
        builder = GenericBuilder(
            name=f"foundry-{server_builder}",
            sequences=[sequence],
        )
        FOUNDRY_BUILDERS_BY_ARCH.setdefault(arch, []).append(builder)
        FOUNDRY_BUILDERS_BY_PACKAGE.setdefault(package, []).append(builder)

FOUNDRY_MARIADB_VERSIONS = _FOUNDRY_CONFIG["mariadb_versions"]
for version, version_config in FOUNDRY_MARIADB_VERSIONS.items():
    for package in version_config["targets"] + version_config["ci_only"]:
        assert (
            package in FOUNDRY_BUILDERS_BY_PACKAGE
        ), f"Unknown foundry package: {package}"
    both = set(version_config["targets"]) & set(version_config["ci_only"])
    assert not both, f"{version}: in both targets and ci_only: {sorted(both)}"
    assert (
        version_config["targets"] or version_config["ci_only"]
    ), f"{version}: no targets or ci_only"

FOUNDRY_FORCE_USERS = _FOUNDRY_CONFIG["access"]["force_users"]


def _builder_names(packages):
    return [
        builder.name
        for package in packages
        for builder in FOUNDRY_BUILDERS_BY_PACKAGE[package]
    ]


# Builders per Triggerable, keyed by scheduler name: one for a version's
# targets, if it has any, and one for its ci_only targets, if it has any.
FOUNDRY_TRIGGERABLE_BUILDERS = {}
for version, version_config in FOUNDRY_MARIADB_VERSIONS.items():
    if version_config["targets"]:
        FOUNDRY_TRIGGERABLE_BUILDERS[sources.scheduler_name(version)] = _builder_names(
            version_config["targets"]
        )
    if version_config["ci_only"]:
        FOUNDRY_TRIGGERABLE_BUILDERS[sources.ci_only_scheduler_name(version)] = (
            _builder_names(version_config["ci_only"])
        )


def _dispatch_specs():
    # Per version: the force-scheduler fields holding its choice, and the
    # Triggerable(s) to fire.
    return [
        {
            "mariadb_version": version,
            "source_property": sources.source_property(version),
            "tarbuildnum_property": sources.tarbuildnum_property(version),
            "mirrored": sources.on_mirrors(version_config),
            # None for a version not on the mirrors yet: it has no targets.
            "scheduler": (
                sources.scheduler_name(version)
                if sources.on_mirrors(version_config)
                else None
            ),
            # Fired too on CI tarball runs; None without ci_only targets.
            "ci_only_scheduler": (
                sources.ci_only_scheduler_name(version)
                if version_config["ci_only"]
                else None
            ),
            "ci_only_targets": version_config["ci_only"],
        }
        for version, version_config in FOUNDRY_MARIADB_VERSIONS.items()
    ]


_DISPATCHER = _FOUNDRY_CONFIG["dispatcher"]

DISPATCHER_BUILDER = GenericBuilder(
    name=_DISPATCHER["builder"],
    sequences=[
        dispatcher.trigger_foundry(
            _docker_config(image=_DISPATCHER["image"]), _dispatch_specs()
        )
    ],
)
