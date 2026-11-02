"""Deterministic synthetic setup shared by regression tests and the opt-in benchmark.

Never point this at a real personality. Fixtures bypass publication for linear
setup cost, then validate the whole canonical graph before building derived views.
"""
import mettle as m


def record(kind, identifier, **fields):
    meta, body = m.decode(m.template(kind))
    meta.update(id=identifier, title="Synthetic amberwidget policy",
                created_at="2026-01-01T00:00:00+00:00")
    meta.update(fields)
    return m.encode(meta, body.replace("TODO", "Authored synthetic evidence only; no model behavior measured."))


def put(store, text):
    m.local_module("mettle_catalogue").invalidate(m, store)
    meta, _ = m.decode(text)
    if meta["kind"] == "lesson":
        relative = f"memory/lessons/{meta['domain']}/{meta['id']}/revisions/{meta['revision']:04d}.md"
    else:
        relative = f"memory/{m.DIRECTORIES[meta['kind']]}/2026/01/{meta['id']}.md"
    path = store.path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
    return path


def seed(store, *, episodes=20, lessons=10, domains=1, long_metadata=False):
    if episodes < 1 or domains < 1:
        raise ValueError("Synthetic fixtures need at least one episode and domain")
    for number in range(episodes):
        put(store, record("episode", f"E-{number:05d}",
                          title=f"Synthetic amberwidget policy needle{number:05d} component/{number % 2}"))
    for number in range(lessons):
        fields = dict(origin=["E-00000"], scope=[f"component/{number % 2}"],
                      domain=f"domain-{number % domains:04d}",
                      title=f"Synthetic amberwidget policy needle{number:05d}",
                      tags=["café", "日本"], aliases=["source of truth"])
        if long_metadata:
            fields.update(title=fields["title"] + ' 日本é"\\' * 45,
                          scope=[fields["scope"][0], "条件" * 250],
                          aliases=["source of truth", "é" * 300, "symbol_name", "fourth alias"])
        put(store, record("lesson", f"L-{number:05d}", **fields))
    records, lesson_map = store.snapshot(verify_views=False)
    store.reindex(lesson_map)
    return records, lesson_map


class CountingRecords(dict):
    """Count relationship-pass visits after canonical validation, without timings."""
    def __init__(self, entries):
        super().__init__(entries)
        self.visits = 0
        self.passes = 0

    def items(self):
        self.passes += 1
        for item in super().items():
            self.visits += 1
            yield item


def old_indexes(store, lessons):
    """0.3.0 index serialization, retained only for before/after size evidence."""
    import json
    domains = {}
    for versions in lessons.values():
        meta, body, path = versions[-1]
        domains.setdefault(meta["domain"], []).append((meta, path.parent.parent))
    root_lines = ["# Memory directory map", "", "Generated navigation, not additional instructions.", "", "Search current lessons; read a full record before applying it.", "", "## Domains"]
    outputs = {}
    for domain, entries in sorted(domains.items()):
        root_lines.append(f"- {domain}: {len(entries)} lesson(s); memory/lessons/{domain}/INDEX.md")
        lines = [f"# {domain}", "", "Generated current-record index; never apply a snippet without its full record.", ""]
        for meta, folder in sorted(entries, key=lambda item: item[0]["id"]):
            row = {key: meta[key] for key in ("id", "revision", "status", "title", "scope", "tags", "aliases")}
            row["path"] = (folder / "current.md").relative_to(store.root).as_posix()
            lines.append(json.dumps(row, ensure_ascii=False))
        outputs[store.path(f"memory/lessons/{domain}/INDEX.md")] = "\n".join(lines) + "\n"
    if not domains:
        root_lines.append("- No lessons yet. This is a fresh history, not an error.")
    outputs[store.path("memory/INDEX.md")] = "\n".join(root_lines) + "\n"
    return outputs
