"""One dashboard across every eval, built from the reports already on disk.

Ordered by the question being asked, not by what data happens to exist:

    can I ship it  ->  what is the trend  ->  what do I fix  ->  which prompt produced it

The per-metric matrix used to be the front page. It answers none of those directly — you
scanned thirty cells to learn whether a provider was usable — so it moved to a drill-down.

Every point on a trend chart links to the prompt that produced it and opens a browser of the
runs sharing that prompt. Reading lives in dashboard_data.py; this file only renders.

    uv run python tests/prompts/tests/evals/visualize.py [-o OUTPUT.html]
"""

import argparse
import difflib
import html
import json
import pathlib

from accuracy import GATE_THRESHOLDS
from dashboard_data import (
    DATASET_DIRS,
    EVAL_DIRS,
    PRIORITY,
    WIDE_SWING,
    case_stability,
    collect,
    prompt_text,
    prompt_versions,
    read_history,
    score,
    swing,
)

OUTPUT = pathlib.Path("tests/prompts/tests/evals/dashboard.html")
METRIC_ORDER = list(PRIORITY) + [
    "person", "url", "designations_other", "email", "phone", "start_date", "end_date", "image",
]


def _case_link(eval_name: str, case_id: str) -> str:
    """Link a case to the page it was scored against.

    The score says a case failed; the input says why. Both were already on disk with nothing
    connecting them.
    """
    base = DATASET_DIRS.get(eval_name)
    if not base:
        return f"<code>{case_id}</code>"
    return f'<a class="caselink" href="{base}/{case_id}/input.md"><code>{case_id}</code></a>'


def _when(stamp: str | None, length: int = 19) -> str:
    """Seconds kept: concurrent runs share a minute, and truncating made them look identical."""
    return (stamp or "").replace("T", " ").replace("+00:00", "")[:length] or "—"


def _moved(directory: pathlib.Path, provider: str, metric: str) -> float:
    """History stores the full provider name; the rows carry the short one."""
    return swing(directory, f"open_router-{provider}", metric) or swing(directory, provider, metric)


def _verdict(rows: list[dict]) -> str:
    by_eval: dict[str, dict[str, list[dict]]] = {}
    for row in rows:
        by_eval.setdefault(row["eval"], {}).setdefault(row["provider"], []).append(row)
    out = ""
    for name, providers in by_eval.items():
        lines = ""
        for provider, prov in sorted(providers.items()):
            gated = [
                r["metric"] for r in prov
                if r.get("f1") is not None and GATE_THRESHOLDS.get(r["metric"])
                and r["f1"] < GATE_THRESHOLDS[r["metric"]]
            ]
            cases = next((r for r in prov if r["metric"] == "cases passed"), None)
            failed_ids = (cases or {}).get("failed_ids") or []
            blocked = gated or failed_ids
            if cases and cases.get("total"):
                summary = f'{cases["passed"]} of {cases["total"]} cases pass'
            else:
                summary = " · ".join(
                    f"{m} <b>{r['f1']:.2f}</b>" for m in PRIORITY for r in prov
                    if r["metric"] == m and r.get("f1") is not None
                )
            cost = next((r["cost"] for r in prov if r.get("cost") is not None), None)
            detail = (", ".join(f"<code>{x}</code>" for x in gated) if gated
                      else ", ".join(_case_link(name, c) for c in failed_ids))
            note = f'<span class="vnote">fails {detail}</span>' if blocked else ""
            lines += (
                f'<div class="vrow {"vbad" if blocked else "vok"}">'
                f'<span class="vname">{provider}</span>'
                f'<span class="vbadge">{"BLOCKED" if blocked else "READY"}</span>'
                f'<span class="vcore">{summary}</span>'
                f'<span class="vcost">{f"${cost:.4f}" if cost is not None else ""}</span>{note}</div>'
            )
        out += f'<p class="sub2">{name}</p><div class="card">{lines}</div>'
    return out


def _chart(name: str, metric: str, history: list[dict], colour: dict, w: int = 200, h: int = 92) -> str:
    left, bottom, top, right = 28, 16, 9, 7
    iw, ih = w - left - right, h - top - bottom
    grid = "".join(
        f'<line x1="{left}" y1="{top + (1 - g) * ih:.1f}" x2="{w - right}" y2="{top + (1 - g) * ih:.1f}" class="gl"/>'
        f'<text x="{left - 5}" y="{top + (1 - g) * ih + 3:.1f}" class="ax">{g:.1f}</text>'
        for g in (0, 0.5, 1)
    )
    floor = ""
    if GATE_THRESHOLDS.get(metric):
        y = top + (1 - GATE_THRESHOLDS[metric]) * ih
        floor = f'<line x1="{left}" y1="{y:.1f}" x2="{w - right}" y2="{y:.1f}" class="floor"/>'
    body = ""
    for provider in sorted(colour):
        runs = [
            r for r in sorted(history, key=lambda r: r.get("timestamp") or "")
            if (r.get("provider") or "").replace("open_router-", "") == provider
            and metric in (r.get("scores") or {})
        ]
        if len(runs) < 2:
            continue
        pts = " ".join(
            f"{left + iw * i / (len(runs) - 1):.1f},{top + (1 - r['scores'][metric]) * ih:.1f}"
            for i, r in enumerate(runs)
        )
        body += f'<polyline points="{pts}" style="stroke:{colour[provider]}"/>'
        for i, run in enumerate(runs):
            x = left + iw * i / (len(runs) - 1)
            y = top + (1 - run["scores"][metric]) * ih
            sha = run.get("prompt_sha256") or "unknown"
            body += (
                f'<a href="#p-{sha}" class="dot" data-eval="{name}" data-sha="{sha}" '
                f'data-ts="{run.get("timestamp", "")}" data-prov="{provider}" data-metric="{metric}">'
                f'<title>{provider} · {metric} {run["scores"][metric]:.3f}\n'
                f'{_when(run.get("timestamp"))}\nprompt {sha} — click to open</title>'
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" class="hit"/>'
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" style="fill:{colour[provider]}"/></a>'
            )
    star = " ★" if metric in PRIORITY else ""
    return (
        f'<figure class="sm{" pri" if metric in PRIORITY else ""}"><figcaption>{metric}{star}</figcaption>'
        f'<svg viewBox="0 0 {w} {h}" width="100%">{grid}{floor}{body}</svg></figure>'
    )


def _trends() -> str:
    out = ""
    for name, directory in EVAL_DIRS.items():
        history = read_history(directory)
        metrics = {m for r in history for m in (r.get("scores") or {})}
        providers = sorted({(r.get("provider") or "").replace("open_router-", "") for r in history})
        colour = {p: f"var(--p{i + 1})" for i, p in enumerate(providers)}
        plottable = [
            m for m in ([m for m in METRIC_ORDER if m in metrics] + sorted(metrics - set(METRIC_ORDER)))
            if any(
                len([
                    r for r in history
                    if (r.get("provider") or "").replace("open_router-", "") == p
                    and m in (r.get("scores") or {})
                ]) > 1
                for p in providers
            )
        ]
        if not plottable:
            if history:
                out += f'<p class="sub2">{name}</p><p class="ph">only one run recorded — no trend yet</p>'
            continue
        key = "".join(f'<span><i style="background:{colour[p]}"></i>{p}</span>' for p in providers)
        out += (
            f'<p class="sub2">{name}</p><div class="card pad">'
            f'<div class="smgrid">{"".join(_chart(name, m, history, colour) for m in plottable)}</div>'
            f'<p class="hint">Every point links to the prompt that produced it — hover for the run, '
            f'click to open it.</p><div class="key">{key}'
            f'<span class="kfloor">- - - gate floor</span><span>★ priority metric</span></div></div>'
        )
    return out


def _issues(rows: list[dict]) -> str:
    found: list[tuple[int, str]] = []
    for row in rows:
        metric, provider = row["metric"], row["provider"]
        directory = EVAL_DIRS[row["eval"]]
        if metric == "cases passed":
            if row.get("failed_ids"):
                cases = ", ".join(_case_link(row["eval"], c) for c in row["failed_ids"])
                found.append((0, f'<b>{provider}</b> fails {len(row["failed_ids"])} case(s) in '
                                 f'<code>{row["eval"]}</code>: {cases}.'))
            continue
        f1 = row.get("f1")
        if f1 is None:
            continue
        floor = GATE_THRESHOLDS.get(metric)
        wanted = (row.get("correct") or 0) + (row.get("missing") or 0)
        moved = _moved(directory, provider, metric)
        if floor and f1 < floor:
            found.append((0, f"<b>{provider}</b> fails the <code>{metric}</code> gate — scored "
                             f"<b>{f1:.3f}</b>, floor is {floor:.2f}."))
        elif (row.get("missing") or 0) >= 10:
            found.append((1, f'<b>{provider}</b> missed <b>{row["missing"]} of {wanted}</b> '
                             f"<code>{metric}</code> values."))
        elif moved > WIDE_SWING:
            found.append((2, f"<b>{provider}</b>&rsquo;s <code>{metric}</code> swung "
                             f"<b>&plusmn;{moved / 2:.2f}</b> between identical runs — not a quality signal."))
    if not found:
        return '<div class="card"><p class="ph">Nothing to fix — no gate failures, no large gaps.</p></div>'
    found.sort(key=lambda x: x[0])
    return ('<div class="card"><ul class="prose">'
            + "".join(f'<li class="s{s}">{t}</li>' for s, t in found[:12]) + "</ul></div>")


def _prompt_diff(directory: pathlib.Path, new_sha: str, old_sha: str) -> str:
    new, old = prompt_text(directory, new_sha), prompt_text(directory, old_sha)
    if not new or not old:
        return ""
    lines = list(difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=1))
    # The ---/+++ headers begin with the same characters as real changes, so they must be
    # dropped before counting or a one-line edit reads as two additions and two deletions.
    body = [ln for ln in lines if not ln.startswith(("@@", "---", "+++"))]
    if not body:
        return ""
    rendered = "".join(
        f'<span class="d{"add" if ln.startswith("+") else "del" if ln.startswith("-") else "ctx"}">'
        f"{html.escape(ln)}</span>\n" for ln in body
    )
    added = sum(1 for ln in body if ln.startswith("+"))
    removed = sum(1 for ln in body if ln.startswith("-"))
    return (f'<details class="pdiff"><summary>changed vs {old_sha} '
            f'(<span class="dadd">+{added}</span> / <span class="ddel">-{removed}</span>)</summary>'
            f"<pre>{rendered}</pre></details>")


def _prompts() -> str:
    out = ""
    for name, directory in EVAL_DIRS.items():
        versions = prompt_versions(directory)
        if not versions:
            continue
        shas = list(versions)
        blocks = ""
        for i, sha in enumerate(shas):
            entry = versions[sha]
            stamps = sorted(r.get("timestamp") or "" for r in entry["runs"])
            provs = sorted({(r.get("provider") or "").replace("open_router-", "") for r in entry["runs"]})
            diff = _prompt_diff(directory, sha, shas[i + 1]) if i + 1 < len(shas) else ""
            blocks += (
                f'<div class="pver" id="p-{sha}"><div class="pvh"><code>{sha}</code>'
                f'<span class="pvm">{len(entry["runs"])} run(s) · '
                f'{len(entry["text"].splitlines())} lines</span>'
                f'<span class="pvm">{_when(stamps[0], 16)} → {_when(stamps[-1], 16)} · '
                f'{", ".join(provs)}</span></div>{diff}</div>'
            )
        note = ('<p class="ph">Only one version recorded, so there is no diff — a second will add one.</p>'
                if len(versions) == 1 else "")
        out += f'<p class="sub2">{name}</p><div class="card">{note}{blocks}</div>'
    return out


def _bar(value: float | None) -> str:
    if value is None:
        return '<span class="bw"><span class="rail"></span><span class="v">—</span></span>'
    # A true zero draws a tick, not nothing — 0.000 rendering as an empty bar reads as
    # "no data", which is the wrong impression for the number that disqualified a provider.
    fill = ('<span class="zero"></span>' if value == 0 else
            f'<span class="fill{" low" if value < 0.75 else ""}" style="width:{value * 100:.1f}%"></span>')
    return f'<span class="bw"><span class="rail">{fill}</span><span class="v">{value:.3f}</span></span>'


def _case_changes(group: list[dict]) -> str:
    """Which cases moved between the two most recent runs, and in which direction.

    The stability column says whether a case ever moves; this says what it did last. An
    aggregate slipping 0.03 could be one case collapsing or five drifting slightly, and those
    call for opposite responses.
    """
    ordered = sorted(group, key=lambda r: r.get("timestamp") or "")
    if len(ordered) < 2:
        return ""
    latest, prior = ordered[-1].get("cases") or {}, ordered[-2].get("cases") or {}
    worse = sorted(c for c, v in latest.items() if c in prior and v < prior[c] - 1e-9)
    better = sorted(c for c, v in latest.items() if c in prior and v > prior[c] + 1e-9)
    if not worse and not better:
        return '<p class="ph">no case changed between the last two runs</p>'
    out = ""
    if worse:
        out += f'<p class="ph"><span class="flappy">regressed</span> {", ".join(worse)}</p>'
    if better:
        out += f'<p class="ph"><span class="steady">improved</span> {", ".join(better)}</p>'
    return out


def _cases(name: str, directory: pathlib.Path) -> str:
    history = read_history(directory)
    if not history:
        return ""
    changed, compared = case_stability(history)
    latest: dict[str, dict] = {}
    for run in sorted(history, key=lambda r: r.get("timestamp") or ""):
        latest[(run.get("provider") or "?").replace("open_router-", "")] = run.get("cases") or {}
    cases = sorted({c for v in latest.values() for c in v})
    if not cases:
        return ""
    order = sorted(cases, key=lambda c: (min((latest[p].get(c, 1.0) for p in latest), default=1.0), c))
    body = ""
    for case in order:
        tag = ('<span class="flappy">moves</span>' if changed.get(case)
               else '<span class="steady">steady</span>' if compared.get(case) else "")
        cells = "".join(
            '<td class="none">·</td>' if latest[p].get(case) is None
            else f'<td class="hm"><span class="hmv" style="--s:{latest[p][case]:.3f}">'
                 f'{latest[p][case]:.2f}</span></td>'
            for p in sorted(latest)
        )
        body += f"<tr><th>{_case_link(name, case)}</th>{cells}<td>{tag}</td></tr>"
    by_provider: dict[str, list[dict]] = {}
    for run in history:
        by_provider.setdefault((run.get("provider") or "?").replace("open_router-", ""), []).append(run)
    moves = "".join(
        f'<p class="ph"><b>{provider}</b></p>{_case_changes(runs)}'
        for provider, runs in sorted(by_provider.items())
        if _case_changes(runs)
    )
    heads = "".join(f"<th>{p}</th>" for p in sorted(latest))
    return (f"<details><summary>{name} — per case, worst first</summary>{moves}"
            f'<p class="ph"><span class="steady">steady</span> never moved across runs, so a change '
            f'there is real. <span class="flappy">moves</span> varies on an unchanged prompt.</p>'
            f'<table class="dt heat"><thead><tr><th></th>{heads}<th></th></tr></thead>'
            f"<tbody>{body}</tbody></table></details>")


def _detail(rows: list[dict]) -> str:
    out = ""
    for name, directory in EVAL_DIRS.items():
        subset = [r for r in rows if r["eval"] == name]
        if not subset:
            continue
        providers = sorted({r["provider"] for r in subset})
        metrics = {r["metric"] for r in subset}
        ordered = [m for m in METRIC_ORDER if m in metrics] + sorted(metrics - set(METRIC_ORDER))
        lookup = {(r["provider"], r["metric"]): r for r in subset}
        body = ""
        for metric in ordered:
            cells = ""
            for provider in providers:
                row = lookup.get((provider, metric))
                if row is None:
                    cells += '<td class="none">—</td>'
                    continue
                moved = _moved(directory, provider, metric)
                extra = f'<span class="unst">±{moved / 2:.2f}</span>' if moved > WIDE_SWING else ""
                miss = f'<span class="cnt">{row["missing"]} missing</span>' if row.get("missing") else ""
                cells += f"<td>{_bar(score(row))}{extra}{miss}</td>"
            body += f"<tr><th>{metric}</th>{cells}</tr>"
        heads = "".join(f"<th>{p}</th>" for p in providers)
        out += (f"<details><summary>{name} — all metrics</summary>"
                f'<table class="dt"><thead><tr><th></th>{heads}</tr></thead><tbody>{body}</tbody></table>'
                f"</details>{_cases(name, directory)}")
    return f'<div class="card">{out}</div>'


def _modal_payload() -> str:
    payload: dict[str, dict] = {}
    for name, directory in EVAL_DIRS.items():
        versions = prompt_versions(directory)
        if not versions:
            continue
        payload[name] = {
            "runs": [
                {"ts": r.get("timestamp"),
                 "provider": (r.get("provider") or "").replace("open_router-", ""),
                 "sha": r.get("prompt_sha256"), "scores": r.get("scores") or {}}
                for r in read_history(directory)
            ],
            "prompts": {sha: v["text"] for sha, v in versions.items()},
        }
    return json.dumps(payload)


CSS = """
:root{--bg:#fbfaf8;--fg:#1c1b19;--muted:#6c6a66;--faint:#6e6a64;--line:#e6e2db;--card:#fff;
--ok:#2f6f4e;--bad:#a33a2a;--warn:#a8620f;--track:#eeeae3;--p1:#2f6f4e;--p2:#3f6d9e;--p3:#a8620f}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#17181a;--fg:#e8e6e3;
--muted:#9b9894;--faint:#9c968e;--line:#2e3033;--card:#1e2022;--ok:#7fc9a0;--bad:#e0806c;
--warn:#e0a55f;--track:#26282b;--p1:#7fc9a0;--p2:#8ab4e0;--p3:#e0a55f}}
:root[data-theme="dark"]{--bg:#17181a;--fg:#e8e6e3;--muted:#9b9894;--faint:#9c968e;--line:#2e3033;
--card:#1e2022;--ok:#7fc9a0;--bad:#e0806c;--warn:#e0a55f;--track:#26282b;--p1:#7fc9a0;--p2:#8ab4e0;--p3:#e0a55f}
*{box-sizing:border-box}
body{margin:0;padding:2.5rem 1.5rem 6rem;background:var(--bg);color:var(--fg);
font:15px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:900px;margin:0 auto}
h1{font-size:1.5rem;margin:0 0 .2rem}
.sub{color:var(--muted);font-size:.88rem;margin:0 0 1.8rem}
h2{font-size:.82rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);
margin:2.4rem 0 .6rem;font-weight:700}
.sub2{font-size:.8rem;color:var(--faint);margin:.9rem 0 .35rem;font-weight:600;
font-family:ui-monospace,Menlo,monospace}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:.35rem 1.1rem}
.card.pad{padding:1rem 1.1rem}
.vrow{display:flex;align-items:center;gap:.9rem;padding:.72rem 0;border-top:1px solid var(--line);flex-wrap:wrap}
.vrow:first-child{border-top:0}
.vname{font-family:ui-monospace,Menlo,monospace;font-weight:600;min-width:9.5rem}
.vbadge{font-size:.72rem;font-weight:700;letter-spacing:.07em;padding:.18rem .5rem;border-radius:4px}
.vok .vbadge{background:color-mix(in srgb,var(--ok) 16%,transparent);color:var(--ok)}
.vbad .vbadge{background:color-mix(in srgb,var(--bad) 16%,transparent);color:var(--bad)}
.vcore{font-size:.86rem;color:var(--muted)}
.vcore b{color:var(--fg);font-variant-numeric:tabular-nums}
.vcost{margin-left:auto;font-size:.83rem;color:var(--faint);font-variant-numeric:tabular-nums}
.vnote{flex-basis:100%;font-size:.83rem;color:var(--bad);font-weight:600;padding-left:10.4rem}
.smgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(196px,1fr));gap:.85rem}
.sm{margin:0}
.sm figcaption{font-family:ui-monospace,Menlo,monospace;font-size:.8rem;color:var(--muted);margin-bottom:.15rem}
.sm.pri figcaption{color:var(--fg);font-weight:700}
.sm svg polyline{fill:none;stroke-width:1.8;stroke-linejoin:round;stroke-linecap:round}
.gl{stroke:var(--line)}
.ax{font-size:7px;fill:var(--faint);text-anchor:end;font-family:ui-monospace,Menlo,monospace}
.floor{stroke:var(--bad);stroke-dasharray:3 2;opacity:.7}
.dot{cursor:pointer}.dot .hit{fill:transparent}
.hint{font-size:.8rem;color:var(--faint);font-weight:600;margin:.7rem 0 0}
.key{display:flex;gap:1.1rem;margin-top:.5rem;font-size:.82rem;color:var(--muted);flex-wrap:wrap}
.key i{display:inline-block;width:.9rem;height:2px;vertical-align:middle;margin-right:.3rem}
.kfloor{color:var(--bad)}
ul.prose{list-style:none;margin:0;padding:0}
ul.prose li{padding:.55rem .2rem .55rem .85rem;border-top:1px solid var(--line);font-size:.89rem;
border-left:3px solid transparent}
ul.prose li:first-child{border-top:0}
li.s0{border-left-color:var(--bad)}li.s1{border-left-color:var(--warn)}
li.s2{border-left-color:var(--line);color:var(--muted)}
code{font-family:ui-monospace,Menlo,monospace;font-size:.86em;background:var(--track);
padding:.05rem .3rem;border-radius:3px}
.pver{border-top:1px solid var(--line);padding:.6rem 0}
.pver:first-of-type{border-top:0}
.pvh{display:flex;align-items:baseline;gap:.9rem;flex-wrap:wrap}
.pvh code{font-weight:700;font-size:.9rem}
.pvm{font-size:.8rem;color:var(--faint);font-weight:600}
details{border-top:1px solid var(--line);padding:.6rem 0}
details:first-child{border-top:0}
summary{cursor:pointer;font-size:.86rem;color:var(--muted);font-weight:600}
.ph{font-size:.84rem;color:var(--faint);margin:.5rem 0 0;font-weight:500}
table.dt{width:100%;border-collapse:collapse;margin-top:.7rem;font-size:.86rem}
table.dt th,table.dt td{text-align:left;padding:.45rem .5rem;white-space:nowrap;vertical-align:top}
table.dt tbody tr{border-top:1px solid var(--line)}
table.dt tbody th{font-family:ui-monospace,Menlo,monospace;font-weight:500;font-size:.84rem}
table.dt thead th{font-size:.78rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.bw{display:flex;align-items:center;gap:.5rem}
.rail{position:relative;flex:0 0 5.5rem;height:.4rem;background:var(--track);border-radius:3px}
.fill{position:absolute;height:.4rem;background:var(--ok);border-radius:3px}
.fill.low{background:var(--bad)}
.zero{position:absolute;top:-.12rem;left:0;width:2px;height:.64rem;background:var(--bad)}
.v{font-variant-numeric:tabular-nums;font-size:.84rem}
.cnt{display:block;font-size:.8rem;color:var(--faint);font-weight:600;margin-top:.2rem}
.unst{margin-left:.4rem;font-size:.8rem;color:var(--warn);font-weight:700}
.hmv{display:inline-block;min-width:2.9rem;text-align:center;padding:.18rem .35rem;border-radius:4px;
font-size:.82rem;font-weight:600;font-variant-numeric:tabular-nums;color:var(--fg);
background:color-mix(in srgb,var(--ok) calc(var(--s)*65%),color-mix(in srgb,var(--bad) 50%,transparent))}
.steady{color:var(--ok);font-weight:600;font-size:.8rem}
.flappy{color:var(--warn);font-weight:600;font-size:.8rem}
.none{color:var(--faint)}
.pdiff pre{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:.6rem .7rem;
font-size:.8rem;line-height:1.5;overflow-x:auto;max-height:22rem;white-space:pre-wrap;margin:.4rem 0 0}
.pdiff pre span{display:block}
.dadd{color:var(--ok)}.ddel{color:var(--bad)}.dctx{color:var(--faint)}
dialog.pdlg{border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--fg);
max-width:min(880px,93vw);width:100%;padding:0;box-shadow:0 24px 60px rgba(0,0,0,.28)}
dialog.pdlg::backdrop{background:rgba(20,18,16,.55)}
.dlgbar{display:flex;align-items:flex-start;gap:1rem;justify-content:space-between;
padding:.85rem 1rem;border-bottom:1px solid var(--line)}
.dlgbar code{font-weight:700;font-size:.9rem;display:block}
.dlgbar .pvm{display:block;margin-top:.15rem}
.dlgbar button{border:1px solid var(--line);background:var(--bg);color:var(--muted);border-radius:6px;
width:1.9rem;height:1.9rem;cursor:pointer;flex:0 0 auto}
.dlgbar button:hover{color:var(--fg);border-color:var(--muted)}
.bwarn{margin:0;padding:.55rem 1rem;font-size:.8rem;color:var(--faint);font-weight:500;
border-bottom:1px solid var(--line);background:var(--bg);line-height:1.5}
.bwrap{display:flex;align-items:stretch;max-height:min(62vh,640px)}
.bside{flex:0 0 15.5rem;border-right:1px solid var(--line);overflow-y:auto;padding:.5rem}
.bgroup{margin-bottom:.5rem;border:1px solid transparent;border-radius:8px}
.bgroup.on{border-color:var(--line);background:var(--bg)}
.bghead{display:flex;justify-content:space-between;align-items:baseline;width:100%;gap:.5rem;
background:none;border:0;cursor:pointer;padding:.45rem .5rem;color:var(--fg);text-align:left}
.bgsha{font-family:ui-monospace,Menlo,monospace;font-size:.82rem;font-weight:700}
.bgn{font-size:.78rem;color:var(--faint);font-weight:600}
.brun{display:flex;gap:.6rem;width:100%;background:none;border:0;cursor:pointer;text-align:left;
padding:.28rem .5rem .28rem 1rem;color:var(--muted);font-size:.8rem;border-radius:5px}
.brun:hover{background:var(--track);color:var(--fg)}
.brun.sel{background:color-mix(in srgb,var(--warn) 18%,transparent);color:var(--fg);font-weight:600}
.brt{font-family:ui-monospace,Menlo,monospace}
.brp{color:var(--faint)}.brun.sel .brp{color:var(--fg)}
.brs{margin-left:auto;font-variant-numeric:tabular-nums;font-size:.79rem;color:var(--faint);font-weight:600}
.brun.sel .brs{color:var(--fg)}
.caselink{color:inherit;text-decoration:none;border-bottom:1px dotted var(--faint)}
.caselink:hover{border-bottom-style:solid;color:var(--fg)}
#btext{flex:1;margin:0;padding:1rem 1.1rem;font-size:.8rem;line-height:1.55;white-space:pre-wrap;overflow:auto}
"""

SCRIPT = """
const DATA = __DATA__;
let current = {eval: null, sha: null, ts: null, prov: null, metric: null};

// Runs grouped by prompt version, newest first. Grouping rather than listing flat is the
// point: nine runs of one prompt is one entry with nine data points under it, so the
// boundary between prompt versions is the thing you see.
function groups(name) {
  const runs = [...DATA[name].runs].sort((a, b) => (b.ts || '').localeCompare(a.ts || ''));
  const by = new Map();
  runs.forEach(r => { if (!by.has(r.sha)) by.set(r.sha, []); by.get(r.sha).push(r); });
  return [...by.entries()];
}

function render() {
  const g = groups(current.eval);
  document.getElementById('bside').innerHTML = g.map(([sha, runs]) => `
    <div class="bgroup${sha === current.sha ? ' on' : ''}">
      <button class="bghead" data-sha="${sha}">
        <span class="bgsha">${sha}</span><span class="bgn">${runs.length} run(s)</span>
      </button>
      ${runs.map(r => `
        <button class="brun${r.ts === current.ts && r.provider === current.prov && sha === current.sha ? ' sel' : ''}"
                data-sha="${sha}" data-ts="${r.ts}" data-prov="${r.provider}">
          <span class="brt">${(r.ts || '').slice(11, 19)}</span>
          <span class="brp">${r.provider}</span>
          <span class="brs">${current.metric && r.scores[current.metric] != null
            ? r.scores[current.metric].toFixed(3) : ''}</span>
        </button>`).join('')}
    </div>`).join('');

  const runs = (g.find(([s]) => s === current.sha) || [null, []])[1];
  const text = DATA[current.eval].prompts[current.sha] || '(not archived)';
  document.getElementById('bsha').textContent = current.sha || '—';
  document.getElementById('bmeta').textContent =
    `${current.eval} · ${runs.length} run(s) · ${text.split('\\n').length} lines`
    + (current.metric ? ` · column shows ${current.metric}` : '');
  document.getElementById('btext').textContent = text;

  document.querySelectorAll('#bside .bghead, #bside .brun').forEach(b =>
    b.addEventListener('click', e => {
      e.preventDefault();
      current.sha = b.dataset.sha;
      if (b.dataset.ts) { current.ts = b.dataset.ts; current.prov = b.dataset.prov; }
      render();
    }));
}

// Progressive enhancement: the points are real anchors to the prompt sections, so the page
// still works with JS off. When it runs, a click opens the prompt without scrolling away
// from the chart being read.
document.querySelectorAll('a.dot').forEach(a => {
  a.addEventListener('click', e => {
    const dlg = document.getElementById('browser');
    if (!dlg || !dlg.showModal || !DATA[a.dataset.eval]) return;
    e.preventDefault();
    current = {eval: a.dataset.eval, sha: a.dataset.sha, ts: a.dataset.ts,
               prov: a.dataset.prov, metric: a.dataset.metric};
    render();
    dlg.showModal();
  });
});
const browser = document.getElementById('browser');
if (browser) browser.addEventListener('click', e => { if (e.target === browser) browser.close(); });
"""

MODAL = """
<dialog id="browser" class="pdlg">
  <form method="dialog" class="dlgbar">
    <div><code id="bsha">—</code><span class="pvm" id="bmeta"></span></div>
    <button value="close" aria-label="Close">&#10005;</button>
  </form>
  <p class="bwarn">System prompt only. Each run sends this once per case, with that case&rsquo;s page
  content as the user message; <code>&lt;injected per case&gt;</code> marks the block that varies.</p>
  <div class="bwrap"><aside class="bside" id="bside"></aside><pre id="btext"></pre></div>
</dialog>"""


def render(rows: list[dict]) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eval Dashboard</title>
<style>{CSS}
</style>
</head>
<body>
<main>
<h1>Eval dashboard</h1>
<p class="sub">Regenerated after every eval run. Read top to bottom: can I ship it &rarr; what is the
trend &rarr; what do I fix &rarr; which prompt produced it.</p>

<h2>Can I ship it</h2>
{_verdict(rows)}

<h2>What is the trend</h2>
{_trends()}

<h2>What do I fix</h2>
{_issues(rows)}

<h2>Which prompt produced it</h2>
{_prompts()}

<h2>Detail</h2>
{_detail(rows)}
</main>
{MODAL}
<script>{SCRIPT.replace("__DATA__", _modal_payload())}</script>
</body>
</html>
"""


def write_dashboard(output: pathlib.Path = OUTPUT) -> int:
    """Render whatever reports exist. Returns the row count, 0 if there was nothing to read.

    Split from main() so the evals' conftest can call it on session finish — the dashboard is
    only useful if it is current, and regenerating it by hand is the step that gets skipped.
    """
    rows = collect()
    if not rows:
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(rows), encoding="utf-8")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", type=pathlib.Path, default=OUTPUT)
    args = parser.parse_args()
    count = write_dashboard(args.output)
    if not count:
        print("No eval reports found — run the evals first.")
        return
    print(f"Wrote {args.output.resolve()} from {count} row(s)")


if __name__ == "__main__":
    main()
