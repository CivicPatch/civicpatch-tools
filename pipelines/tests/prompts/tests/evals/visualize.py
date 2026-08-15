"""One dashboard across every eval, built from the reports already on disk.

The four evals do not agree on a report shape yet — officials emits disposition counts per
field, relevant_page and find_jurisdiction_url emit a failed-case list, role_normalization
emits its own summary. Rather than rewrite three scorers to converge them (which would mean
discarding the only record of a real failure while doing it), each shape gets a small
adapter into one row type here. Converging the scorers can then happen one at a time
without the dashboard changing.

Reads only — never runs an eval and never edits a fixture. Run it after `mise run evals`.

    uv run python tests/prompts/tests/evals/visualize.py [-o OUTPUT.html]
"""

import argparse
import pathlib

import yaml

EVALS = pathlib.Path("tests/prompts/tests/evals")
OUTPUT = pathlib.Path("../.scratch/2026-08-15-eval-dashboard.html")


def _load(path: pathlib.Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _rate(row: dict) -> float | None:
    """Every eval reduces to "what fraction went right", however it counts."""
    if row.get("total"):
        return row["passed"] / row["total"]
    return None


def read_officials() -> list[dict]:
    """Disposition counts per field — the only eval that already reports precision/recall."""
    rows = []
    directory = EVALS / "municipal_officials"
    comparison = _load(directory / "comparison.yml").get("providers") or {}
    for provider in comparison:
        accuracy = _load(directory / f"{provider}-eval-report.yml").get("accuracy") or {}
        if not accuracy:
            continue
        for field, counts in accuracy.items():
            rows.append(
                {
                    "eval": "officials",
                    "provider": provider.replace("open_router-", ""),
                    "metric": field,
                    "f1": counts.get("f1"),
                    "correct": counts.get("correct"),
                    "missing": counts.get("missing"),
                    "spurious": counts.get("spurious"),
                    "wrong": counts.get("wrong"),
                    "cost": comparison[provider].get("cost_usd"),
                    "seconds": comparison[provider].get("elapsed_seconds"),
                }
            )
    return rows


def _from_failed_cases(name: str, directory: pathlib.Path) -> list[dict]:
    """relevant_page and find_jurisdiction_url both report a failed-case list and nothing
    else, so pass/total is the most that can honestly be derived. They gain real
    precision/recall only once their scorers move to dispositions."""
    rows = []
    comparison = _load(directory / "comparison.yml").get("providers") or {}
    for path in sorted(directory.glob("*-eval-report.yml")):
        provider = path.name.removesuffix("-eval-report.yml")
        report = _load(path)
        if "failed_cases" not in report:
            continue
        summary = comparison.get(provider, {})
        failed = len(report["failed_cases"])
        passed = summary.get("passed_cases")
        total = (passed + failed) if passed is not None else None
        rows.append(
            {
                "eval": name,
                "provider": provider.replace("open_router-", ""),
                "metric": "cases passed",
                "passed": passed if passed is not None else 0,
                "total": total,
                "failed": failed,
                "cost": (report.get("cost_summary") or {}).get("total_cost_usd"),
                "seconds": (report.get("cost_summary") or {}).get("elapsed_seconds"),
            }
        )
    return rows


def read_role_normalization() -> list[dict]:
    summary = _load(EVALS / "role_normalization" / "eval-report.yml").get("summary") or {}
    if not summary:
        return []
    return [
        {
            "eval": "role_normalization",
            "provider": "offline",
            "metric": "labels normalized",
            "f1": summary.get("f1"),
            "correct": summary.get("correct"),
            "missing": summary.get("false_negatives"),
            "spurious": summary.get("false_positives"),
            "wrong": summary.get("wrong_matches"),
            "passed": summary.get("correct"),
            "total": summary.get("total"),
            "cost": 0.0,
        }
    ]


def collect() -> list[dict]:
    return (
        read_officials()
        + _from_failed_cases("relevant_page", EVALS / "relevant_page")
        + _from_failed_cases("find_jurisdiction_url", EVALS / "find_jurisdiction_url")
        + read_role_normalization()
    )


def _score(row: dict) -> float | None:
    return row["f1"] if row.get("f1") is not None else _rate(row)


def _bar(value: float | None, width: int = 150) -> str:
    if value is None:
        return '<span class="na">—</span>'
    low = value < 0.75
    return (
        f'<span class="bw" style="--w:{width}px">'
        f'<span class="fill{" low" if low else ""}" style="width:{value * width:.1f}px"></span>'
        f'<span class="v">{value:.3f}</span></span>'
    )


def _counts(row: dict) -> str:
    if row.get("correct") is None:
        failed = row.get("failed")
        return f'<span class="c">{row.get("passed", 0)} passed</span>, {failed} failed' if failed is not None else ""
    return (
        f'<span class="c">{row["correct"]}</span> / '
        f'<span class="m">{row["missing"]}</span> / '
        f'<span class="s">{row["spurious"]}</span> / '
        f'<span class="w">{row["wrong"]}</span>'
    )


def render(rows: list[dict]) -> str:
    by_eval: dict[str, list[dict]] = {}
    for row in rows:
        by_eval.setdefault(row["eval"], []).append(row)

    sections = ""
    for name, group in by_eval.items():
        body = "".join(
            f"<tr><th>{r['provider']}</th><td>{r['metric']}</td>"
            f"<td>{_bar(_score(r))}</td><td class='cnt'>{_counts(r)}</td>"
            f"<td class='num'>{('$%.4f' % r['cost']) if r.get('cost') is not None else '—'}</td>"
            f"<td class='num'>{('%.0fs' % r['seconds']) if r.get('seconds') else '—'}</td></tr>"
            for r in sorted(group, key=lambda x: (x["provider"], x["metric"]))
        )
        sections += (
            f"<h2>{name}</h2><div class='card scroll'><table>"
            f"<thead><tr><th>provider</th><th>metric</th><th>score</th>"
            f"<th>correct / missing / spurious / wrong</th>"
            f"<th class='num'>cost</th><th class='num'>time</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div>"
        )

    return f"""<title>Eval Dashboard</title>
<style>
:root{{--bg:#fbfaf8;--fg:#1c1b19;--muted:#6c6a66;--line:#e2ded7;--card:#fff;--ok:#2f6f4e;--warn:#a8620f;--bad:#a33a2a;--pale:#cfe3d6}}
@media(prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#17181a;--fg:#e8e6e3;--muted:#9b9894;--line:#2e3033;--card:#1e2022;--ok:#7fc9a0;--warn:#e0a55f;--bad:#e0806c;--pale:#2c4438}}}}
:root[data-theme="dark"]{{--bg:#17181a;--fg:#e8e6e3;--muted:#9b9894;--line:#2e3033;--card:#1e2022;--ok:#7fc9a0;--warn:#e0a55f;--bad:#e0806c;--pale:#2c4438}}
*{{box-sizing:border-box}}
body{{margin:0;padding:2.5rem 1.25rem 5rem;background:var(--bg);color:var(--fg);font:15px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:1080px;margin:0 auto}}
h1{{font-size:1.6rem;margin:0 0 .3rem}}
h2{{font-size:1.02rem;margin:2.2rem 0 .7rem;padding-bottom:.35rem;border-bottom:1px solid var(--line);font-family:ui-monospace,Menlo,monospace}}
.sub{{color:var(--muted);margin:0 0 1.5rem;font-size:.92rem}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:.6rem .9rem}}
.scroll{{overflow-x:auto}}
table{{border-collapse:collapse;width:100%;font-size:.86rem}}
th,td{{text-align:left;padding:.36rem .5rem;border-bottom:1px solid var(--line);white-space:nowrap;vertical-align:middle}}
thead th{{color:var(--muted);font-weight:600;font-size:.73rem;text-transform:uppercase;letter-spacing:.03em}}
tbody th{{font-weight:500;font-family:ui-monospace,Menlo,monospace;font-size:.82rem}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
.bw{{position:relative;display:inline-block;width:var(--w);height:1.05rem;vertical-align:middle}}
.fill{{position:absolute;top:.3rem;height:.45rem;background:var(--ok);border-radius:3px}}
.fill.low{{background:var(--bad)}}
.v{{position:absolute;right:-2.9rem;font-size:.8rem;color:var(--muted);font-variant-numeric:tabular-nums}}
td:nth-child(3){{padding-right:3.1rem}}
.cnt{{font-variant-numeric:tabular-nums;font-size:.82rem;color:var(--muted)}}
.c{{color:var(--ok);font-weight:600}} .m{{color:var(--bad)}} .s{{color:var(--warn)}} .w{{color:#6b6b6b}}
.na{{color:var(--muted)}}
.note{{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--warn);border-radius:10px;padding:.8rem 1rem;margin:1.2rem 0;font-size:.9rem}}
</style>
<main>
<h1>Eval dashboard</h1>
<p class="sub">Built from the report files on disk — run the evals first, then this. Red bars are below 0.75.</p>
<div class="note">
Only <b>officials</b> reports true precision/recall, because only it scores dispositions.
<b>relevant_page</b> and <b>find_jurisdiction_url</b> record a pass/fail case list, so their
bar is the pass rate and the counts column cannot break down <i>how</i> a case failed.
Converging those scorers onto dispositions is what would make these columns comparable.
</div>
{sections}
</main>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", type=pathlib.Path, default=OUTPUT)
    args = parser.parse_args()
    rows = collect()
    if not rows:
        print("No eval reports found — run the evals first.")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(rows), encoding="utf-8")
    print(f"Wrote {args.output.resolve()} from {len(rows)} row(s) across "
          f"{len({r['eval'] for r in rows})} eval(s)")


if __name__ == "__main__":
    main()
