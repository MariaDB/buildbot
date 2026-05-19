import os
from pathlib import PurePath

from buildbot.plugins import util
from configuration.builders.base import GenericBuilder
from configuration.builders.common import docker_config
from configuration.builders.infra.runtime import DockerConfig, Sidecar
from configuration.builders.sequences.connectors.conc import (
    bintar,
    get_source_package,
    git_clone_sq,
    save_packages,
    tarball,
    windows,
)

PACKAGES_DIR = f"{os.environ['CONNECTORS_PACKAGES_DIR']}/cpp"
BUILD_BASE_PATH = "build"
BINTAR_PATH = f"{BUILD_BASE_PATH}/bintar"
SOURCE_PATH = f"{BUILD_BASE_PATH}/source"
BINTAR_PACKAGES_TO_SAVE = [f"{BINTAR_PATH}/*.tar.gz"]


# MariaDB Server used for C/C++ tests
SIDECAR = Sidecar(
    repository="docker.io/library/",
    image_tag="mariadb:lts",
    env_vars=[("MARIADB_ROOT_PASSWORD", "test"), ("MARIADB_DATABASE", "test")],
    tmpfs=PurePath("/var/lib/mysql"),
)


TARBALL = GenericBuilder(
    name="cc-tarball-docker",
    sequences=[
        tarball(
            config=docker_config(
                image="debian13",
                packages_dir=PACKAGES_DIR,
                artifacts_url=f"{os.environ['ARTIFACTS_URL']}/connector-c/",
            ),
        )
    ],
)


def generate_bintar_sqs(
    ops,
    version,
    build_environment: DockerConfig = None,
    upload_packages_to_ci=True,
    get_source_from_git=False,
    with_asan_ubsan=False,
    with_msan=False,
):
    if not build_environment:
        build_environment = docker_config(
            image=f"{ops}{version}",
            packages_dir=PACKAGES_DIR,
            artifacts_url=f"{os.environ['ARTIFACTS_URL']}/connector-c/",
        )

    alma_linux_environment = None
    rockylinux_environment = None
    if ops == "rhel":
        alma_linux_environment = DockerConfig(
            repository="docker.io/library/",
            image_tag=f"almalinux:{version}",
        )
        rockylinux_environment = DockerConfig(
            repository="rockylinux/",
            image_tag=f"rockylinux:{version}",
        )

    test_environments = [
        build_environment,
        alma_linux_environment,
        rockylinux_environment,
    ]

    source_sq = [
        get_source_package(
            config=build_environment,
            source_path=SOURCE_PATH,
        ),
    ]

    if get_source_from_git:
        source_sq = [
            git_clone_sq(
                config=build_environment,
                source_path=SOURCE_PATH,
            )
        ]

    return (
        source_sq
        + [
            bintar(
                config=build_environment,
                test_environments=test_environments,
                source_path=SOURCE_PATH,
                bintar_path=BINTAR_PATH,
                package_platform_suffix=f"{ops}{version}",
                jobs=util.Property("jobs"),
                with_asan_ubsan=with_asan_ubsan,
                with_msan=with_msan,
            ),
        ]
        + (
            [
                save_packages(
                    packages=BINTAR_PACKAGES_TO_SAVE,
                    config=build_environment,
                )
            ]
            if upload_packages_to_ci
            else []
        )
    )


RELEASE_BUILDERS_BY_ARCH = {"amd64": [], "aarch64": []}
for arch in ["amd64", "aarch64"]:
    for ops, version in [
        ("fedora", "43"),
        ("fedora", "44"),
        ("sles", "1507"),
        ("sles", "1600"),
        ("rhel", "8"),
        ("rhel", "9"),
        ("rhel", "10"),
    ]:
        if ops == "sles" and arch != "amd64":
            continue
        builder = GenericBuilder(
            name=f"cc-{arch}-{ops}-{version}",
            sidecar=SIDECAR,
            sequences=generate_bintar_sqs(ops=ops, version=version),
        )
        RELEASE_BUILDERS_BY_ARCH[arch].append(builder)

    for ops, version in [
        ("debian", "11"),
        ("debian", "12"),
        ("debian", "13"),
        ("ubuntu", "22.04"),
        ("ubuntu", "24.04"),
        ("ubuntu", "26.04"),
    ]:
        builder = GenericBuilder(
            name=f"cc-{arch}-{ops}-{version}",
            sidecar=SIDECAR,
            sequences=generate_bintar_sqs(ops=ops, version=version),
        )
        RELEASE_BUILDERS_BY_ARCH[arch].append(builder)

# UBASAN_BUILDER = GenericBuilder(
#     name="cc-debian-13-ubasan-clang-22",
#     sidecar=SIDECAR,
#     sequences=generate_bintar_sqs(
#         build_environment=docker_config(
#             image="debian13-msan-clang-22",
#             artifacts_url=f"{os.environ['ARTIFACTS_URL']}/connector-c/",
#         ),
#         ops="debian",
#         version="13",
#         upload_packages_to_ci=False,
#         with_asan_ubsan=True,
#         get_source_from_git=True,
#     ),
# )

# WINDOWS_64_BUILDER = GenericBuilder(
#     name="cc-amd64-windows",
#     sequences=[
#         windows(jobs=util.Property("jobs"), target_platform="64-bit"),
#     ],
# )

# MSAN_BUILDER = GenericBuilder(
#     name="cc-debian-13-msan-clang-22",
#     sidecar=SIDECAR,
#     sequences=generate_bintar_sqs(
#         build_environment=docker_config(
#             image="debian13-msan-clang-22",
#             artifacts_url=f"{os.environ['ARTIFACTS_URL']}/connector-c/",
#         ),
#         with_msan=True,
#         ops="debian",
#         version="13",
#         upload_packages_to_ci=False,
#     ),
# )
