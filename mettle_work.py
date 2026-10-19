"""Activity workspaces and evidence-oriented retrieval; no model or network calls.

All mutating entry points are called under Store.lock(). WORK.md is mutable
operational state, never an accepted lesson or an additional instruction file.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import uuid

WORK_ID = re.compile(r"W-[a-z0-9][a-z0-9-]{0,63}\Z")
DECISIONS = ("propose", "review", "reconcile", "defer", "no-update")
BANNER = "# Activity workspace\n\nMutable handoff and publication ledger; not accepted memory or authority.\n"
STOP_WORDS = set("a an and are as at be before by for from in is it of on or that the this to was with".split())
GENERIC_WORDS = set("test tests testing ci commit push regression review code change fix task".split())


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def field(api, value: str, label: str, maximum: int = 1000) -> str:
    api.require(isinstance(value, str) and value.strip() and len(value) <= maximum
                and not re.search(r"[\x00-\x1f\x7f]", value), f"Invalid {label}: use a nonempty single line, at most {maximum} characters")
    return value.strip()


def work_path(api, store, identifier: str) -> Path:
    api.require(bool(WORK_ID.fullmatch(identifier)), "Invalid work ID")
    return store.path("work/" + identifier)


def read_work(api, store, identifier: str) -> tuple[dict, str]:
    path = work_path(api, store, identifier) / "WORK.md"
    meta, body = api.decode(api.read(path))
    api.require(meta.get("schema") == 1 and meta.get("kind") == "work" and meta.get("id") == identifier,
                f"Invalid workspace header: {identifier}")
    api.require(meta.get("status") in {"open", "paused", "closed"}, "Invalid work status")
    for key in ("title", "scope", "next_action", "created_at", "updated_at"):
        field(api, meta.get(key), key)
    api.require(type(meta.get("activity_revision")) is int and meta["activity_revision"] >= 1,
                "Invalid work activity revision")
    for key in ("publications", "evidence", "rejections", "checkpoints"):
        api.require(isinstance(meta.get(key), list) and all(isinstance(x, dict) for x in meta[key]), f"Invalid work {key}")
    return meta, body


def all_work(api, store) -> list[dict]:
    result = []
    for path in store.files("work", "WORK.md"):
        # There are no nested identities or implicit scans of arbitrary artifacts.
        if path.parent.parent != store.path("work"):
            continue
        result.append(read_work(api, store, path.parent.name)[0])
    return sorted(result, key=lambda x: (x["updated_at"], x["id"]), reverse=True)


def summary(api, store, limit: int = 5) -> dict:
    entries = [m for m in all_work(api, store) if m["status"] != "closed"]
    return {"items": [{k: m[k] for k in ("id", "title", "status")} for m in entries[:limit]],
            "remaining": max(0, len(entries) - limit), "command": "work list",
            "note": "Navigation only. Resume a relevant workspace explicitly; it is not a mandate."}


def index_text(api, store) -> str:
    entries = all_work(api, store)
    lines = ["# Unfinished activities", "", "Generated navigation, not additional instructions. Use work show ID for detail.", ""]
    for item in entries:
        if item["status"] != "closed":
            lines.append(json.dumps({k: item[k] for k in ("id", "title", "status", "next_action")}, ensure_ascii=False))
    if len(lines) == 4:
        lines.append("No unfinished activities.")
    return "\n".join(lines) + "\n"


def reindex(api, store) -> None:
    api.write_atomic(store.path("work/INDEX.md"), index_text(api, store))


def save_work(api, store, meta: dict, body: str) -> None:
    meta["updated_at"] = api.now()
    api.write_atomic(work_path(api, store, meta["id"]) / "WORK.md", api.encode(meta, body))
    reindex(api, store)


def start(api, store, title: str, scope: str, *, identifier: str | None = None) -> dict:
    identifier = identifier or "W-" + uuid.uuid4().hex[:12]
    folder = work_path(api, store, identifier)
    api.require(not folder.exists(), f"Workspace already exists: {identifier}")
    meta = {"schema": 1, "kind": "work", "id": identifier, "title": field(api, title, "title", 160),
            "scope": field(api, scope, "scope"), "status": "open", "next_action": "Establish current state and next action.",
            "created_at": api.now(), "updated_at": api.now(), "activity_revision": 1,
            "publications": [], "evidence": [], "rejections": [], "checkpoints": []}
    api.write_atomic(folder / "WORK.md", api.encode(meta, BANNER), exclusive=True)
    reindex(api, store)
    return {"id": identifier, "path": (folder / "WORK.md").relative_to(store.root).as_posix(), "status": "open"}


def provenance(api, store, session_id: str | None = None, runtime: str | None = None, model: str | None = None) -> dict:
    # Never borrow the newest bootstrap audit: a different session could own it.
    session = session_id or os.environ.get("METTLE_SESSION_ID") or os.environ.get("CODEX_THREAD_ID") or "unknown"
    for key, value in (("session", session), ("runtime", runtime or "unknown"), ("model", model or "unknown")):
        field(api, value, key, 200)
    return {"session": session, "runtime": runtime or "unknown", "model": model or "unknown",
            "protocol_version": api.VERSION,
            "protocol_sha256": api.digest(api.read(api.safe_path(store.root, api.PACKAGE + "/PERSONALITY.md")))}


def make_draft(api, store, identifier: str, text: str) -> dict:
    work, body = read_work(api, store, identifier)
    api.require(work["status"] != "closed", "Resume the workspace before creating drafts")
    meta, _ = api.decode(text)
    api.require(isinstance(meta.get("id"), str) and bool(api.ID_PATTERN.fullmatch(meta["id"])), "Invalid draft ID")
    suffix = f"-r{meta['revision']}" if meta.get("kind") == "lesson" else ""
    path = work_path(api, store, identifier) / "drafts" / f"{meta['id']}{suffix}.md"
    api.write_atomic(path, text, exclusive=True)
    work["activity_revision"] += 1
    save_work(api, store, work, body)
    return {"work": identifier, "draft": path.relative_to(store.root).as_posix(), "id": meta["id"]}


def draft_target(api, path: Path) -> None:
    """Protect installed/stable files even for callers using legacy --output."""
    path = path.expanduser().absolute()
    for parent in path.parents:
        if parent.name == api.PACKAGE:
            parts = path.relative_to(parent).parts
            api.require(len(parts) >= 5 and parts[:2] == ("state", "work")
                        and bool(WORK_ID.fullmatch(parts[2])) and parts[3] == "drafts",
                        "Put managed drafts in state/work/<work-id>/drafts; prefer --work ID")
            break


def owner(api, store, path: Path) -> str | None:
    path = path.absolute()
    try:
        relative = path.relative_to(store.path("work"))
    except ValueError:
        return None
    parts = relative.parts
    api.require(len(parts) >= 3 and parts[1] == "drafts", "Publish workspace records from drafts/, not artifacts or WORK.md")
    work_path(api, store, parts[0])
    api.safe_path(store.root, path.relative_to(store.root).as_posix())
    return parts[0]


def accepted(api, store) -> dict[str, tuple[dict, str, Path]]:
    records, lessons = store.snapshot()
    return {**records, **{f"{key}@{m['revision']}": (m, b, p) for key, versions in lessons.items() for m, b, p in versions}}


def reference(meta: dict) -> str:
    return f"{meta['id']}@{meta['revision']}" if meta["kind"] == "lesson" else meta["id"]


def publish(api, store, path: Path, expected: int | None) -> str:
    identifier = owner(api, store, path)
    if identifier is None:
        return store.publish(api.read(path), expected)
    work, body = read_work(api, store, identifier)
    api.require(work["status"] != "closed", "Resume the workspace before publishing")
    text = api.read(path)
    meta, record_body = api.decode(text)
    api.validate_record(meta, record_body)
    if meta["kind"] == "lesson":
        api.require(expected == meta["revision"] - 1, "Provide the draft's expected prior lesson revision")
    ref = reference(meta)
    record = accepted(api, store).get(ref)
    canonical = api.encode(meta, record_body)
    if record:
        # Retry only repairs bookkeeping for this exact workspace draft. A same-ID
        # record with different content is a conflict, never an overwrite.
        api.require(api.encode(*record[:2]) == canonical, "Published ID has different content; inspect the history")
        destination = record[2].relative_to(store.root).as_posix()
    else:
        destination = store.publish(text, expected)
    entry = {"draft": path.relative_to(work_path(api, store, identifier)).as_posix(),
             "draft_sha256": sha(path.read_bytes()), "record": ref, "path": destination,
             "accepted_sha256": sha((store.root / destination).read_bytes())}
    if entry not in work["publications"]:
        work["publications"].append(entry)
        work["activity_revision"] += 1
        # If this write fails, rerunning publish of the same unchanged draft
        # recovers this ledger using the already accepted record above.
        save_work(api, store, work, body)
    return destination


def evidence(api, store, identifier: str, path: Path) -> dict:
    work, body = read_work(api, store, identifier)
    api.require(work["status"] != "closed", "Resume the workspace before preserving evidence")
    path = path.absolute()
    folder = work_path(api, store, identifier)
    api.require(path.is_relative_to(folder / "artifacts"), "Preserve evidence from this workspace's artifacts/ directory")
    api.safe_path(store.root, path.relative_to(store.root).as_posix())
    api.require(path.is_file() and path.stat().st_size <= 16_000_000, "Evidence must be a regular file no larger than 16 MB")
    data = path.read_bytes()
    digest = sha(data)
    api.portable_parts(path.name)
    dest = store.path("memory/evidence/" + digest + "/" + path.name)
    if dest.exists():
        api.require(dest.read_bytes() == data, "Existing evidence differs from its hash address")
    else:
        api.write_atomic(dest, data, exclusive=True)
    entry = {"source": path.relative_to(folder).as_posix(), "path": dest.relative_to(store.root).as_posix(), "sha256": digest}
    if entry not in work["evidence"]:
        work["evidence"].append(entry)
        work["activity_revision"] += 1
        save_work(api, store, work, body)
    return entry


def checkpoint(api, store, identifier: str, decision: str | None, reason: str | None,
               records: list[str], next_review: str | None, limit: int = 10) -> dict:
    work, body = read_work(api, store, identifier)
    known = accepted(api, store)
    api.require(1 <= limit <= 30, "limit must be 1..30")
    if decision is None:
        api.require(not reason and not records and not next_review, "Select --decision to record a checkpoint")
        refs = list(dict.fromkeys(p["record"] for p in work["publications"]))
        return {"work": identifier, "activity_revision": work["activity_revision"],
                "publications": [{"record": r, "title": known[r][0]["title"], "kind": known[r][0]["kind"],
                                  "path": known[r][2].relative_to(store.root).as_posix()} for r in refs[-limit:] if r in known],
                "omitted": max(0, len(refs) - limit), "decisions": DECISIONS,
                "questions": ["What reusable practice can be proposed within observed conditions?",
                              "Which existing lesson needs a review or reconciliation?",
                              "Are locally supported results being confused with universal or causal proof?",
                              "What remains uncertain, and when should it be revisited?"],
                "note": "Inspect full records and related memory. This packet is a prompt for agent-owned judgment, not an automatic conclusion."}
    api.require(work["status"] != "closed", "Resume closed work before changing its checkpoint")
    api.require(decision in DECISIONS, "Invalid checkpoint decision")
    reason = field(api, reason, "checkpoint reason", 2000)
    api.require(all(r in known for r in records), "Checkpoint references must identify accepted records; lessons use ID@revision")
    kinds = {known[r][0]["kind"] for r in records}
    needed = {"propose": "lesson", "review": "review", "reconcile": "reconciliation"}.get(decision)
    api.require(not needed or needed in kinds, f"{decision} requires a published {needed}; otherwise defer")
    if decision == "reconcile":
        cs = {r for r in records if known[r][0]["kind"] == "reconciliation"}
        api.require(any(known[r][0]["kind"] == "lesson" and cs.intersection(known[r][0]["reconciliations"])
                        for r in records), "Reconcile must also cite a published lesson revision linked to the reconciliation")
    if decision == "defer":
        next_review = field(api, next_review, "concrete revisit trigger")
    entry = {"activity_revision": work["activity_revision"], "decision": decision, "reason": reason,
             "records": records, "next_review": next_review, "at": api.now()}
    work["checkpoints"].append(entry)
    save_work(api, store, work, body)
    return entry


def update(api, store, identifier: str, status: str | None, next_action: str | None) -> dict:
    work, body = read_work(api, store, identifier)
    api.require(status is None or status in {"open", "paused", "closed"}, "Invalid work status")
    if status == "closed":
        api.require(work["checkpoints"] and work["checkpoints"][-1]["activity_revision"] == work["activity_revision"],
                    "Run a current learning checkpoint before closing; defer/no-update are valid")
        # Do not silently abandon a changed/unpublished draft.
        for path in store.files(f"work/{identifier}/drafts", "*"):
            rel = path.relative_to(work_path(api, store, identifier)).as_posix()
            api.require(any(p["draft"] == rel and p["draft_sha256"] == sha(path.read_bytes()) for p in work["publications"]),
                        f"Unpublished or changed draft remains: {rel}; publish it or pause the activity")
    if next_action:
        work["next_action"] = field(api, next_action, "next action")
    if status == "open" and work["status"] != "open":
        work["activity_revision"] += 1
    if status:
        work["status"] = status
    save_work(api, store, work, body)
    return {k: work[k] for k in ("id", "status", "next_action", "activity_revision")}


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[^\W_]+(?:[-_][^\W_]+)*", text.casefold(), re.UNICODE))


def retrieve(api, store, query: list[str], limit: int, scope: str | None, kind: str = "lessons", work_id: str | None = None) -> list[dict]:
    records, lessons = store.snapshot()
    api.require(kind in {"lessons", "episodes"} and 1 <= limit <= 50, "Invalid search kind or limit")
    original = set().union(*(tokens(value) for value in query)) - STOP_WORDS
    api.require(bool(original), "Use at least one nontrivial search term")
    terms = set(original)
    vocabulary, _ = api.decode(api.read(store.path("memory/vocabulary.md")))
    groups = vocabulary.get("groups")
    api.require(isinstance(groups, list) and all(isinstance(g, list) and all(isinstance(t, str) for t in g) for g in groups), "Invalid vocabulary groups")
    for group in groups:
        expanded = set().union(*(tokens(s) for s in group)) - STOP_WORDS
        if original & expanded:
            terms |= expanded
    source = [v[-1] for v in lessons.values()] if kind == "lessons" else [r for r in records.values() if r[0]["kind"] == "episode"]
    docs = []
    for meta, body, path in source:
        if kind == "lessons" and meta["status"] in {"retired", "superseded"}:
            continue
        scopes = meta.get("scope", [])
        if scope and not any(scope.casefold() in s.casefold() for s in scopes):
            # Episodes have no mandatory scope field; explicit body/title filter.
            if kind != "episodes" or scope.casefold() not in (meta["title"] + " " + body).casefold():
                continue
        header = tokens(" ".join([meta["id"], meta["title"], meta.get("domain", ""), *meta.get("tags", []), *meta.get("aliases", []), *scopes]))
        docs.append((meta, body, path, header, tokens(body)))
    frequency = {term: sum(term in d[3] or term in d[4] for d in docs) for term in terms}
    rejected = set()
    if work_id:
        work, _ = read_work(api, store, work_id)
        rejected = {(r.get("record"), r.get("query")) for r in work["rejections"] if r.get("activity_revision") == work["activity_revision"]}
    normalized_query = " ".join(sorted(original))
    results = []
    for meta, body, path, header, body_terms in docs:
        matches = terms & (header | body_terms)
        direct = original & (header | body_terms)
        if not matches or (original - GENERIC_WORDS and not (matches - GENERIC_WORDS)):
            continue  # Generic overlap alone cannot drag an unrelated lesson in.
        ref = reference(meta)
        if (ref, normalized_query) in rejected:
            continue
        score = sum((4 if term in header else 1) * (0.15 if term in GENERIC_WORDS else 1)
                    * (1 if term in original else 0.4)
                    * (1 + math.log((len(docs) + 1) / (1 + frequency[term])))
                    for term in matches)
        item = {"id": meta["id"], "kind": meta["kind"], "title": meta["title"], "matches": sorted(matches),
                "score": round(score, 4), "path": path.relative_to(store.root).as_posix()}
        if kind == "lessons":
            item.update(revision=meta["revision"], status=meta["status"], scope=scopes,
                        path=(path.parent.parent / "current.md").relative_to(store.root).as_posix(),
                        pending_counterevidence=[k for k, r in records.items() if r[0]["kind"] == "review"
                            and r[0]["lesson"] == meta["id"] and r[0]["assessment"] == "counterexample"
                            and k not in meta["counterevidence"]])
        else:
            item.update(status="observation-not-instruction", created_at=meta["created_at"],
                        session=meta["session"], corrects=meta["corrects"],
                        corrected_by=[k for k, r in records.items() if r[0]["kind"] == "episode" and meta["id"] in r[0]["corrects"]])
        results.append(item)
    return sorted(results, key=lambda r: (-r["score"], r["id"]))[:limit]


def reject_candidate(api, store, identifier: str, ref: str, query: list[str], reason: str) -> dict:
    work, body = read_work(api, store, identifier)
    api.require(work["status"] != "closed", "Resume workspace before recording a decision")
    api.require(ref in accepted(api, store), "Unknown accepted record/revision")
    normalized = " ".join(sorted(set().union(*(tokens(s) for s in query)) - STOP_WORDS))
    api.require(bool(normalized), "Supply the exact search terms being rejected")
    entry = {"record": ref, "query": normalized, "activity_revision": work["activity_revision"], "reason": field(api, reason, "rejection reason"), "at": api.now()}
    work["rejections"].append(entry)
    save_work(api, store, work, body)
    return entry


def validate(api, store) -> dict:
    entries = all_work(api, store)
    known = accepted(api, store)
    warnings = []
    for meta in entries:
        folder = work_path(api, store, meta["id"])
        for item in meta["publications"]:
            api.require(item.get("record") in known, "Workspace links an unknown accepted record")
            record_path = known[item["record"]][2]
            api.require(item.get("path") == record_path.relative_to(store.root).as_posix()
                        and item.get("accepted_sha256") == sha(record_path.read_bytes()),
                        "Workspace accepted-record path/hash changed; inspect its history")
            parts = api.portable_parts(item["draft"])
            api.require(parts[0] == "drafts", "Workspace publication source must be a draft")
            draft = api.safe_path(folder, item["draft"])
            if draft.exists() and sha(draft.read_bytes()) != item["draft_sha256"]:
                warnings.append({"work": meta["id"], "draft": item["draft"], "warning": "Working draft differs from its published copy"})
        for item in meta["evidence"]:
            expected_prefix = api.PACKAGE + "/state/memory/evidence/" + item["sha256"] + "/"
            api.require(item["path"].startswith(expected_prefix), "Invalid workspace evidence path")
            path = api.safe_path(store.root, item["path"])
            api.require(path.is_file() and sha(path.read_bytes()) == item["sha256"], "Preserved evidence is missing or changed")
    index = store.path("work/INDEX.md")
    if index.exists():
        api.require(api.read(index) == index_text(api, store), "Stale work index; run reindex")
    return {"workspaces": len(entries), "work_warnings": warnings}


def add_parser(sub) -> None:
    parser = sub.add_parser("work", help="Manage mutable activity workspaces; not accepted memory")
    parser.add_argument("--root")
    actions = parser.add_subparsers(dest="work_command", required=True)
    p = actions.add_parser("start")
    p.add_argument("--title", required=True)
    p.add_argument("--scope", required=True)
    actions.add_parser("list")
    p = actions.add_parser("show"); p.add_argument("id")
    p = actions.add_parser("update"); p.add_argument("id")
    p.add_argument("--status", choices=("open", "paused", "closed"))
    p.add_argument("--next-action")
    p = actions.add_parser("checkpoint"); p.add_argument("id")
    p.add_argument("--decision", choices=DECISIONS); p.add_argument("--reason")
    p.add_argument("--records", nargs="*", default=[]); p.add_argument("--next-review")
    p.add_argument("--limit", type=int, default=10)
    p = actions.add_parser("evidence"); p.add_argument("id"); p.add_argument("file", type=Path)
    p = actions.add_parser("reject"); p.add_argument("id"); p.add_argument("record")
    p.add_argument("--query", nargs="+", required=True); p.add_argument("--reason", required=True)


def run(api, store, args) -> dict:
    command = args.work_command
    if command == "start":
        return start(api, store, args.title, args.scope)
    if command == "list":
        return {"work": summary(api, store, 100)}
    if command == "show":
        meta, body = read_work(api, store, args.id)
        return {"work": meta, "notes": body}
    if command == "update":
        return update(api, store, args.id, args.status, args.next_action)
    if command == "checkpoint":
        return checkpoint(api, store, args.id, args.decision, args.reason, args.records, args.next_review, args.limit)
    if command == "evidence":
        return evidence(api, store, args.id, args.file)
    return reject_candidate(api, store, args.id, args.record, args.query, args.reason)
