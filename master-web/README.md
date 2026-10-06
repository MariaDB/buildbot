# master-web

The only master with a web server: the UI at buildbot.mariadb.org, the REST API, and the GitHub change hook. It has no workers.

## The UI

nginx forwards requests to master-web's port 8010. master-web reads the builds of every master from the shared database, and gets their events live through the Crossbar message queue, so the UI shows all masters. Settings: `c["www"]` in [master.cfg](master.cfg).

| Path | Holds |
| --- | --- |
| [templates/](templates/) | Overrides of the home page, grid view and console view, and the Sponsors page |
| [static/](static/) | The sponsors' logos |
| [../dashboards/release/](../dashboards/release/README.md) | The Server Release Status page |

Signing in uses a GitHub OAuth app (`gh_mdbauth` in `master-private.cfg`). Forcing, rebuilding and stopping builds is open to members of the MariaDB GitHub organization; Foundry's rules, checked first, also restrict who may force a Foundry run.

## How changes arrive

GitHub sends push and pull request events to `/change_hook/github`, signed with `gh_secret`. master-web stores each change in the database, and every master's schedulers see it through the message queue. A pull request's change has the branch `refs/pull/<number>/head`.

| Project | Repository on production | Its change scheduler runs on |
| --- | --- | --- |
| Server | MariaDB/server | master-web (`s_upstream_tarball`) |
| Galera | MariaDB/galera | master-galera |
| Connectors | `CONNECTOR_*_REPO_URL` in [.env](../docker-compose/.env) | master-migration |
| Foundry | `FOUNDRY_REPO_URL` in [.env](../docker-compose/.env) | master-web |

Dev receives events from forks under the RazvanLiviuVarzaru GitHub account: the Connectors' and Foundry's are in [.env.dev](../docker-compose/.env.dev), the server's and Galera's are added to the schedulers when `ENVIRON` is `DEV`.

## Force schedulers

A force scheduler is offered only by the master that serves the UI, so force schedulers are loaded here (Foundry's), whatever master runs the builders they start.
