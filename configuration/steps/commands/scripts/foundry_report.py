"""Writes a Foundry run's status.html and status.json.

Reads the files each package build wrote to <run dir>/<mariadb version>/<builder>/status/:
  build    run.cmake's result lines: "PASS <plugin> ..." or "FAIL <plugin> <stage> <reason>"
  install  "<plugin> pass" or "<plugin> fail"
  suites   "<plugin> <suite> <suite> ..." for the plugins with MTR suites
  mtr      MTR's closing summary: "... were successful." and "Failing test(s): ..."
A plugin that reached a stage whose file is missing shows "builder failed":
the builder failed for another cause, or was cancelled, before that stage. A
builder with no status directory failed before its first Foundry step, or never
started.

Usage: foundry_report.py <run dir> <versions json> <triggered> <plugins> <commit>
    <sources> <ci url>
<versions json> is {version: {Triggerable: [builder]}}; <triggered> lists the
Triggerables the dispatcher fired; <sources> is "<version>=<tarbuildnum or
mirror> ..." for the versions it triggered.
"""

import html
import json
import os
import re
import sys

PASS = "pass"
FAIL = "fail"
NOT_RUN = "not run"
BUILDER_FAILED = "builder failed"
NO_SUITES = "no suites"
NOT_APPLICABLE = "n/a"
NO_STATUS = "No status"
NOT_TRIGGERED = "Not triggered in this run"

# What each status means, shown at the top of the page.
LEGEND = {
    PASS: "The stage succeeded for this plugin.",
    FAIL: "The plugin failed this stage: it didn't build or install, or the "
    "MTR tests listed failed.",
    BUILDER_FAILED: "The builder failed for another cause, or was cancelled, "
    "before this stage.",
    NOT_RUN: "An earlier stage failed for this plugin, so this one was skipped.",
    NO_SUITES: "The plugin has no MTR suite, so there was nothing to test.",
    NOT_APPLICABLE: "The platform has no such stage: bintar builds have no install.",
    NO_STATUS: "For a whole platform: its builder failed before its first "
    "Foundry step, or never started.",
    NOT_TRIGGERED: "For a whole MariaDB version: the dispatcher didn't trigger "
    "it, as it was skipped on Force or isn't on the mirrors for a pull request.",
}
RED = (FAIL, BUILDER_FAILED, NO_STATUS)

# A failed test, with its combinations if any: main.t or main.t 'innodb'.
FAILED_TEST = re.compile(r"\S+?\.\S+(?: '[^']*')?")


def read_lines(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return [line.split() for line in f if line.strip()]


def mtr_summary(directory):
    # (failed tests, completed) from the mtr file, or None if MTR didn't run.
    path = os.path.join(directory, "mtr")
    if not os.path.exists(path):
        return None
    failed, completed = [], False
    with open(path) as f:
        for line in f:
            if line.startswith("Failing test(s):"):
                failed = FAILED_TEST.findall(line[len("Failing test(s):") :])
                completed = True
            elif "were successful" in line:
                completed = True
    return failed, completed


def platform_status(directory, plugins, bintar):
    # {plugin: {"build": {...}, "install": {...}, "mtr": {...}}}, each stage a
    # {"status": ...} with a "detail" or "failed_tests" when it failed.
    build = read_lines(os.path.join(directory, "build"))
    built = {f[1]: f for f in build or [] if len(f) > 1}
    install = read_lines(os.path.join(directory, "install"))
    installed = {f[0]: f[1] for f in install or [] if len(f) > 1}
    suites = read_lines(os.path.join(directory, "suites"))
    plugin_suites = {f[0]: f[1:] for f in suites or []}
    mtr = mtr_summary(directory)

    statuses = {}
    for plugin in plugins:
        if build is None:
            b = {"status": BUILDER_FAILED}
        elif plugin not in built:
            b = {"status": FAIL, "detail": "not reported by run.cmake"}
        elif built[plugin][0] == "PASS":
            b = {"status": PASS}
        else:
            b = {"status": FAIL, "detail": " ".join(built[plugin][2:])}

        if bintar:
            i = {"status": NOT_APPLICABLE}
        elif b["status"] != PASS:
            i = {"status": NOT_RUN}
        elif install is None:
            i = {"status": BUILDER_FAILED}
        else:
            i = {"status": PASS if installed.get(plugin) == PASS else FAIL}

        ready = (b if bintar else i)["status"] == PASS
        if not ready:
            m = {"status": NOT_RUN}
        elif suites is None:
            m = {"status": BUILDER_FAILED}
        elif plugin not in plugin_suites:
            m = {"status": NO_SUITES}
        elif mtr is None:
            m = {"status": BUILDER_FAILED}
        else:
            failed, completed = mtr
            own = [t for t in failed if t.split(".", 1)[0] in plugin_suites[plugin]]
            if own:
                m = {"status": FAIL, "failed_tests": own}
            elif completed:
                m = {"status": PASS}
            else:
                m = {
                    "status": BUILDER_FAILED,
                    "detail": "MTR ended without its summary",
                }
        statuses[plugin] = {"build": b, "install": i, "mtr": m}
    return statuses


def run_status(run_dir, versions, triggered, plugins, sources):
    # {version: {"tarbuildnum": the CI tarball, or None for the mirrors,
    # "builders": {builder: statuses, or None if it wrote nothing}}}, or
    # {version: None} for a version this run didn't trigger.
    report = {}
    for version, triggerables in versions.items():
        builders = [
            builder
            for triggerable, names in triggerables.items()
            if triggerable in triggered
            for builder in names
        ]
        if not builders:
            report[version] = None
            continue
        source = sources.get(version, "mirror")
        report[version] = {
            "tarbuildnum": None if source == "mirror" else source,
            "builders": {},
        }
        for builder in builders:
            directory = os.path.join(run_dir, version, builder, "status")
            report[version]["builders"][builder] = (
                platform_status(directory, plugins, bintar=builder.endswith("-bintar"))
                if os.path.isdir(directory)
                else None
            )
    return report


CSS = """
body { margin: 0 auto; padding: 0 16px 48px; max-width: 1000px; font: 15px/1.5 system-ui, sans-serif; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 20px; }
caption { text-align: left; font-weight: 600; padding: 6px 0; }
th, td { text-align: left; padding: 6px 10px; border: 1px solid #ccd3d8; vertical-align: top; }
.pass { color: #1f7a4a; } .fail { color: #a93226; font-weight: 600; } .dim { color: #6b7780; }
ul { margin: 4px 0 0; padding-left: 18px; font-family: monospace; }
summary, p.version { font-size: 1.3em; font-weight: 600; margin: 16px 0 4px; }
summary { cursor: pointer; }
summary span, p.version span { font-size: 0.75em; margin-left: 8px; }
.filters { display: flex; flex-wrap: wrap; gap: 8px 20px; align-items: center; }
"""

# Filters the page by plugin and by builder name, and opens or closes every
# MariaDB version.
JS = r"""
const plugin = document.getElementById("plugin");
const builder = document.getElementById("builder");
const versions = document.querySelectorAll("details.version");

// Shows the chosen plugin's rows, in the builders whose name has every word
// typed, and hides a version left without a builder.
function filter() {
  const words = builder.value.toLowerCase().split(/\s+/).filter(Boolean);
  for (const version of versions) {
    let shown = 0;
    for (const table of version.querySelectorAll("table[data-builder]")) {
      const name = table.dataset.builder.toLowerCase();
      table.hidden = !words.every((word) => name.includes(word));
      if (!table.hidden) shown++;
      for (const row of table.querySelectorAll("tr[data-plugin]")) {
        row.hidden = plugin.value !== "" && row.dataset.plugin !== plugin.value;
      }
    }
    version.hidden = shown === 0;
  }
}
plugin.addEventListener("change", filter);
builder.addEventListener("input", filter);

// Opens every version, or closes them all if all are open.
document.getElementById("toggle").addEventListener("click", () => {
  const open = ![...versions].every((version) => version.open);
  for (const version of versions) version.open = open;
});
"""


def badge(status):
    css = "pass" if status == PASS else "fail" if status in RED else "dim"
    return f'<span class="{css}">{html.escape(status)}</span>'


def cell(stage):
    text = badge(stage["status"])
    if stage.get("detail"):
        text += f"<br>{html.escape(stage['detail'])}"
    if stage.get("failed_tests"):
        text += (
            "<ul>"
            + "".join(f"<li>{html.escape(t)}</li>" for t in stage["failed_tests"])
            + "</ul>"
        )
    return f"<td>{text}</td>"


def has_failures(statuses):
    # Whether a builder shows anything red: no status, or a failed stage.
    return statuses is None or any(
        stage["status"] in RED
        for stages in statuses.values()
        for stage in stages.values()
    )


def overview(builders):
    # A version's result in one line, shown next to its name.
    failed = sum(has_failures(statuses) for statuses in builders.values())
    total = f"{len(builders)} builder{'' if len(builders) == 1 else 's'}"
    if failed:
        return f'<span class="fail">failures on {failed} of {total}</span>'
    return f'<span class="pass">no failures on {total}</span>'


def filters(plugins):
    options = "".join(
        f'<option value="{html.escape(p)}">{html.escape(p)}</option>' for p in plugins
    )
    return (
        '<p class="filters">'
        '<label>Plugin <select id="plugin"><option value="">All</option>'
        f"{options}</select></label>"
        '<label>Builder <input id="builder" type="search" '
        'placeholder="e.g. debian aarch64"></label>'
        '<button id="toggle" type="button">Expand or collapse all</button>'
        "</p>"
    )


def render(run_label, commit, plugins, report, ci_url):
    parts = [
        f"<h1>Foundry run {html.escape(run_label)}</h1>",
        f"<p>Commit {html.escape(commit)}. Plugins: {html.escape(', '.join(plugins))}.</p>",
        "<table><caption>What each status means</caption>"
        + "".join(
            f"<tr><td>{badge(status)}</td><td>{html.escape(meaning)}</td></tr>"
            for status, meaning in LEGEND.items()
        )
        + "</table>",
        filters(plugins),
    ]
    # Each triggered version is a section that starts collapsed.
    for version, info in report.items():
        heading = f"MariaDB {html.escape(version)}"
        if info is None:
            parts.append(f'<p class="version">{heading} {badge(NOT_TRIGGERED)}</p>')
            continue
        parts.append(
            f'<details class="version"><summary>{heading} '
            f"{overview(info['builders'])}</summary>"
        )
        if info["tarbuildnum"]:
            tarball = html.escape(info["tarbuildnum"])
            parts.append(
                f'<p>Server packages: CI tarball <a href="{html.escape(ci_url)}/'
                f'{tarball}/">{tarball}</a>.</p>'
            )
        else:
            parts.append("<p>Server packages: MariaDB Server mirrors.</p>")
        for builder, statuses in info["builders"].items():
            name = html.escape(builder)
            # Links to the build's directory: its packages, logs and status.
            caption = (
                f'<caption><a href="{html.escape(version)}/{name}/">{name}</a>'
                "</caption>"
            )
            if statuses is None:
                parts.append(
                    f'<table data-builder="{name}">{caption}'
                    f"<tr><td>{badge(NO_STATUS)}: "
                    "the builder failed before its first Foundry step, or never "
                    "started.</td></tr></table>"
                )
                continue
            rows = "".join(
                f'<tr data-plugin="{html.escape(plugin)}">'
                f"<th>{html.escape(plugin)}</th>"
                + "".join(cell(stages[s]) for s in ("build", "install", "mtr"))
                + "</tr>"
                for plugin, stages in statuses.items()
            )
            parts.append(
                f'<table data-builder="{name}">{caption}'
                "<tr><th>Plugin</th><th>Build</th><th>Install</th><th>MTR</th></tr>"
                f"{rows}</table>"
            )
        parts.append("</details>")
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Foundry run {html.escape(run_label)}</title><style>{CSS}</style>"
        f"</head><body>{''.join(parts)}<script>{JS}</script></body></html>\n"
    )


def main(run_dir, versions_json, triggered, plugins, commit, sources, ci_url):
    plugins = plugins.split()
    sources = dict(entry.split("=", 1) for entry in sources.split())
    report = run_status(
        run_dir, json.loads(versions_json), triggered.split(), plugins, sources
    )
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "status.json"), "w") as f:
        json.dump(report, f, indent=1)
    with open(os.path.join(run_dir, "status.html"), "w") as f:
        f.write(
            render(
                os.path.basename(run_dir.rstrip("/")), commit, plugins, report, ci_url
            )
        )


if __name__ == "__main__":
    main(*sys.argv[1:8])
