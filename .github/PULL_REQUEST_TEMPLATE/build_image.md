# Build images

## What and why

<!-- What changes, and why. Link the Jira issue: https://jira.mariadb.org/browse/MDBF-... -->

## How it was tested

<!-- The image workflow's run on this pull request, and after merging to dev, the builders that ran with the dev_ image. -->

## Checklist

<!-- Running MariaDB Buildbot locally isn't possible yet, but will be at some point. Until then, tick what you can. -->

- [ ] `make pre-commit-run` passes (hadolint)
- [ ] The image workflow built the images on this pull request

<!-- Keep the sections below that apply, and delete the others. -->

### Adding an image

- [ ] Entry in the matrix of its family's workflow: `image`, `platforms`, `tag`, and `branch`, `nogalera`, `deploy_on_schedule` as needed
- [ ] The builders that will use it refer to its tag

### Changing an image

- [ ] After merging to `dev`: the builders that use it ran on dev, with `dev_<tag>`
- [ ] Merging to `main` moves `<tag>` to this image for production. To roll back, copy the previous `hist_<tag>_<commit>` from ghcr.io to quay.io (see `ci_build_images/README.md`)

### Removing an image

- [ ] No builder uses its tag: searched `os_info.yaml`, `master-*/` and `configuration/`
