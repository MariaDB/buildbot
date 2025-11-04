import os
from pathlib import PurePath

from configuration.builders.base import GenericBuilder
from configuration.builders.callables import canStartBuild, nextBuild
from configuration.builders.infra.runtime import DockerConfig
from configuration.builders.sequences.release import deb_autobake, rpm_autobake

DEFAULT_SHM_SIZE = "15g"
DEFAULT_BUILDER_JOBS = 7
DEFAULT_MEMLOCK_LIMIT = 51200000


def docker_config(
    image: str,
    shm_size: str = DEFAULT_SHM_SIZE,
    memlock_limit: int = DEFAULT_MEMLOCK_LIMIT,
    additional_bind_mounts: list[tuple[str, str]] = None,
    additional_env_vars: list[tuple[str, str]] = None,
) -> DockerConfig:
    bind_mounts = [
        (f'{os.environ["MASTER_PACKAGES_DIR"]}/', "/packages"),
        ("/srv/buildbot/ccache", "/mnt/ccache"),
    ] + (additional_bind_mounts if additional_bind_mounts else [])

    env_vars = [
        ("ARTIFACTS_URL", os.environ["ARTIFACTS_URL"]),
        ("CCACHE_DIR", "/mnt/ccache"),
    ] + (additional_env_vars if additional_env_vars else [])

    return DockerConfig(
        repository=os.environ["CONTAINER_REGISTRY_URL"],
        image_tag=image,
        workdir=PurePath("/home/buildbot"),
        bind_mounts=bind_mounts,
        shm_size=shm_size,
        env_vars=env_vars,
        memlock_limit=memlock_limit,
    )


def deb_release_builder(name: str, image: str, worker_pool: list) -> GenericBuilder:
    return GenericBuilder(
        name=name,
        sequences=[
            deb_autobake(
                jobs=DEFAULT_BUILDER_JOBS,
                config=docker_config(image=image),
                artifacts_url=os.environ["ARTIFACTS_URL"],
                test_galera=True,
                test_rocksdb=True,
                test_s3=True,
            ),
        ],
    ).get_config(
        workers=worker_pool,
        next_build=nextBuild,
        can_start_build=canStartBuild,
        tags=["release_packages", "autobake", "deb"],
        jobs=DEFAULT_BUILDER_JOBS,
        properties={
            "save_packages": True,
        },
    )


def rpm_release_builder(
    name: str, image: str, worker_pool: list, arch: str, has_compat: bool, rpm_type: str
) -> GenericBuilder:
    return GenericBuilder(
        name=name,
        sequences=[
            rpm_autobake(
                jobs=DEFAULT_BUILDER_JOBS,
                config=docker_config(image=image),
                srpm_config=docker_config(
                    image=f"{image}-srpm",
                    memlock_limit=DEFAULT_MEMLOCK_LIMIT,
                    shm_size=DEFAULT_SHM_SIZE,
                    additional_bind_mounts=(
                        [
                            (
                                "/etc/pki/entitlement",
                                "/run/secrets/etc-pki-entitlement",
                            ),
                            ("/etc/rhsm", "/run/secrets/rhsm"),
                        ]
                        if "rhel" in rpm_type
                        else []
                    ),
                ),
                rpm_type=rpm_type,
                arch=arch,
                artifacts_url=os.environ["ARTIFACTS_URL"],
                has_compat=has_compat,
                test_galera=True,
                test_rocksdb=True,
                test_s3=True,
            ),
        ],
    ).get_config(
        workers=worker_pool,
        next_build=nextBuild,
        can_start_build=canStartBuild,
        tags=["release_packages", "autobake", "rpm"],
        jobs=DEFAULT_BUILDER_JOBS,
        properties={
            "rpm_type": rpm_type,
            "save_packages": True,
        },
    )
