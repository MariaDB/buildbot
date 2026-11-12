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
    mariadb_repo,
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


def has_conc_repo(conc_repos: dict[str, str]):
    # True when the platform lists a MariaDB Server repo for the build's C/C series
    return lambda step: step.getProperty("conc_series") in conc_repos


def generate_bintar_release_sq(ops, version):
    build_environment = docker_config(
        image=f"{ops}{version}",
        packages_dir=PACKAGES_DIR,
        artifacts_url=f"{os.environ['ARTIFACTS_URL']}/connector-odbc/",
    )
    return generate_bintar_sqs(build_environment, ops, version)


def generate_rpm_release_sq(ops, version, conc_repos):
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
        mariadb_repo(config=build_environment, conc_repos=conc_repos),
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
    for sequence in rhel_sqs:
        for step in sequence.get_steps():
            step.options.doStepIf = has_conc_repo(conc_repos)

    return bintar_sqs + rhel_sqs


def generate_deb_release_sq(ops, version, conc_repos):
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

    bintar_sqs = generate_bintar_sqs(build_environment, ops[:3], version)
    deb_sqs = [
        mariadb_repo(config=build_environment, conc_repos=conc_repos),
        deb(
            config=build_environment,
            jobs=util.Property("jobs"),
            package_platform_suffix=f"{ops[:3]}{version}",
            deb_path=DEB_PATH,
            source_path=SOURCE_PATH,
        ),
        deb_pkg_tests(
            config=clean_environment,
            deb_path=DEB_PATH,
        ),
        save_packages(
            packages=DEB_PACKAGES_TO_SAVE,
            user="root",
            config=clean_environment,
        ),
    ]
    for sequence in deb_sqs:
        for step in sequence.get_steps():
            step.options.doStepIf = has_conc_repo(conc_repos)

    return bintar_sqs + deb_sqs


RELEASE_BUILDERS_BY_ARCH = {"amd64": [], "aarch64": []}
for arch in ["amd64", "aarch64"]:
    for ops, version in [
        ("fedora", "43"),
        ("fedora", "44"),
        ("fedora", "45"),
        ("sles", "1507"),
        ("sles", "1600"),
    ]:
        if ops == "sles" and arch != "amd64":
            continue
        builder = GenericBuilder(
            name=f"codbc-{arch}-{ops}-{version}",
            sidecar=SIDECAR,
            sequences=generate_bintar_release_sq(ops=ops, version=version),
        )
        RELEASE_BUILDERS_BY_ARCH[arch].append(builder)

    # Packaging platforms: (ops, version, conc_repos)
    # A branch's C/C series (e.g. "3.4") is read from its libmariadb submodule.
    # For deb/rpm packaging, the builder installs that C/C from the repo of a
    # MariaDB Server release on mirror.mariadb.org: conc_repos says, for this
    # platform, which server version's repo has each C/C series.
    # Series not in conc_repos -> only the bintar is built.
    for ops, version, conc_repos in [
        ("rhel", "8", {"3.3": "10.11", "3.4": "11.8"}),
        ("rhel", "9", {"3.3": "10.11", "3.4": "11.8"}),
        ("rhel", "10", {"3.3": "10.11", "3.4": "11.8"}),
    ]:
        builder = GenericBuilder(
            name=f"codbc-{arch}-{ops}-{version}",
            sidecar=SIDECAR,
            sequences=generate_rpm_release_sq(
                ops=ops, version=version, conc_repos=conc_repos
            ),
        )
        RELEASE_BUILDERS_BY_ARCH[arch].append(builder)

    for ops, version, conc_repos in [
        ("debian", "12", {"3.3": "10.11", "3.4": "11.8"}),
        ("debian", "13", {"3.4": "11.8"}),
        ("ubuntu", "22.04", {"3.3": "10.11", "3.4": "11.8"}),
        ("ubuntu", "24.04", {"3.3": "10.11", "3.4": "11.8"}),
        ("ubuntu", "26.04", {"3.4": "11.8"}),
    ]:
        builder = GenericBuilder(
            name=f"codbc-{arch}-{ops}-{version}",
            sidecar=SIDECAR,
            sequences=generate_deb_release_sq(
                ops=ops, version=version, conc_repos=conc_repos
            ),
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
