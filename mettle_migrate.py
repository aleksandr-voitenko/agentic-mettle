"""Conservative, preview-first relocation of legacy working files.

No accepted records are edited, no draft is promoted, no archived code is run.
Run with all agents/writers stopped. Backups, a journal and exact-byte checks
support interruption recovery. This is not a hostile-process-safe transaction.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

import mettle_work as work

STABLE = {"PERSONALITY.md", "LOCATION.md", "REFERENCE.md", "WORK_REFERENCE.md", ".gitignore"}
JOURNAL_ID = re.compile(r"M-[0-9a-f]{16}\Z")
MAX_SCAN = 64_000_000
MAX_FILE = 16_000_000


def fingerprint(value) -> str:
    return work.sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def tree_files(api, base: Path) -> list[Path]:
    import os
    result = []
    if not base.exists():
        return result
    api.reject_redirect(base)
    def failed(exc):
        raise exc
    for directory, dirs, files in os.walk(base, followlinks=False, onerror=failed):
        for name in dirs + files:
            path = Path(directory) / name
            api.reject_redirect(path)
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]
        for name in files:
            path = Path(directory) / name
            api.require(path.is_file(), f"Not a regular file: {path}")
            result.append(path)
    return sorted(result)


def read_bytes(api, path: Path) -> bytes:
    api.reject_redirect_parents(path)
    api.require(path.is_file() and path.stat().st_size <= MAX_FILE, f"Migration input missing, redirected, or larger than {MAX_FILE} bytes: {path}")
    return path.read_bytes()


def protected(api, store) -> dict:
    # Do not hash mutable sessions, generated indexes or installer files as
    # historical learning. Accepted data and current profiles must not change.
    records, lessons = store.snapshot()
    paths = [r[2] for r in records.values()] + [r[2] for v in lessons.values() for r in v]
    paths += tree_files(api, store.path("personality"))
    paths += tree_files(api, store.path("memory/evidence"))
    return {p.relative_to(store.root).as_posix(): work.sha(read_bytes(api, p)) for p in paths}


def pending_journals(api, store) -> list[str]:
    result = []
    for path in store.files("migrations", "manifest.json"):
        info = json.loads(api.read(path))
        if info.get("status") in {"applying", "restoring"}:
            result.append(path.parent.name)
    return result


def accepted_match(api, data: bytes, known: dict) -> str | None:
    try:
        meta, body = api.decode(data.decode("utf-8-sig"))
        ref = work.reference(meta)
        entry = known.get(ref)
        if entry and api.encode(meta, body) == api.encode(*entry[:2]):
            return ref
    except (ValueError, KeyError, TypeError, api.MettleError):
        pass
    return None


def record_shaped(api, data: bytes) -> bool:
    try:
        meta, _ = api.decode(data.decode("utf-8-sig"))
        return meta.get("kind") in api.KINDS and isinstance(meta.get("id"), str) and bool(api.ID_PATTERN.fullmatch(meta["id"]))
    except (ValueError, TypeError, api.MettleError):
        return False


def plan(api, store) -> dict:
    api.require(not store.path(".write-lock").exists(), "Stop active writers before migration preview")
    return plan_unlocked(api, store)


def plan_unlocked(api, store) -> dict:
    api.require(not pending_journals(api, store), "An incomplete migration exists; use --resume ID before planning another")
    history = protected(api, store)
    known = work.accepted(api, store)
    candidates, kept, inputs = [], [], {}
    # Only positively recognized legacy locations, never the source repository.
    entries = list(store.home.iterdir())
    for folder in ("drafts", "tools"):
        entries += tree_files(api, api.safe_path(store.root, api.PACKAGE + "/" + folder))
    for path in sorted(set(entries)):
        api.reject_redirect(path)
        if path.is_dir():
            continue
        rel = path.relative_to(store.home).as_posix()
        if rel in STABLE:
            continue
        data = read_bytes(api, path)
        backup = bool(re.fullmatch(r"(?:tools/)?(?:mettle(?:_installer|_work|_migrate)?\.py|PERSONALITY\.md|LOCATION\.md|REFERENCE\.md|WORK_REFERENCE\.md|\.gitignore)\.mettle-backup-[0-9a-f]{8}", rel))
        if backup:
            category = "backup"
        elif rel.startswith("tools/"):
            continue
        elif rel.startswith("drafts/") or record_shaped(api, data) or re.search(r"(?:^|[-_])draft(?:\.|[-_])", path.name, re.I):
            category = "draft"
        elif path.suffix.lower() in {".log", ".txt"}:
            category = "artifact"
        else:
            kept.append({"source": rel, "reason": "Unknown file; no automatic ownership assumption"})
            continue
        api.portable_parts(rel)
        inputs[rel] = work.sha(data)
        candidates.append({"source": rel, "category": category, "sha256": work.sha(data), "bytes": len(data),
                           "accepted_record": accepted_match(api, data, known)})
    api.require(sum(c["bytes"] for c in candidates) <= MAX_SCAN, "Legacy input exceeds the migration size limit; split it manually")
    # Scan the available private state for references. Keep referenced targets in
    # place; never rewrite immutable history to repair links. Unknown external
    # references cannot be ruled out, so mappings/backups remain essential.
    texts = []
    scan_bytes = 0
    guards = dict(history)
    for path in tree_files(api, store.home):
        rel = path.relative_to(store.home).as_posix()
        if rel.startswith(("state/migrations/", "state/backups/", "state/.write-lock/", "tools/")) or rel in STABLE:
            continue
        if path.suffix.lower() not in {".md", ".json", ".txt", ".log"}:
            continue
        data = read_bytes(api, path)
        scan_bytes += len(data)
        api.require(scan_bytes <= MAX_SCAN, "Reference scan exceeds 64 MB; inspect legacy references manually")
        guards[path.relative_to(store.root).as_posix()] = work.sha(data)
        try:
            text = data.decode("utf-8-sig").replace("\\", "/")
        except UnicodeDecodeError:
            # An unreadable possible reference file is not silently ignored.
            api.require(False, f"Cannot check references in non-UTF-8 file: {rel}")
        texts.append((rel, text))
    moves = []
    # Be conservative even on POSIX: the archive may have been authored on a
    # case-insensitive Windows checkout. Preserve original spelling and bytes.
    for entry in candidates:
        name = Path(entry["source"]).name
        refs = [rel for rel, text in texts if rel != entry["source"]
                and re.search(r"(?<![\w.-])" + re.escape(name.casefold()) + r"(?![\w.-])", text.casefold())]
        if refs:
            kept.append({**entry, "reason": "Referenced in available state; preserve original path", "references": refs})
        else:
            moves.append(entry)
    seed = {"schema": 1, "root": str(store.root), "moves": moves, "kept": kept, "guards": guards, "inputs": inputs,
            "protected": history, "protocol_sha256": api.digest(api.read(store.home / "PERSONALITY.md")), "version": api.VERSION}
    token = fingerprint(seed)
    identifier = "M-" + token[:16]
    workspace = "W-legacy-" + token[:16]
    for entry in moves:
        prefix = "state/backups/legacy-" + token[:16] if entry["category"] == "backup" else "state/work/" + workspace + ("/drafts" if entry["category"] == "draft" else "/artifacts")
        entry["destination"] = prefix + "/" + entry["source"]
        destination = api.safe_path(store.root, api.PACKAGE + "/" + entry["destination"])
        api.require(not destination.exists(), f"Migration destination already exists: {destination}")
    result = {**seed, "id": identifier, "work_id": workspace, "plan_id": token,
            "warnings": ["Stop all agents/writers and keep a full pre-upgrade archive before applying.",
                         "Only available .agent-personality text is checked for references; external references are unknown.",
                         "Referenced/unknown files stay in place. No accepted memory or Git index is rewritten.",
                         "Relocation copies exact bytes to backup and destination before unlinking the old file; no history is deleted."]}
    if moves:
        journal_capacity(api, new_journal(api, result))
    return result


def journal_path(api, store, identifier: str) -> Path:
    api.require(bool(JOURNAL_ID.fullmatch(identifier)), "Invalid migration ID")
    return store.path("migrations/" + identifier + "/manifest.json")


def journal_text(journal: dict, *, compact: bool = False) -> str:
    return json.dumps(journal, ensure_ascii=False, indent=None if compact else 2,
                      separators=(",", ":") if compact else None) + "\n"


def new_journal(api, plan: dict) -> dict:
    return {"schema": 1, "id": plan["id"], "status": "applying", "started_at": api.now(),
            "plan": plan, "plan_sha256": fingerprint(plan), "completed": []}


def journal_capacity(api, journal: dict) -> int:
    # Reserve every future completion plus the finishing timestamp BEFORE moving
    # any file. The longest terminal/transitional statuses have nine characters.
    full = {**journal, "status": "completed", "completed": [e["source"] for e in journal["plan"]["moves"]],
            "finished_at": journal.get("finished_at", "9999-12-31T23:59:59+00:00")}
    size = len(journal_text(full).encode("utf-8"))
    api.require(size <= api.MAX_RECORD,
                f"Completed migration manifest would need {size} bytes (limit {api.MAX_RECORD}); no further files moved. "
                "Review/split the migration input manually. For an interrupted older migration, use --restore ID to preview recovery without completing it.")
    return size


def put_journal(api, path: Path, journal: dict, *, compact: bool = False) -> None:
    # The plan is never recomputed from a partially migrated tree. Compact JSON
    # gives old near-full journals a recovery path without dropping any history.
    text = journal_text(journal, compact=compact)
    api.require(len(text.encode("utf-8")) <= api.MAX_RECORD, "Migration manifest exceeds the supported size; inspect/split manually")
    api.write_atomic(path, text)


def load_journal(api, store, identifier: str) -> tuple[Path, dict]:
    path = journal_path(api, store, identifier)
    journal = json.loads(api.read(path))
    api.require(journal.get("schema") == 1 and journal.get("id") == identifier and isinstance(journal.get("plan"), dict), "Malformed migration journal")
    p = journal["plan"]
    api.require(p.get("id") == identifier and p.get("root") == str(store.root), "Journal belongs to a different root; relocate/review manually")
    api.require(isinstance(p.get("moves"), list) and isinstance(journal.get("completed"), list), "Missing migration entries")
    api.require(p.get("work_id") == "W-legacy-" + identifier[2:], "Invalid migration workspace")
    for entry in p["moves"]:
        # Never accept arbitrary archive/destination paths from an edited journal.
        src = api.portable_parts(entry["source"])
        dst = api.portable_parts(entry["destination"])
        api.require(src[0] not in {"state", ".git"} and entry["source"] not in STABLE
                    and (len(src) == 1 or src[0] in {"drafts", "tools"}), "Unsafe original path in migration journal")
        api.require(entry["category"] in {"draft", "artifact", "backup"}, "Unknown migration category")
        if src[0] == "tools":
            api.require(entry["category"] == "backup" and re.search(r"\.mettle-backup-[0-9a-f]{8}$", entry["source"]), "Only known tool backups may move")
        prefix = "state/backups/legacy-" + identifier[2:] if entry["category"] == "backup" else "state/work/" + p["work_id"] + ("/drafts" if entry["category"] == "draft" else "/artifacts")
        api.require(entry["destination"] == prefix + "/" + entry["source"], "Migration destination does not match its original plan layout")
        api.require(dst[:2] in {("state", "work"), ("state", "backups")}, "Unsafe destination in migration journal")
        api.require(re.fullmatch(r"[0-9a-f]{64}", entry["sha256"] or ""), "Invalid migration digest")
    sources = [e["source"] for e in p["moves"]]
    api.require(len(set(sources)) == len(sources) and all(isinstance(x, str) and x in sources for x in journal["completed"])
                and len(set(journal["completed"])) == len(journal["completed"]), "Invalid migration completion entries")
    # Detect accidental journal editing. This is integrity, not authentication.
    api.require(journal.get("plan_sha256") == fingerprint(p), "Migration plan was edited; inspect backups instead of guessing")
    return path, journal


def exact_copy(api, source: Path, destination: Path, expected: str) -> None:
    data = read_bytes(api, source)
    api.require(work.sha(data) == expected, f"File changed: {source}")
    if destination.exists():
        api.require(read_bytes(api, destination) == data, f"Destination conflict: {destination}")
    else:
        api.write_atomic(destination, data, exclusive=True)
    api.require(work.sha(read_bytes(api, destination)) == expected, f"Destination verification failed: {destination}")


def resume(api, store, identifier: str) -> dict:
    path, journal = load_journal(api, store, identifier)
    api.require(journal["status"] in {"applying", "completed"}, "Migration is restoring/restored; do not resume moves")
    if journal["status"] == "completed":
        return {"id": identifier, "status": "completed", "moved": len(journal["completed"])}
    journal_capacity(api, journal)  # Older interrupted plans must also fit before further relocation.
    p = journal["plan"]
    api.require(protected(api, store) == p["protected"], "Accepted history/profile/evidence changed during migration; inspect before resuming")
    # Preflight every remaining original, backup, and destination before moves.
    for entry in p["moves"]:
        source = api.safe_path(store.root, api.PACKAGE + "/" + entry["source"])
        dest = api.safe_path(store.root, api.PACKAGE + "/" + entry["destination"])
        backup = store.path(f"migrations/{identifier}/originals/" + entry["source"])
        for existing in (source, dest, backup):
            if existing.exists():
                api.require(work.sha(read_bytes(api, existing)) == entry["sha256"], f"File differs from migration plan: {existing}")
        api.require(source.exists() or (dest.exists() and backup.exists()), f"Missing migration source and recovery copies: {source}")
    if any(e["category"] != "backup" for e in p["moves"]):
        folder = work.work_path(api, store, p["work_id"])
        if folder.exists() and not (folder / "WORK.md").exists():
            api.require(not any(folder.iterdir()), "Partially initialized legacy workspace contains unknown files; inspect it")
            folder.rmdir()  # Only an empty directory left by an interrupted first write.
        if not folder.exists():
            work.start(api, store, "Legacy work import (activity attribution unknown)",
                       "Imported working files only. Inspect prior context before resuming or closing.", identifier=p["work_id"])
        else:
            work.read_work(api, store, p["work_id"])
    for entry in p["moves"]:
        source = api.safe_path(store.root, api.PACKAGE + "/" + entry["source"])
        dest = api.safe_path(store.root, api.PACKAGE + "/" + entry["destination"])
        backup = store.path(f"migrations/{identifier}/originals/" + entry["source"])
        if source.exists():
            exact_copy(api, source, backup, entry["sha256"])
            exact_copy(api, backup, dest, entry["sha256"])
            api.require(work.sha(read_bytes(api, source)) == entry["sha256"], f"Source changed before relocation: {source}")
            source.unlink()
        if entry["source"] not in journal["completed"]:
            journal["completed"].append(entry["source"])
            put_journal(api, path, journal)
    if any(e["category"] != "backup" for e in p["moves"]):
        wm, body = work.read_work(api, store, p["work_id"])
        known = work.accepted(api, store)
        for e in p["moves"]:
            if e["category"] == "draft" and e["accepted_record"]:
                item = known[e["accepted_record"]]
                dest = api.safe_path(store.root, api.PACKAGE + "/" + e["destination"])
                publication = {"draft": dest.relative_to(work.work_path(api, store, p["work_id"])).as_posix(),
                               "draft_sha256": e["sha256"], "record": e["accepted_record"],
                               "path": item[2].relative_to(store.root).as_posix(), "accepted_sha256": work.sha(item[2].read_bytes())}
                if publication not in wm["publications"]:
                    wm["publications"].append(publication)
        wm["status"] = "paused"
        wm["next_action"] = "Review imported material, unpublished differences, and retained legacy references; do not infer task ownership."
        wm["migration"] = identifier
        work.save_work(api, store, wm, body)
    api.require(protected(api, store) == p["protected"], "Protected data changed; migration journal retained for inspection")
    journal["status"] = "completed"
    journal["finished_at"] = api.now()
    put_journal(api, path, journal)
    return {"id": identifier, "status": "completed", "moved": len(p["moves"]), "kept": p["kept"],
            "manifest": path.relative_to(store.root).as_posix(), "work_id": p["work_id"],
            "history_unchanged": True, "note": "Original bytes remain in the migration backup. No files were deduplicated or auto-published."}


def apply(api, store, expected: str) -> dict:
    with store.lock():
        p = plan_unlocked(api, store)
        api.require(expected == p["plan_id"], "Migration inputs changed; review a new plan before applying")
        if not p["moves"]:
            return {"status": "nothing-to-move", "kept": p["kept"]}
        path = journal_path(api, store, p["id"])
        api.require(not path.parent.exists(), "Migration journal already exists; inspect or resume it")
        journal = new_journal(api, p)
        journal_capacity(api, journal)
        text = journal_text(journal)
        api.write_atomic(path, text, exclusive=True)
        return resume(api, store, p["id"])


def restore(api, store, identifier: str, perform: bool) -> dict:
    path, journal = load_journal(api, store, identifier)
    api.require(journal["status"] in {"applying", "completed", "restoring", "restored"}, "Unknown migration status")
    entries, missing = journal["plan"]["moves"], []
    # Recovery is independent of relocation completion. Unmoved originals may
    # have no backup yet; a missing original ALWAYS requires its verified backup.
    for entry in entries:
        source = api.safe_path(store.root, api.PACKAGE + "/" + entry["source"])
        backup = store.path(f"migrations/{identifier}/originals/" + entry["source"])
        if backup.exists():
            api.require(work.sha(read_bytes(api, backup)) == entry["sha256"], f"Backup changed: {backup}")
        if source.exists():
            api.require(work.sha(read_bytes(api, source)) == entry["sha256"], f"Original path now has different content: {source}")
        else:
            api.require(backup.is_file(), f"Missing original and verified backup: {source}")
            missing.append(entry["source"])
    recovering = {**journal, "status": "restoring"}
    api.require(len(journal_text(recovering, compact=True).encode("utf-8")) <= api.MAX_RECORD,
                "Recovery manifest exceeds capacity; preserve all copies for manual recovery")
    if not perform:
        return {"id": identifier, "restore": [e["source"] for e in entries], "copies_needed": missing, "writes": False,
                "note": "Restores verified original paths even after partial migration; retains migrated copies and newer work."}
    put_journal(api, path, recovering, compact=True)
    copied = 0
    for entry in entries:
        source = api.safe_path(store.root, api.PACKAGE + "/" + entry["source"])
        if source.exists():
            api.require(work.sha(read_bytes(api, source)) == entry["sha256"], f"Original path changed while restoring: {source}")
        else:
            exact_copy(api, store.path(f"migrations/{identifier}/originals/" + entry["source"]), source, entry["sha256"])
            copied += 1
    recovering["status"] = "restored"
    put_journal(api, path, recovering, compact=True)
    return {"id": identifier, "status": "restored", "restored": len(entries), "copied": copied,
            "migrated_copies_retained": True}


def add_parser(sub) -> None:
    p = sub.add_parser("migrate-work", help="Preview legacy relocation; applying requires the exact reviewed plan")
    p.add_argument("--root")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--expect", help="plan_id from the immediately preceding preview")
    action = p.add_mutually_exclusive_group()
    action.add_argument("--resume", metavar="M-ID")
    action.add_argument("--restore", metavar="M-ID")


def run(api, store, args) -> dict:
    api.require(not args.expect or args.apply, "--expect requires --apply")
    if args.restore:
        api.require(not args.expect, "Restore uses verified journal backups, not --expect")
        if args.apply:
            with store.lock():
                return restore(api, store, args.restore, True)
        return restore(api, store, args.restore, False)
    if args.resume:
        api.require(args.apply and not args.expect, "Resuming requires --apply and uses the original journal plan")
        with store.lock():
            return resume(api, store, args.resume)
    if args.apply:
        api.require(args.expect, "Preview first, then provide --apply --expect <plan_id>")
        return apply(api, store, args.expect)
    p = plan(api, store)
    return {key: p[key] for key in ("id", "work_id", "plan_id", "moves", "kept", "warnings")} | {"protected_files": len(p["protected"]), "writes": False}
