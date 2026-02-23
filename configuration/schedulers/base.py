import fnmatch


def upstream_branch_fn(branch, filter_branches):
    return any(fnmatch.fnmatch(branch, pattern) for pattern in filter_branches)
