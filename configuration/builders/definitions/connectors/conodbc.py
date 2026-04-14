import os
from pathlib import PurePath

from buildbot.plugins import util
from configuration.builders.base import GenericBuilder
from configuration.builders.common import docker_config
from configuration.builders.infra.runtime import DockerConfig, Sidecar
from configuration.builders.sequences.connectors.conodbc import (
    bintar,
    deb,
    deb_pkg_tests,
    get_source_package,
    git_clone_sq,
    macos,
    rpm,
    rpm_pkg_tests,
    save_packages,
    srpm_pkg_test,
    tarball,
    windows,
)

PACKAGES_DIR = f"{os.environ['CONNECTORS_PACKAGES_DIR']}/odbc"
BUILD_BASE_PATH = "build"
BINTAR_PATH = f"{BUILD_BASE_PATH}/bintar"
RPM_PATH = f"{BUILD_BASE_PATH}/rpm"
DEB_PATH = f"{BUILD_BASE_PATH}/deb"
SOURCE_PATH = f"{BUILD_BASE_PATH}/source"
BINTAR_PACKAGES_TO_SAVE = [f"{BINTAR_PATH}/*.tar.gz"]
DEB_PACKAGES_TO_SAVE = [f"{DEB_PATH}/*.deb", f"{DEB_PATH}/*.ddeb"]
RPM_PACKAGES_TO_SAVE = [f"{RPM_PATH}/*.rpm", f"{RPM_PATH}/srpms/*.src.rpm"]


# MariaDB Server used for ODBC tests
SIDECAR = Sidecar(
    repository="docker.io/library/",
    image_tag="mariadb:lts",
    env_vars=[("MARIADB_ALLOW_EMPTY_ROOT_PASSWORD", "1"), ("MARIADB_DATABASE", "test")],
    tmpfs=PurePath("/var/lib/mysql"),
)


TARBALL = GenericBuilder(
    name="codbc-tarball-docker",
    sequences=[
        tarball(
            config=docker_config(
                image="debian13",
                packages_dir=PACKAGES_DIR,
                artifacts_url=f"{os.environ['ARTIFACTS_URL']}/connector-odbc/",
            ),
        )
    ],
)


def generate_bintar_sqs(
    build_environment,
    ops,
    version,
    upload_packages_to_ci=True,
    get_source_from_git=False,
    with_asan_ubsan=False,
    with_msan=False,
):

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


def generate_rpm_release_sq(ops, version):
    build_environment = docker_config(
        image=f"{ops}{version}",
        packages_dir=PACKAGES_DIR,
        artifacts_url=f"{os.environ['ARTIFACTS_URL']}/connector-odbc/",
    )
    clean_environment = docker_config(
        image=f"{ops}{version}-srpm",
        packages_dir=PACKAGES_DIR,
        artifacts_url=f"{os.environ['ARTIFACTS_URL']}/connector-odbc/",
    )

    alma_linux_environment = DockerConfig(
        repository="docker.io/library/",
        image_tag=f"almalinux:{version}",
    )
    rockylinux_environment = DockerConfig(
        repository="rockylinux/",
        image_tag=f"rockylinux:{version}",
    )

    if ops == "rhel":
        rhel_subscription_mounts = [
            (
                "/etc/pki/entitlement",
                "/run/secrets/etc-pki-entitlement",
            ),
            ("/etc/rhsm", "/run/secrets/rhsm"),
        ]
        build_environment.bind_mounts += rhel_subscription_mounts
        clean_environment.bind_mounts += rhel_subscription_mounts

    bintar_sqs = generate_bintar_sqs(build_environment, ops, version)

    rhel_sqs = [
        rpm(
            config=build_environment,
            jobs=util.Property("jobs"),
            package_platform_suffix=f"{ops}{version}",
            rpm_path=RPM_PATH,
            source_path=SOURCE_PATH,
            os_name=ops.upper(),
        ),
        rpm_pkg_tests(
            config=clean_environment,
            rpm_path=RPM_PATH,
            os_name=ops.upper(),
        ),
        srpm_pkg_test(
            config=clean_environment,
            jobs=util.Property("jobs"),
            rpms_dir=RPM_PATH,
        ),
        save_packages(
            packages=RPM_PACKAGES_TO_SAVE,
            config=clean_environment,
        ),
        rpm_pkg_tests(
            config=alma_linux_environment,
            rpm_path=RPM_PATH,
            os_name=f"ALMA",
        ),
        rpm_pkg_tests(
            config=rockylinux_environment,
            rpm_path=RPM_PATH,
            os_name=f"ROCKY",
        ),
    ]

    if ops == "rhel":
        return bintar_sqs + rhel_sqs
    return bintar_sqs


def generate_deb_release_sq(ops, version):
    build_environment = docker_config(
        image=f"{ops}{version}",
        packages_dir=PACKAGES_DIR,
        artifacts_url=f"{os.environ['ARTIFACTS_URL']}/connector-odbc/",
    )
    clean_environment = DockerConfig(
        repository="docker.io/library/",
        image_tag=f"{ops}:{version}",
        bind_mounts=[(f"{PACKAGES_DIR}/", "/packages")],
    )

    do_step_if = lambda props: True
    if ops == "debian" and version == "13":
        # ODBC 3.1 needs C/C 3.3 which is not available in Debian 13
        # MariaDB-Server repos as only >= 11.8 is built which contains C/C 3.4
        # In this case we only produce a bintar
        do_step_if = lambda step: step.getProperty("odbc_version") != "3.1"

    bintar_sqs = generate_bintar_sqs(build_environment, ops[:3], version)
    deb_sqs = [
        deb(
            config=build_environment,
            jobs=util.Property("jobs"),
            package_platform_suffix=f"{ops[:3]}{version}",
            deb_path=DEB_PATH,
            source_path=SOURCE_PATH,
            do_step_if=do_step_if,
        ),
        deb_pkg_tests(
            config=clean_environment,
            deb_path=DEB_PATH,
            do_step_if=do_step_if,
        ),
        save_packages(
            packages=DEB_PACKAGES_TO_SAVE,
            user="root",
            config=clean_environment,
        ),
    ]

    if ops == "ubuntu" and version == "26.04":
        return bintar_sqs
    return bintar_sqs + deb_sqs


RELEASE_BUILDERS_BY_ARCH = {"amd64": [], "aarch64": []}
for arch in ["amd64", "aarch64"]:
    for ops, version in [
        ("fedora", "42"),
        ("fedora", "43"),
        ("sles", "1507"),
        ("sles", "1600"),
        ("rhel", "8"),
        ("rhel", "9"),
        ("rhel", "10"),
    ]:
        if ops == "sles" and arch != "amd64":
            continue
        builder = GenericBuilder(
            name=f"codbc-{arch}-{ops}-{version}",
            sidecar=SIDECAR,
            sequences=generate_rpm_release_sq(ops=ops, version=version),
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
            name=f"codbc-{arch}-{ops}-{version}",
            sidecar=SIDECAR,
            sequences=generate_deb_release_sq(ops=ops, version=version),
        )
        RELEASE_BUILDERS_BY_ARCH[arch].append(builder)

UBASAN_BUILDER = GenericBuilder(
    name="codbc-debian-13-ubasan-clang-22",
    sidecar=SIDECAR,
    sequences=generate_bintar_sqs(
        build_environment=docker_config(
            image="debian13-msan-clang-22",
            artifacts_url=f"{os.environ['ARTIFACTS_URL']}/connector-odbc/",
        ),
        ops="debian",
        version="13",
        upload_packages_to_ci=False,
        with_asan_ubsan=True,
        get_source_from_git=True,
    ),
)

MACOS_BUILDER = GenericBuilder(
    name="codbc-aarch64-macos",
    sequences=[macos(jobs=util.Property("jobs"))],
)

WINDOWS_64_BUILDER = GenericBuilder(
    name="codbc-amd64-windows",
    sequences=[
        windows(jobs=util.Property("jobs"), target_platform="64-bit"),
    ],
)

WINDOWS_32_BUILDER = GenericBuilder(
    name="codbc-x86-windows",
    sequences=[
        windows(jobs=util.Property("jobs"), target_platform="32-bit"),
    ],
)

MSAN_BUILDER = GenericBuilder(
    name="codbc-debian-13-msan-clang-22",
    sidecar=SIDECAR,
    sequences=generate_bintar_sqs(
        build_environment=docker_config(
            image="debian13-msan-clang-22",
            artifacts_url=f"{os.environ['ARTIFACTS_URL']}/connector-odbc/",
        ),
        with_msan=True,
        ops="debian",
        version="13",
        upload_packages_to_ci=False,
    ),
)
