# Running and deploying the masters

Each environment runs on one master host, as a Docker Compose stack: `/srv/prod` for production, `/srv/dev` for dev.

## The stack

[generate-config.py](generate-config.py) writes `docker-compose.yaml` from the list of masters (`MASTER_DIRECTORIES`) and the environment's settings. Change `generate-config.py`, not `docker-compose.yaml`, which it overwrites. The containers use the host's network:

| Container | Runs |
| --- | --- |
| `mariadb` | Buildbot's database ([mariadb-config/](mariadb-config/)) |
| `crossbar` | The message router the masters coordinate through ([crossbar/](crossbar/)) |
| `nginx` | The Buildbot site, proxied to master-web, and the site that serves saved files, ci.mariadb.org ([nginx/templates/](nginx/templates/)). |
| `master-web` | The UI, from the `bb-master:master-web` image, on port 8010 |
| one per master | `start.sh <master directory>`, from the `bb-master:master` image |

The repository is mounted in every master at `/srv/buildbot/master`, and their logs go to `logs/`. Each master gets a port, starting from `starting_port` in `master-private.cfg`, in the order of `MASTER_DIRECTORIES`.

The two environments differ only by their settings: [.env](.env) for production, [.env.dev](.env.dev) for dev. These set the URLs, the directories packages are saved to, the image tags (`dev_` on dev), the repositories of the Connectors and Foundry, and `BRANCH`, the branch builders download scripts from.

## Deploying

The [bbm-deploy](../.github/workflows/bbm_deploy.yml) workflow checks the configuration and copies the repository to the master host with `rsync`, which leaves the host's own files alone: `master-private.cfg`, the credentials, the libvirt ssh key, the certificates. It then regenerates `docker-compose.yaml` and the autogen masters.

**Dev** is deployed on every push to `dev`. The workflow stops the whole stack first and starts it again after, so every container is recreated.

**Production** is not deployed on a push to `main`. An operator starts bbm-deploy on `main` from the repository's Actions tab. It copies the code and regenerates the configuration, but restarts nothing. The operator then restarts the masters one at a time, when production's load allows:

```console
cd /srv/prod/docker-compose
docker-compose stop <master>
docker-compose --env-file .env up -d <master>
```

`stop` gives the master up to its `stop_grace_period` (5 minutes, set in `generate-config.py`) to shut down before it is killed. To make it faster, pass a shorter timeout, in seconds: `docker-compose stop -t 30 <master>`.

Check the number of autogen masters before deploying a change to `os_info.yaml`; see [Autogen masters](../docs/server-builders.md#autogen-masters).

### Restarting production without disrupting anyone

Prefer restarting when no branch protection builds are running, so that contributors already have their results on GitHub. Buildbot is meant to restart the builds a stop interrupts, but doesn't always. If you restart while such builds run, check the Grid View, filtered on the `protected` tag, that they finished or were restarted.

### Changes that don't need a deployment

- Scripts that builders download from GitHub when they run, from `BRANCH`: merging them to `main` changes production right away. These are the install and upgrade tests on master-libvirt and the Docker Library tests.
- Build images: merging a Dockerfile change to `main` moves the production tags; see [Build images](../ci_build_images/README.md).

## Testing on dev

Before starting many builds on dev, check that production's load is low.

Changes reach dev from the maintainers' forks, for every project (see [master-web](../master-web/README.md#how-changes-arrive)).

To run only what a change affects, edit the schedulers on the dev host, in `/srv/dev`, so that the trigger steps start only the builders of interest, then restart the masters concerned. To test a change to the MSAN builder, for instance, trigger only the MSAN builder. The next deployment to dev overwrites these edits.

## Secrets

No secrets are stored in git. Each master host, on dev and on production, keeps its own secrets, which `rsync` leaves alone on a deployment:

| On the master host | Holds | Read by |
| --- | --- | --- |
| `master-private.cfg` | Database and worker passwords, Docker daemon addresses, the GitHub tokens for statuses and sign-in, the webhook secret, ... (see [master-private.cfg-sample](../master-private.cfg-sample)) | Every `master.cfg` when it loads, and `generate-config.py` |
| `master-credential-provider/` (`MASTER_CREDENTIALS_DIR`) | One file per secret, such as `github_token` | Buildbot's secret provider |
| `master-libvirt/id_ed25519`, `known_hosts` | The ssh key to the libvirt hosts | master-libvirt |

The GitHub workflows have their own, in the repository's Actions secrets: the ssh keys and addresses of the master hosts for bbm-deploy, and the registry tokens for the images.

A value in `master-private.cfg` is an ordinary Python value of the configuration. A secret from the provider is written `%(secret:<name>)s` in an `Interpolate`: Buildbot reads it when the step runs, and shows `<name>` in its place in the logs. Use the provider for anything a build step needs.

The provider is Buildbot's `SecretInAFile`, on every master ([master_common.py](../master_common.py)). It reads the files when the master starts, so after adding or changing one, restart the masters that use it, as in [Deploying](#deploying).

A step of the builder framework takes secrets in `secret_env_vars`, as the GitHub token does ([git_auth.py](../git_auth.py)).

### GitHub credentials

github.com rejects anonymous clones from our CI with HTTP 401, so git
operations authenticate with a read-only Personal Access Token, stored as the
secret `github_token` in `MASTER_CREDENTIALS_DIR` (buildbot's `SecretInAFile`
provider):

```sh
install -d -m 0700 master-credential-provider
printf '%s' "$PAT" > master-credential-provider/github_token
chmod 0600 master-credential-provider/github_token
```

Then restart the masters that clone from github.com, one at a time, as in
[Deploying](#deploying): master-galera, master-nonlatent,
master-protected-branches and master-migration.

Git normally sends requests anonymously and offers credentials only after a
401, so we also set `http.proactiveAuth=basic` to send the token up front. That
needs git >= 2.46: on older images git authenticates only when GitHub
challenges it, which still fixes the 401 but lets unchallenged requests go out
anonymously. Where proactive auth is in effect, a missing or empty token fails
the clone instead of falling back to anonymous access.

**No scope beyond public read is required** — authenticating at all is what
lifts us off the 401 path. Prefer a fine-grained token with *Public
repositories (read-only)*; a classic token with no scopes ticked also works.
Either can be set to never expire. If you do set an expiry, track it: when the
token lapses every builder that clones fails at once, with a symptom
indistinguishable from the original 401.

Four things that will bite you otherwise:

- The file holds the token and nothing else (a trailing newline is stripped).
- `SecretInAFile` treats **every** file in that directory as a secret and
  refuses to start if any is group- or world-readable — so no notes, backups
  or `.gitkeep` in there.
- The secret is read when the master starts, not per build, so a **restart is
  required** after creating or rotating it. A missing secret fails the builds
  that need it, not `checkconfig`.
- No write access is granted or needed. The only factory that pushes (the
  unexercised staging-branch rebase in `master-protected-branches`) still uses
  `push_access_token` from `master-private.cfg`.

To confirm the token itself is accepted:

```sh
curl -sS -H "Authorization: Bearer $(cat master-credential-provider/github_token)" \
     https://api.github.com/rate_limit | grep -m1 limit
```

`"limit": 5000` means authenticated; `60` means still anonymous.

That does not show that builders send it, and neither does a green build. To
check a builder, force a build against a repository that does not exist (if
the force-build form lets you set one), e.g.
`https://github.com/MariaDB/this-repo-requires-auth`, and read the clone step:

- `Repository not found` — the token reached git and GitHub accepted it.
- `Authentication failed` — the token reached git but GitHub rejected it.
- `could not read Username` — the token never reached git on that builder.

Everything consuming the token goes through `git_auth.py` — never interpolate
one into a URL or a command, use the helpers there.
