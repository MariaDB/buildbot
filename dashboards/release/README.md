# MariaDB Community Server Release Dashboard

## Scope

The purpose of this dashboard is to track all builds associated with the **planned releases** defined in Jira under the **MDEV project**.
A release is considered *planned* when its **Status = UNRELEASED**.

When multiple point releases exist within the same series (e.g., **12.3.1**, **12.3.2**, **12.3.3**, ...), **only the most recent release within that series** is included in the dashboard.

---

## Data Retrieval

Data is extracted from the Buildbot API for each **`bb-<series>-release`** branch, but only when the **MariaDB version** on the **latest change** of that branch **matches the planned version in Jira**.

Only builders tagged with **`release_packages`** are taken into account.
If the list of relevant builders is incomplete, please contact a **Buildbot Maintainer** to add the appropriate tag to the required builder.

As long as the MariaDB version matches across **Jira** and **Buildbot**, the dashboard will display data for that release.
If a version is marked as **RELEASED** in Jira, it will automatically be removed from the dashboard.

### MISC

- The rendered HTML page is cached for `CACHE_DURATION` to avoid excessive API calls.
- MariaDB version is extracted from the **source VERSION file.**
- For a given change (tarball number), only the most recent build from each builder is considered. This accounts for re-runs caused by sporadic test failures.

---

## Status Definitions

### **Pending**

A release is marked *Pending* when:

1. The `bb-<series>-release` branch does not exist, **or**
1. The branch exists but there is **no Buildbot run** matching the MariaDB version planned in Jira, **or**
1. One or more builds are **in progress** or **not yet executed**, and **no failed build exists**.

### **Releasable**

A release is marked *Releasable* when:

1. All builds within scope are **successful**.
1. This **does not imply** that development for the release is complete, only that the `bb-<series>-release` branch is currently in a healthy state.

### **Unreleasable**

A release is marked *Unreleasable* when:

1. One or more builds that produce packages have failed.

### **Needs Attention**

A release is marked *Needs Attention* when:

1. At least one normal builder has failed (probably MTR) but **there is no failed** autobake (producing packages for CI) builder.

---
