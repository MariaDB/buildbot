"""The runtime image is (re)tagged, and fetched, per image: steps on the same
image can use different docker configs and keep the committed state."""

import pathlib
import unittest
from dataclasses import replace

from configuration.builders.infra.runtime import DockerConfig, InContainer
from configuration.steps.commands.base import Command
from configuration.steps.processors import processor_docker_fetch, processor_docker_tag
from configuration.steps.remote import ShellStep


class _StubCommand(Command):
    def __init__(self):
        super().__init__(name="Run command", workdir=pathlib.PurePath("."))

    def as_cmd_arg(self) -> list:
        return ["true"]


def _config(image, **kwargs):
    config = DockerConfig(repository="registry/", image_tag=image, **kwargs)
    config._container_name = "builder"
    return config


def _steps(*configs):
    return [
        InContainer(ShellStep(command=_StubCommand()), config) for config in configs
    ]


def _tagged(configs):
    _, active, _ = processor_docker_tag([], _steps(*configs), [])
    return [s.command.image_url for s in active if not isinstance(s, InContainer)]


def _fetched(configs):
    prepare, _, _ = processor_docker_fetch([], _steps(*configs), [])
    return [s.command.image_url for s in prepare]


class TestDockerTagAndFetch(unittest.TestCase):
    def test_same_image_other_config(self):
        base = _config("debian12")
        mounted = replace(base, bind_mounts=[("/src", "/dst")])
        mounted._container_name = "builder"
        self.assertEqual(_tagged([base, mounted, base]), ["registry/debian12"])
        self.assertEqual(_fetched([base, mounted]), ["registry/debian12"])

    def test_image_change(self):
        a, b = _config("debian12"), _config("rhel9")
        self.assertEqual(
            _tagged([a, b, a]),
            ["registry/debian12", "registry/rhel9", "registry/debian12"],
        )
        self.assertEqual(_fetched([a, b, a]), ["registry/debian12", "registry/rhel9"])

    def test_platform_change(self):
        amd64 = _config("debian12")
        i386 = _config("debian12", platform="linux/386")
        self.assertEqual(len(_tagged([amd64, i386])), 2)
        self.assertEqual(len(_fetched([amd64, i386])), 2)


if __name__ == "__main__":
    unittest.main()
