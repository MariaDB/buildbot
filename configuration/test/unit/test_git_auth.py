# The helper text itself is private to git_auth, but it is exactly what these
# tests exist to pin down.
# pylint: disable=protected-access
import pathlib
import subprocess
import tempfile
import unittest

import git_auth
from configuration.steps.commands.base import Command
from configuration.steps.remote import PropFromShellStep, ShellStep
from git_auth import (
    GITHUB_TOKEN_ENV_VAR,
    git_auth_args,
    git_auth_argv,
    git_auth_config,
    git_auth_config_env,
    git_auth_env_vars,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def _git_version():
    out = subprocess.run(
        ["git", "--version"], capture_output=True, text=True, check=True
    ).stdout
    return tuple(int(p) for p in out.split()[2].split(".")[:2])


class TestCredentialHelperString(unittest.TestCase):
    """The helper text is spliced into bash command lines and into
    util.Interpolate() strings, so two characters must never appear in it."""

    def test_contains_no_single_quote(self):
        # git_auth_args() wraps the helper in '...' for bash.
        self.assertNotIn("'", git_auth._CREDENTIAL_HELPER)

    def test_contains_no_percent(self):
        # A bare % would be eaten by buildbot's util.Interpolate().
        self.assertNotIn("%", git_auth._CREDENTIAL_HELPER)
        self.assertNotIn("%", git_auth_args())

    def test_token_is_never_inlined(self):
        """The PAT must reach git through the environment, never through
        config values or a command line."""
        for rendered in (git_auth_args(), str(git_auth_config())):
            self.assertIn(GITHUB_TOKEN_ENV_VAR, rendered)
            self.assertNotIn("secret:", rendered)

    def test_resets_preconfigured_helpers(self):
        """'helper' is multi-valued and accumulates across config files; a
        helper already present on the worker would otherwise answer first."""
        self.assertIn("-c credential.helper= ", git_auth_args())
        self.assertEqual(git_auth_config()["credential.helper"], "")
        self.assertEqual(git_auth_config_env()["GIT_CONFIG_VALUE_0"], "")

    def test_scoped_to_github(self):
        for rendered in (git_auth_args(), str(git_auth_config())):
            self.assertIn("credential.https://github.com.helper", rendered)
            self.assertIn("http.https://github.com.proactiveAuth", rendered)

    def test_sends_token_proactively(self):
        """Without it git authenticates only after a 401, so unchallenged
        requests go out anonymously even though the token is configured."""
        key = "http.https://github.com.proactiveAuth"
        self.assertIn(f"-c {key}=basic", git_auth_args())
        self.assertEqual(git_auth_config()[key], "basic")

    def test_env_form_matches_the_flags(self):
        env = git_auth_config_env()
        pairs = [
            f"{env[f'GIT_CONFIG_KEY_{i}']}={env[f'GIT_CONFIG_VALUE_{i}']}"
            for i in range(int(env["GIT_CONFIG_COUNT"]))
        ]
        self.assertEqual(pairs, git_auth_argv()[1::2])

    def test_env_vars_reference_the_secret_provider(self):
        ((name, value),) = git_auth_env_vars()
        self.assertEqual(name, GITHUB_TOKEN_ENV_VAR)
        self.assertEqual(value, "%(secret:github_token)s")

    def test_shell_script_helper_is_in_sync(self):
        """scripts/docker-library-build.sh hardcodes the same helper."""
        script = (REPO_ROOT / "scripts" / "docker-library-build.sh").read_text()
        self.assertIn(git_auth._CREDENTIAL_HELPER, script)


class TestShellScript(unittest.TestCase):
    """docker-library-build.sh assembles its own git_auth array and runs under
    set -x, so check both what it produces and what its trace shows."""

    def _run_auth_block(self, env):
        script = REPO_ROOT / "scripts" / "docker-library-build.sh"
        lines = script.read_text().splitlines()
        start = lines.index("git_auth=(")
        block = "\n".join(lines[start : lines.index("fi", start) + 1])
        return subprocess.run(
            ["bash", "-xc", block + '\nprintf "%s\\n" "${git_auth[@]}"'],
            capture_output=True,
            text=True,
            check=True,
            env={"PATH": "/usr/bin:/bin", **env},
        )

    def test_proactive_auth_only_with_a_token(self):
        # Proactive auth without a token fails the clone instead of letting a
        # public repo through anonymously, and this script may run without one.
        key = "http.https://github.com.proactiveAuth=basic"
        with_token = self._run_auth_block({GITHUB_TOKEN_ENV_VAR: "DUMMY-PAT"})
        without = self._run_auth_block({})
        self.assertIn(key, with_token.stdout)
        self.assertNotIn(key, without.stdout)

    def test_trace_never_shows_the_token(self):
        proc = self._run_auth_block({GITHUB_TOKEN_ENV_VAR: "DUMMY-PAT"})
        self.assertNotIn("DUMMY-PAT", proc.stderr)


class _StubCommand(Command):
    # Deliberately not GitInitFromCommit: that lives in download.py, which
    # imports utils -> constants, and those read os.environ at import time.
    def __init__(self):
        super().__init__(name="stub", workdir=pathlib.PurePath("."))

    def as_cmd_arg(self) -> list:
        return ["true"]


class TestLogEnviron(unittest.TestCase):
    """The worker dumps its environment to its own twistd.log, which nothing
    scrubs, and most of our workers are long-lived."""

    def _generate(self, **kwargs):
        step = ShellStep(command=_StubCommand(), **kwargs).generate()
        # This buildbot fork keeps the shell arguments in remote_kwargs rather
        # than as attributes on the step.
        return step.remote_kwargs

    def test_disabled_when_the_step_carries_a_token(self):
        kwargs = self._generate(secret_env_vars=git_auth_env_vars())
        self.assertIn(GITHUB_TOKEN_ENV_VAR, kwargs["env"])
        self.assertFalse(kwargs["logEnviron"])

    def test_left_alone_otherwise(self):
        kwargs = self._generate(env_vars=[("CCACHE_DIR", "/mnt/ccache")])
        self.assertTrue(kwargs["logEnviron"])

    def test_disabled_when_a_property_step_carries_a_token(self):
        step = PropFromShellStep(
            command=_StubCommand(), property="x", secret_env_vars=git_auth_env_vars()
        ).generate()
        self.assertIn(GITHUB_TOKEN_ENV_VAR, step.remote_kwargs["env"])
        self.assertFalse(step.remote_kwargs["logEnviron"])


class TestCredentialHelperBehaviour(unittest.TestCase):
    """Drive the real git binary through `git credential fill`."""

    def _fill(self, host, env, extra_args):
        with tempfile.TemporaryDirectory() as home:
            # Isolate from the developer's own credential configuration.
            preexisting = pathlib.Path(home) / ".gitconfig"
            preexisting.write_text(
                "[credential]\n"
                '\thelper = "!echo username=LEAK; echo password=LEAK-TOKEN;"\n'
            )
            proc = subprocess.run(
                ["git", *extra_args, "credential", "fill"],
                input=f"protocol=https\nhost={host}\n\n",
                capture_output=True,
                text=True,
                check=False,  # the absent-token case is expected to fail
                env={
                    "HOME": home,
                    "PATH": "/usr/bin:/bin",
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_TERMINAL_PROMPT": "0",
                    **env,
                },
            )
            return proc.stdout

    def test_supplies_the_token_for_github(self):
        out = self._fill(
            "github.com",
            {GITHUB_TOKEN_ENV_VAR: "DUMMY-PAT"},
            git_auth_argv(),
        )
        self.assertIn("username=x-access-token", out)
        self.assertIn("password=DUMMY-PAT", out)
        self.assertNotIn("LEAK", out)

    def test_does_not_leak_pat_to_other_hosts(self):
        out = self._fill(
            "gitlab.com",
            {GITHUB_TOKEN_ENV_VAR: "DUMMY-PAT"},
            git_auth_argv(),
        )
        self.assertNotIn("DUMMY-PAT", out)

    def test_absent_token_yields_no_credential(self):
        out = self._fill(
            "github.com",
            {},
            git_auth_argv(),
        )
        self.assertNotIn("password=", out)
        self.assertNotIn("LEAK", out)

    @unittest.skipIf(
        _git_version() < (2, 31),
        "GIT_CONFIG_COUNT needs git >= 2.31; only the Windows workers use this form",
    )
    def test_env_config_form_is_equivalent(self):
        out = self._fill(
            "github.com",
            {GITHUB_TOKEN_ENV_VAR: "DUMMY-PAT", **git_auth_config_env()},
            [],
        )
        self.assertIn("username=x-access-token", out)
        self.assertIn("password=DUMMY-PAT", out)
        self.assertNotIn("LEAK", out)


if __name__ == "__main__":
    unittest.main()
