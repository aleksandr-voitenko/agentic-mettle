#!/usr/bin/env python3
"""Opt-in synthetic benchmark. Creates disposable installations only; no model calls."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import platform
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(SOURCE / "tests"))
import mettle as m
import mettle_work as w
import mettle_catalogue as c
from examples.scalability_fixture import CountingRecords, old_indexes, put, record, seed
from reference_retrieval_031 import retrieve_031


def worker(root, command, reference):
    counts = {"canonical_reads": 0, "current_view_reads": 0, "other_reads": 0,
              "derived_writes": 0, "catalogue_writes": 0, "other_writes": 0,
              "decodes": 0, "snapshot_calls": 0, "inventory_passes": 0, "inventory_entries": 0, "catalogue_connections": 0}
    archives = []
    original_read, original_write, original_snapshot = m.read, m.write_atomic, m.Store.snapshot

    original_decode, original_inventory, original_connect = m.decode, c.inventory, c.connect

    def decode(text):
        counts["decodes"] += 1
        return original_decode(text)

    def inventory(api, store):
        entries = original_inventory(api, store)
        counts["inventory_passes"] += 1
        counts["inventory_entries"] += len(entries)
        return entries

    def connect(path):
        counts["catalogue_connections"] += 1
        return original_connect(path)

    def reference_page(api, store, query, limit, scope, kind="lessons", work_id=None, **kwargs):
        return {"candidates": retrieve_031(api, store, query, limit, scope, kind, work_id)}

    @contextlib.contextmanager
    def reference_catalogue(api, store):
        # The former show command's complete snapshot lookup; no cached reads.
        records, lessons = store.snapshot()
        class Reference:
            def get(self, identifier, revision=None):
                if identifier in lessons:
                    return lessons[identifier][revision - 1 if revision else -1]
                return records[identifier]
        yield Reference()

    def read(path):
        category = ("canonical_reads" if "revisions" in path.parts or
                    any(name in path.parts for name in m.DIRECTORIES.values()) else
                    "current_view_reads" if path.name == "current.md" else "other_reads")
        counts[category] += 1
        return original_read(path)

    def write(path, text, **kwargs):
        key = ("catalogue_writes" if path.name == "catalogue.sqlite3" else
               "derived_writes" if path.name in {"current.md", "INDEX.md"} else "other_writes")
        counts[key] += 1
        return original_write(path, text, **kwargs)

    def snapshot(store, **kwargs):
        counts["snapshot_calls"] += 1
        records, lessons = original_snapshot(store, **kwargs)
        counted = CountingRecords(records)
        archives.append(counted)
        return counted, lessons

    output, errors = io.StringIO(), io.StringIO()
    with mock.patch.object(m, "read", side_effect=read), mock.patch.object(m, "write_atomic", side_effect=write), \
            mock.patch.object(m.Store, "snapshot", snapshot), \
            mock.patch.object(m, "decode", side_effect=decode), \
            mock.patch.object(c, "inventory", side_effect=inventory), \
            mock.patch.object(c, "connect", side_effect=connect), \
            mock.patch.object(c, "open_catalogue", reference_catalogue if reference else c.open_catalogue), \
            mock.patch.object(w, "search_page", reference_page if reference else w.search_page), \
            contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        start = time.perf_counter()
        code = m.main([*command, "--root", root])
        elapsed = time.perf_counter() - start
    if code:
        raise RuntimeError(errors.getvalue())
    text = output.getvalue()
    counts.update(relationship_visits=sum(a.visits for a in archives),
                  relationship_passes=sum(a.passes for a in archives), command_seconds=elapsed,
                  output_bytes=len(text.encode("utf-8")), output_characters=len(text))
    if command[0] == "search":
        counts["results"] = json.loads(text)["candidates"]
    return counts


def run_command(root, command, reference=False):
    start = time.perf_counter()
    result = subprocess.run([sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
                             "--worker", str(root), "--command-json", json.dumps(command),
                             *(["--reference"] if reference else [])],
                            capture_output=True, encoding="utf-8", check=True)
    stats = json.loads(result.stdout)
    stats["process_seconds"] = time.perf_counter() - start
    return stats


def sizes(store, lessons):
    old, new = old_indexes(store, lessons), store.indexes(lessons)
    root = store.path("memory/INDEX.md")
    return {"old_root_bytes": len(old[root].encode("utf-8")), "root_bytes": len(new[root].encode("utf-8")),
            "old_largest_index_bytes": max(len(s.encode("utf-8")) for s in old.values()),
            "largest_index_bytes": max(len(s.encode("utf-8")) for s in new.values()),
            "generated_index_count": len(new)}


def benchmark(args):
    report = {"environment": {"platform": platform.platform(), "python": sys.version,
                              "processor": platform.processor(), "temporary_directory": tempfile.gettempdir()},
              "repetitions": args.repetitions, "lessons": args.lessons, "domains": args.domains,
              "note": "Synthetic local warm-cache measurements, not Windows predictions or LLM behavior. "
                      "Process time includes instrumented wrapper startup; command time includes CLI parsing, locking, "
                      "validation, ranking/enrichment and output. Reference uses frozen 0.3.1 retrieval and full-snapshot show. "
                      "Read counts cover mettle.read; inventory counts are canonical entries enumerated, not stat syscalls. "
                      "Catalogue connections count logical SQLite opens, not page I/O. Cold means no catalogue, not flushed OS caches.",
              "archives": []}
    for episodes in args.episodes:
        with tempfile.TemporaryDirectory(prefix="mettle-benchmark-") as temporary:
            root = Path(temporary).resolve()
            m.install(root, [])
            store = m.Store(root)
            _, lessons = seed(store, episodes=episodes, lessons=args.lessons, domains=args.domains)
            entry = {"episodes": episodes, **sizes(store, lessons), "search": [], "cold_show": [], "warm_show": []}
            for _ in range(args.repetitions):
                store.path(c.RELATIVE).unlink(missing_ok=True)
                entry["cold_show"].append(run_command(root, ["show", "E-00000"]))
                entry["warm_show"].append(run_command(root, ["show", "E-00000"]))
            entry["before_show"] = run_command(root, ["show", "E-00000"], True)
            entry["catalogue_bytes"] = store.path(c.RELATIVE).stat().st_size
            store.path(c.RELATIVE).unlink()
            entry["cold_search"] = run_command(root, ["search", "--kind", "episodes", "--limit", "3", "amberwidget"])
            entry["cold_search"].pop("results")
            for kind in ("lessons", "episodes"):
                for query in ("needle00000", "amberwidget"):
                    runs = {"before": [], "after": []}
                    for _ in range(args.repetitions):
                        before = run_command(root, ["search", "--kind", kind, "--limit", "3", query], True)
                        after = run_command(root, ["search", "--kind", kind, "--limit", "3", query])
                        assert before.pop("results") == after.pop("results"), "Retrieval parity failure"
                        runs["before"].append(before)
                        runs["after"].append(after)
                    entry["search"].append({"kind": kind, "query": query, "limit": 3, "runs": runs,
                                            "median_process_seconds": {key: statistics.median(r["process_seconds"] for r in values)
                                                                       for key, values in runs.items()}})
            entry["warm_navigate"] = run_command(root, ["navigate", "--domain", "domain-0000", "--limit", "3"])
            entry["bootstrap"] = run_command(root, ["bootstrap"])
            draft = root / "synthetic-episode.md"
            draft.write_text(record("episode", "E-benchmark-new"), encoding="utf-8")
            entry["episode_publication"] = run_command(root, ["publish", str(draft)])
            entry["old_episode_derived_writes_from_loop"] = len(lessons) + len(store.indexes(lessons))
            entry["unchanged_reindex"] = run_command(root, ["reindex"])
            report["archives"].append(entry)
    if args.navigation_stress:
        with tempfile.TemporaryDirectory(prefix="mettle-navigation-benchmark-") as temporary:
            root = Path(temporary).resolve()
            m.install(root, [])
            store = m.Store(root)
            seed(store, episodes=20, lessons=500, long_metadata=True)
            for number in range(1, 401):
                put(store, record("lesson", f"L-domain-{number:04d}", origin=["E-00000"],
                                  scope=["synthetic"], domain=f"domain-{number:04d}"))
            _, lessons = store.snapshot(verify_views=False)
            store.reindex(lessons)
            report["navigation_stress"] = {"episodes": 20, "lessons": 900, "domains": 401,
                                           "large_domain_lessons": 500, **sizes(store, lessons),
                                           "bootstrap": run_command(root, ["bootstrap"]),
                                           "navigate": run_command(root, ["navigate"]),
                                           "check": run_command(root, ["check"])}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, nargs="+", default=[1000, 5000, 10000])
    parser.add_argument("--lessons", type=int, default=100)
    parser.add_argument("--domains", type=int, default=10)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--navigation-stress", action="store_true")
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--command-json", help=argparse.SUPPRESS)
    parser.add_argument("--reference", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker, json.loads(args.command_json), args.reference)))
    else:
        if min(*args.episodes, args.lessons, args.domains, args.repetitions) < 1:
            parser.error("All counts must be positive")
        print(json.dumps(benchmark(args), indent=2))


if __name__ == "__main__":
    main()
