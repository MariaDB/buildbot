import os
from pathlib import PurePath
from typing import Union

from configuration.builders.base import GenericBuilder
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
    platform: str = None,
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
        platform=platform,
    )


def deb_release_builder(
    name: str, image: Union[str, tuple[str, str]], worker_pool: list
) -> GenericBuilder:
    """Create a Debian-based release builder
    Args:
        name: The name of the builder.
        image: The Docker image to use, can be a string or a tuple of (image, platform). Platform is to be used with --platform flag when pulling the image.
        worker_pool: The list of workers to assign the builder to.

    """
    if isinstance(image, tuple):
        image_name = image[0]
        image_platform = image[1]
    else:
        image_name = image
        image_platform = None
    return GenericBuilder(
        name=name,
        sequences=[
            deb_autobake(
                jobs=DEFAULT_BUILDER_JOBS,
                config=docker_config(image=image_name, platform=image_platform),
                artifacts_url=os.environ["ARTIFACTS_URL"],
                test_galera=True,
                test_rocksdb=True,
                test_s3=True,
            ),
        ],
    ).get_config(
        workers=worker_pool,
        tags=["release_packages", "autobake", "deb"],
        jobs=DEFAULT_BUILDER_JOBS,
        properties={
            "save_packages": True,
        },
    )


def rpm_release_builder(
    name: str, image: str, worker_pool: list, arch: str, has_compat: bool, rpm_type: str
) -> GenericBuilder:
    """Create an RPM-based release builder
    Args:
        name: The name of the builder.
        image: The Docker image to use.
        worker_pool: The list of workers to assign the builder to.
        arch: For fetching the correct RPM compatibility packages.
        has_compat: Whether to include compatibility packages.
        rpm_type: The type of RPM (e.g., "rhel8", "rhel9"). Used during packaging.
    """
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
        tags=["release_packages", "autobake", "rpm"],
        jobs=DEFAULT_BUILDER_JOBS,
        properties={
            "rpm_type": rpm_type,
            "save_packages": True,
        },
    )
