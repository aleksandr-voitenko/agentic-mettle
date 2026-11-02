"""Disposable canonical-memory lookup and targeted validation. Stdlib only.

Call under the existing store lock. This is neither accepted memory nor an audit
of unrelated canonical contents. See docs/targeted-access.md for the boundary.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile

FORMAT = 1
LEXICAL_VERSION = "phrases-v1-sequences-1"
RELATIVE = "memory/catalogue.sqlite3"


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def inventory(api, store):
    """Enumerate protected paths/stat metadata, without opening canonical bodies."""
    entries = {}
    for folder in [*api.DIRECTORIES.values(), "lessons"]:
        for path in store.files("memory/" + folder, "*.md"):
            if folder == "lessons" and path.parent.name != "revisions":
                continue
            info = path.stat()
            api.require(path.is_file(), f"Not a canonical file: {path}")
            entries[path.relative_to(store.root).as_posix()] = (
                info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_dev, info.st_ino)
    return dict(sorted(entries.items()))


def invalidate(api, store):
    # Before accepted publication, not after it: interruption cannot leave an old
    # complete catalogue available to a later cooperating reader.
    store.path(RELATIVE).unlink(missing_ok=True)


def lexical(api, meta, body):
    work = api.local_module("mettle_work")
    fields = [meta["id"], meta["title"], meta.get("domain", ""),
              *meta.get("tags", []), *meta.get("aliases", []), *meta.get("scope", [])]
    return {"header": [work.token_sequence(s) for s in fields],
            "body": [work.token_sequence(body)],
            # Preserve the old episode scope substring filter, including punctuation.
            "episode_scope": (meta["title"] + " " + body).casefold() if meta["kind"] == "episode" else ""}


def rebuild(api, store, snapshot, before=None):
    records, lessons = snapshot
    before = inventory(api, store) if before is None else before
    entries = [*records.values(), *(entry for versions in lessons.values() for entry in versions)]
    api.require({p.relative_to(store.root).as_posix() for _, _, p in entries} == set(before),
                "Canonical inventory changed during validation; retry or run reindex --repair")
    metadata = {"format": FORMAT, "lexical": LEXICAL_VERSION, "root": str(store.root),
                "inventory": fingerprint(before), "records": len(entries), "derived": True}
    with tempfile.TemporaryDirectory(prefix="mettle-catalogue-") as temporary:
        path = Path(temporary) / "catalogue.sqlite3"
        db = sqlite3.connect(path)
        try:
            db.executescript("""
                CREATE TABLE info (value TEXT NOT NULL);
                CREATE TABLE records (
                    id TEXT NOT NULL, revision INTEGER NOT NULL, kind TEXT NOT NULL,
                    path TEXT UNIQUE NOT NULL, source_hash TEXT NOT NULL,
                    metadata TEXT NOT NULL, lexical TEXT NOT NULL, ordinal INTEGER NOT NULL,
                    PRIMARY KEY (id, revision));
                CREATE TABLE links (source TEXT NOT NULL, target TEXT NOT NULL, relation TEXT NOT NULL);
                CREATE INDEX reverse_links ON links (target, relation);
            """)
            db.execute("INSERT INTO info VALUES (?)", (json.dumps(metadata),))
            for ordinal, (meta, body, canonical) in enumerate(entries):
                features = lexical(api, meta, body) if meta["kind"] in {"lesson", "episode"} else {}
                db.execute("INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           (meta["id"], meta.get("revision", 0) if meta["kind"] == "lesson" else 0,
                            meta["kind"], canonical.relative_to(store.root).as_posix(),
                            api.digest(api.encode(meta, body)), json.dumps(meta, ensure_ascii=False),
                            json.dumps(features, ensure_ascii=False), ordinal))
                if meta["kind"] == "episode":
                    db.executemany("INSERT INTO links VALUES (?, ?, 'corrects')",
                                   [(meta["id"], target) for target in meta["corrects"]])
                elif meta["kind"] == "review" and meta["assessment"] == "counterexample":
                    db.execute("INSERT INTO links VALUES (?, ?, 'counterexample')", (meta["id"], meta["lesson"]))
            db.commit()
        finally:
            db.close()
        api.require(inventory(api, store) == before, "Canonical inventory changed during catalogue rebuild; retry")
        target, content = store.path(RELATIVE), path.read_bytes()
        if not target.is_file() or target.read_bytes() != content:
            api.write_atomic(target, content)


def connect(path):
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA trusted_schema=OFF")
        return db
    except sqlite3.Error:
        db.close()
        raise


def check(api, store, snapshot):
    """Audit an existing catalogue against an already verified full snapshot.

    Missing is normal after publication; this audit never creates derived state.
    """
    path = store.path(RELATIVE)
    if not path.exists():
        return "absent; next targeted read rebuilds it"
    records, lessons = snapshot
    entries = [*records.values(), *(entry for versions in lessons.values() for entry in versions)]
    observed = inventory(api, store)
    db = None
    try:
        db = connect(path)
        info = json.loads(db.execute("SELECT value FROM info").fetchone()[0])
        expected = {"format": FORMAT, "lexical": LEXICAL_VERSION, "root": str(store.root),
                    "inventory": fingerprint(observed), "records": len(entries), "derived": True}
        api.require(info == expected and db.execute("PRAGMA quick_check").fetchone()[0] == "ok",
                    "Stale or incompatible catalogue; run reindex --repair")
        rows = db.execute("SELECT * FROM records ORDER BY ordinal").fetchall()
        api.require(len(rows) == len(entries), "Incomplete catalogue; run reindex --repair")
        links = []
        for ordinal, (row, (meta, body, canonical)) in enumerate(zip(rows, entries)):
            expected_features = lexical(api, meta, body) if meta["kind"] in {"episode", "lesson"} else {}
            api.require(api.safe_path(store.root, row["path"]) == canonical
                        and row["id"] == meta["id"] and row["kind"] == meta["kind"]
                        and row["revision"] == (meta["revision"] if meta["kind"] == "lesson" else 0)
                        and row["ordinal"] == ordinal and json.loads(row["metadata"]) == meta
                        and row["source_hash"] == api.digest(api.encode(meta, body))
                        and fingerprint(json.loads(row["lexical"])) == fingerprint(expected_features),
                        "Catalogue contents disagree with canonical records; run reindex --repair")
            if meta["kind"] == "episode":
                links.extend((meta["id"], target, "corrects") for target in meta["corrects"])
            elif meta["kind"] == "review" and meta["assessment"] == "counterexample":
                links.append((meta["id"], meta["lesson"], "counterexample"))
        api.require(sorted(tuple(row) for row in db.execute("SELECT source, target, relation FROM links")) == sorted(links),
                    "Catalogue relationships disagree with canonical records; run reindex --repair")
        return "verified against canonical snapshot"
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError) as exc:
        raise api.MettleError(f"Invalid derived catalogue; run reindex --repair: {exc}") from exc
    finally:
        if db is not None:
            db.close()


@contextlib.contextmanager
def open_catalogue(api, store):
    observed = inventory(api, store)
    path = store.path(RELATIVE)
    db = None
    try:
        try:
            db = connect(path)
            info = json.loads(db.execute("SELECT value FROM info").fetchone()[0])
            expected = {"format": FORMAT, "lexical": LEXICAL_VERSION, "root": str(store.root),
                        "inventory": fingerprint(observed), "records": len(observed), "derived": True}
            if (info != expected or db.execute("PRAGMA quick_check").fetchone()[0] != "ok"
                    or {row[0] for row in db.execute("SELECT path FROM records")} != set(observed)):
                raise ValueError("Stale/incomplete catalogue")
        except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
            if db is not None:
                db.close()
                db = None
            rebuild(api, store, store.snapshot(), observed)
            db = connect(path)
        yield Catalogue(api, store, db, observed)
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError) as exc:
        raise api.MettleError(f"Invalid derived catalogue; run reindex --repair: {exc}") from exc
    finally:
        if db is not None:
            db.close()


class Catalogue:
    def __init__(self, api, store, db, observed):
        self.api, self.store, self.db, self.observed = api, store, db, observed
        self.loaded, self.histories = {}, {}

    def path(self, row):
        path = self.api.safe_path(self.store.root, row["path"])
        self.api.require(row["path"] in self.observed, "Catalogue path is not canonical; run reindex --repair")
        return path

    def row(self, identifier, revision=None):
        rows = self.db.execute("SELECT * FROM records WHERE id=? " +
                               ("ORDER BY revision DESC LIMIT 1" if revision is None else "AND revision=?"),
                               (identifier,) if revision is None else (identifier, revision)).fetchall()
        self.api.require(bool(rows), f"Unknown record or revision: {identifier}" + (f"@{revision}" if revision is not None else ""))
        return rows[0]

    def read_row(self, row):
        key = row["id"], row["revision"]
        if key in self.loaded:
            return self.loaded[key]
        api = self.api
        path = self.path(row)
        meta, body = api.decode(api.read(path))
        api.validate_record(meta, body)
        api.require(meta["id"] == row["id"] and meta["kind"] == row["kind"], f"Canonical identity changed: {path}; run reindex --repair")
        if meta["kind"] == "lesson":
            expected = self.store.path(f"memory/lessons/{meta['domain']}/{meta['id']}/revisions/{meta['revision']:04d}.md")
            api.require(meta["revision"] == row["revision"] and path.as_posix() == expected.as_posix(), f"Revision location does not match metadata: {path}")
        else:
            base = self.store.path("memory/" + api.DIRECTORIES[meta["kind"]])
            api.require(row["revision"] == 0 and path.is_relative_to(base) and path.stem == meta["id"], f"Record location does not match metadata: {path}")
        api.require(api.digest(api.encode(meta, body)) == row["source_hash"] and meta == json.loads(row["metadata"]),
                    f"Canonical content disagrees with catalogue: {path}; run reindex --repair")
        if meta["kind"] in {"episode", "lesson"}:
            api.require(fingerprint(json.loads(row["lexical"])) == fingerprint(lexical(api, meta, body)),
                        f"Canonical lexical features disagree with catalogue: {path}; run reindex --repair")
        result = meta, body, path
        self.loaded[key] = result
        return result

    def history(self, identifier):
        if identifier not in self.histories:
            rows = self.db.execute("SELECT * FROM records WHERE id=? ORDER BY revision", (identifier,)).fetchall()
            self.api.require(bool(rows) and all(r["kind"] == "lesson" for r in rows), f"Unknown lesson: {identifier}")
            versions = [self.read_row(row) for row in rows]
            self.api.require([v[0]["revision"] for v in versions] == list(range(1, len(versions) + 1)), f"Non-contiguous revisions: {identifier}")
            # Inventory must agree with the whole local sequence, not only a cached head.
            folder = versions[-1][2].parent
            actual = {p.name for p in folder.iterdir() if p.suffix.casefold() == ".md"}
            self.api.require(actual == {v[2].name for v in versions}, f"Lesson revisions changed: {identifier}; run reindex --repair")
            for old, new in zip(versions, versions[1:]):
                self.store.validate_transition(old[0], new[0])
            self.histories[identifier] = versions
        return self.histories[identifier]

    def validate_references(self, meta):
        record_ids, lesson_ids = set(), set()
        kind = meta["kind"]
        if kind == "lesson":
            for key in ("origin", "support", "counterevidence", "reconciliations"):
                record_ids.update(meta[key])
            lesson_ids.update(meta["supersedes"] + meta["superseded_by"])
        elif kind == "review":
            record_ids.update(meta["episodes"])
            lesson_ids.add(meta["lesson"])
        elif kind == "reconciliation":
            record_ids.update(meta["evidence"])
            for ref in meta["inputs"]:
                match = re.fullmatch(r"(L-[A-Za-z0-9_-]+)@([1-9][0-9]*)", ref)
                self.api.require(match is not None, f"Expected ID@revision: {ref}")
                lesson_ids.add(match[1])
        else:
            record_ids.update(meta["corrects"])
        records = {key: self.read_row(self.row(key, 0)) for key in record_ids}
        lessons = {key: self.history(key) for key in lesson_ids}
        self.store.validate_links(meta, records, lessons)

    def get(self, identifier, revision=None):
        self.api.require(isinstance(identifier, str) and bool(self.api.ID_PATTERN.fullmatch(identifier)), "Invalid record ID")
        row = self.row(identifier, revision)
        if row["kind"] == "lesson":
            versions = self.history(identifier)
            for meta, _, _ in versions:
                self.validate_references(meta)
            result = versions[row["revision"] - 1]
            if row["revision"] == len(versions):
                current = result[2].parent.parent / "current.md"
                self.api.require(current.is_file() and self.api.read(current) == self.api.encode(*result[:2]),
                                 f"Stale current view: {identifier}; run reindex --repair")
            return result
        self.api.require(revision is None, "Inapplicable revision for non-lesson record")
        result = self.read_row(row)
        self.validate_references(result[0])
        return result

    def sources(self, kind, history=False, *, features=True):
        if kind == "episodes":
            sql = "SELECT * FROM records WHERE kind='episode' ORDER BY ordinal"
        elif history:
            sql = "SELECT * FROM records WHERE kind='lesson' ORDER BY id, revision"
        else:
            sql = "SELECT r.* FROM records r WHERE kind='lesson' AND revision=(SELECT MAX(revision) FROM records WHERE id=r.id) ORDER BY ordinal"
        if not features:
            sql = sql.replace("SELECT r.*", "SELECT r.metadata, r.path").replace("SELECT *", "SELECT metadata, path")
        for row in self.db.execute(sql):
            # Inventory already walked this exact path through normal protections.
            # Avoid repeating every parent lstat for all unselected lexical rows;
            # read_row checks the selected path again immediately before opening.
            self.api.require(row["path"] in self.observed, "Catalogue path is not canonical; run reindex --repair")
            path = self.store.root / row["path"]
            yield json.loads(row["metadata"]), json.loads(row["lexical"]) if features else {}, path

    def relationships(self, selected, kind):
        relation = "counterexample" if kind == "lessons" else "corrects"
        identifiers = {item["id"] for item in selected}
        rows = {}
        for identifier in identifiers:
            for row in self.db.execute("SELECT r.* FROM links l JOIN records r ON r.id=l.source AND r.revision=0 WHERE l.target=? AND l.relation=?", (identifier, relation)):
                rows[row["ordinal"]] = row
        return {row["id"]: self.get(row["id"]) for _, row in sorted(rows.items())}

    def navigation(self, domain, offset, limit):
        lessons = {meta["id"]: [(meta, "", path)] for meta, _, path in self.sources("lessons", features=False)}
        page = self.store.navigation(lessons, domain, offset, limit)
        for item in page["items"]:
            if domain is not None:
                self.get(item["id"])
            else:
                representative = next(key for key, v in lessons.items() if v[-1][0]["domain"] == item["domain"])
                self.get(representative)
        return page
