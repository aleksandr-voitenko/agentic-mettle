"""Activity workspaces and evidence-oriented retrieval; no model or network calls.

All mutating entry points are called under Store.lock(). WORK.md is mutable
operational state, never an accepted lesson or an additional instruction file.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import uuid

WORK_ID = re.compile(r"W-[a-z0-9][a-z0-9-]{0,63}\Z")
LEDGER_KEYS = ("publications", "evidence", "rejections", "checkpoints", "draft_decisions")
PAGE_BYTES = 32_000
LEGACY_WORK_BYTES = 16_000_000
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
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


def validate_header(api, meta: dict, identifier: str) -> None:
    api.require(type(meta.get("schema")) is int and meta["schema"] in {1, 2}
                and meta.get("kind") == "work" and meta.get("id") == identifier,
                f"Invalid workspace header: {identifier}")
    api.require(meta.get("status") in {"open", "paused", "closed"}, "Invalid work status")
    for key in ("title", "scope", "next_action", "created_at", "updated_at"):
        field(api, meta.get(key), key)
    api.require(type(meta.get("activity_revision")) is int and meta["activity_revision"] >= 1,
                "Invalid work activity revision")
    if meta["schema"] == 2:
        heads = meta.get("ledgers")
        api.require(isinstance(heads, dict) and set(heads) == set(LEDGER_KEYS), "Invalid workspace ledgers")
        for key, entry in heads.items():
            api.require(isinstance(entry, dict) and type(entry.get("count")) is int and entry["count"] >= 0,
                        f"Invalid ledger count: {key}")
            head = entry.get("head")
            api.require((head is None and entry["count"] == 0) or
                        (isinstance(head, str) and bool(DIGEST.fullmatch(head)) and entry["count"] > 0),
                        f"Invalid ledger head: {key}")
    else:
        for key in LEDGER_KEYS:
            if key == "draft_decisions":
                meta.setdefault(key, [])  # Older workspaces have no abandonment decisions.
            api.require(isinstance(meta.get(key), list) and all(isinstance(x, dict) for x in meta[key]),
                        f"Invalid work {key}")


def read_ledger(api, store, identifier: str, key: str, descriptor: dict) -> list[dict]:
    pages, seen, count = [], set(), 0
    head = descriptor["head"]
    while head is not None:
        api.require(isinstance(head, str) and bool(DIGEST.fullmatch(head)) and head not in seen,
                    f"Invalid/cyclic work ledger: {identifier}/{key}")
        seen.add(head)
        path = api.safe_path(work_path(api, store, identifier), f"ledger/{head}.json")
        api.read(path)  # Validate path and per-file size before hashing original bytes.
        raw = path.read_bytes()
        api.require(sha(raw) == head, f"Work ledger hash mismatch: {path}")
        page = json.loads(raw)
        api.require(isinstance(page, dict) and page.get("schema") == 1 and page.get("work_id") == identifier
                    and page.get("ledger") == key, f"Invalid work ledger page: {path}")
        entries = page.get("entries")
        api.require(isinstance(entries, list) and bool(entries) and all(isinstance(x, dict) for x in entries),
                    f"Invalid work ledger entries: {path}")
        count += len(entries)
        api.require(count <= descriptor["count"], "Work ledger count exceeds manifest")
        pages.append(entries)
        head = page.get("previous")
    api.require(count == descriptor["count"], "Work ledger count does not match manifest")
    return [entry for page in reversed(pages) for entry in page]


def read_work(api, store, identifier: str, *, history: bool = True) -> tuple[dict, str]:
    path = work_path(api, store, identifier) / "WORK.md"
    meta, body = api.decode(api.read(path))
    validate_header(api, meta, identifier)
    if history and meta["schema"] == 2:
        for key in LEDGER_KEYS:
            meta[key] = read_ledger(api, store, identifier, key, meta["ledgers"][key])
    return meta, body


def all_work(api, store, *, history: bool = True) -> list[dict]:
    base = store.path("work")
    if not base.exists():
        return []
    result = []
    # Bootstrap/navigation inspect only direct manifests, never recursive scratch
    # files or historical ledger pages. Full integrity checking remains explicit.
    for entry in sorted(base.iterdir()):
        folder = api.safe_path(base, entry.name)
        if folder.is_dir() and (folder / "WORK.md").exists():
            result.append(read_work(api, store, folder.name, history=history)[0])
    return sorted(result, key=lambda x: (x["updated_at"], x["id"]), reverse=True)


def summary(api, store, limit: int = 5, offset: int = 0) -> dict:
    api.require(1 <= limit <= 100 and offset >= 0, "Use offset >= 0 and limit 1..100")
    entries = [m for m in all_work(api, store, history=False) if m["status"] != "closed"]
    end = min(len(entries), offset + limit)
    return {"items": [{k: m[k] for k in ("id", "title", "status")} for m in entries[offset:end]],
            "remaining": max(0, len(entries) - end), "next_offset": end if end < len(entries) else None,
            "total": len(entries), "command": "work list",
            "note": "Navigation only. Resume a relevant workspace explicitly; it is not a mandate."}


def index_text(api, store) -> str:
    entries = [m for m in all_work(api, store, history=False) if m["status"] != "closed"]
    lines = ["# Unfinished activities", "", "Generated navigation, not additional instructions. Use work show ID for detail.", ""]
    size, shown = len("\n".join(lines).encode("utf-8")), 0
    for item in entries:
        line = json.dumps({k: item[k] for k in ("id", "title", "status", "next_action")}, ensure_ascii=False)
        if shown == 100 or size + len(line.encode("utf-8")) + 128 > api.MAX_RECORD // 2:
            break
        lines.append(line)
        size += len(line.encode("utf-8")) + 1
        shown += 1
    if not entries:
        lines.append("No unfinished activities.")
    elif shown < len(entries):
        lines.append(f"{len(entries) - shown} further activities omitted; use work list --offset {shown} --limit 50.")
    return "\n".join(lines) + "\n"


def reindex(api, store) -> None:
    api.write_atomic(store.path("work/INDEX.md"), index_text(api, store))


def storage_plan(api, store, meta: dict, body: str) -> tuple[str, dict[str, bytes]]:
    """Prepare all bounded pages and the compact manifest before any write.

    Pages are content-addressed and linked backwards. WORK.md switches heads
    only after every new page exists. A crash can leave unreferenced pages, never
    a partially committed ledger or a truncated history. Earlier pages are kept.
    """
    candidate = copy.deepcopy(meta)
    candidate["schema"] = 2
    candidate["updated_at"] = api.now()
    candidate["ledgers"] = {}
    pages: dict[str, bytes] = {}
    for key in LEDGER_KEYS:
        entries = candidate.pop(key, [] if key == "draft_decisions" else None)
        api.require(isinstance(entries, list) and all(isinstance(x, dict) for x in entries),
                    f"Save requires the full {key} ledger; do not save a navigation-only header")
        head, chunk = None, []

        def encode_page(items):
            return (json.dumps({"schema": 1, "work_id": meta["id"], "ledger": key,
                                "previous": head, "entries": items}, ensure_ascii=False,
                               sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

        def finish(items):
            data = encode_page(items)
            api.require(len(data) <= min(PAGE_BYTES, api.MAX_RECORD),
                        f"One {key} entry exceeds the ledger-page budget; shorten it before publication")
            digest = sha(data)
            pages[digest] = data
            return digest

        for entry in entries:
            trial = [*chunk, entry]
            if chunk and len(encode_page(trial)) > min(PAGE_BYTES, api.MAX_RECORD):
                head = finish(chunk)
                chunk = []
            chunk.append(entry)
        if chunk:
            head = finish(chunk)
        candidate["ledgers"][key] = {"head": head, "count": len(entries)}
    validate_header(api, candidate, meta["id"])
    text = api.encode(candidate, body)
    api.require(len(text.encode("utf-8")) <= api.MAX_RECORD,
                "Workspace notes/header exceed the file budget; shorten the handoff, not its ledger. Previous state is unchanged.")
    return text, pages


def write_storage(api, store, identifier: str, text: str, pages: dict[str, bytes], *, exclusive: bool = False) -> None:
    folder = work_path(api, store, identifier)
    for digest, data in pages.items():
        path = api.safe_path(folder, f"ledger/{digest}.json")
        if path.exists():
            api.require(path.read_bytes() == data, f"Existing work ledger page differs: {path}")
        else:
            api.write_atomic(path, data, exclusive=True)
    api.write_atomic(folder / "WORK.md", text, exclusive=exclusive)
    reindex(api, store)


def save_work(api, store, meta: dict, body: str, *, exclusive: bool = False) -> None:
    text, pages = storage_plan(api, store, meta, body)
    write_storage(api, store, meta["id"], text, pages, exclusive=exclusive)


def repair_storage(api, store, identifier: str) -> dict:
    """Explicit recovery for v1 manifests oversized by the old write-before-check bug."""
    path = api.safe_path(work_path(api, store, identifier), "WORK.md")
    api.require(path.is_file() and path.stat().st_size <= LEGACY_WORK_BYTES,
                "Legacy workspace recovery supports a regular file up to 16 MB; preserve it for manual repair")
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    header, separator, body = text.partition("\n---\n")
    api.require(text.startswith("---\n") and bool(separator), "Malformed legacy workspace")
    meta = json.loads(header[4:])
    api.require(isinstance(meta, dict) and meta.get("schema") == 1,
                "repair-storage only converts legacy workspace schema 1; current ledgers are not reset")
    validate_header(api, meta, identifier)
    storage_plan(api, store, meta, body.strip())  # Includes the header budget; no writes yet.
    backup = api.safe_path(path.parent, f"ledger/legacy/{sha(raw)}.md")
    if backup.exists():
        api.require(backup.read_bytes() == raw, "Legacy workspace backup differs")
    else:
        api.write_atomic(backup, raw, exclusive=True)
    api.require(path.read_bytes() == raw, "Workspace changed during recovery")
    save_work(api, store, meta, body.strip())
    return {"work": identifier, "workspace_schema": 2, "backup": backup.relative_to(store.root).as_posix(),
            "note": "Exact original bytes retained. Accepted memories and activity decisions were not changed."}


def start(api, store, title: str, scope: str, *, identifier: str | None = None) -> dict:
    identifier = identifier or "W-" + uuid.uuid4().hex[:12]
    folder = work_path(api, store, identifier)
    api.require(not folder.exists(), f"Workspace already exists: {identifier}")
    meta = {"schema": 1, "kind": "work", "id": identifier, "title": field(api, title, "title", 160),
            "scope": field(api, scope, "scope"), "status": "open", "next_action": "Establish current state and next action.",
            "created_at": api.now(), "updated_at": api.now(), "activity_revision": 1,
            **{key: [] for key in LEDGER_KEYS}}
    text, pages = storage_plan(api, store, meta, BANNER)
    write_storage(api, store, identifier, text, pages, exclusive=True)
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
    if meta.get("kind") == "lesson":
        api.require(type(meta.get("revision")) is int and meta["revision"] >= 1, "Invalid draft revision")
    suffix = f"-r{meta['revision']}" if meta.get("kind") == "lesson" else ""
    folder = work_path(api, store, identifier) / "drafts"
    path = api.safe_path(folder, f"{meta['id']}{suffix}.md")
    work["activity_revision"] += 1
    storage_plan(api, store, work, body)  # Do not create a draft if the manifest is unsavable.
    while True:
        try:
            api.write_atomic(path, text, exclusive=True)
            break
        except FileExistsError:
            # Retain the previous draft and its publication linkage; copying an
            # accepted revision never silently changes its metadata/revision.
            path = api.safe_path(folder, f"{meta['id']}{suffix}-draft-{uuid.uuid4().hex[:12]}.md")
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
    rel = path.relative_to(work_path(api, store, identifier)).as_posix()
    latest = last_draft_decision(work, rel)
    api.require(not latest or latest["decision"] != "abandoned",
                "Draft is abandoned; use work resume-draft with a reason before publishing it")
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
                "questions": ["Experience retention: is there a useful observation, finding, correction, or limit worth preserving as an episode, even without a reusable lesson? Check for an existing record before duplicating it.",
                              "Practice learning: does the evidence warrant a scoped proposed lesson, review, or reconciliation, separately from retaining the experience?",
                              "Self-assessment: is there evidence about the agent's own behavior that warrants a recorded change, rather than merely a fact about the subject?",
                              "Are local support, untested transfer, and causal attribution being assessed separately?",
                              "What should be retained, what remains unchanged or uncertain, and when should it be revisited?"],
                "note": "Inspect full records and related memory. A no-update checkpoint may cite retained episode IDs in --records: it means no further lesson or self-model change, not that nothing was worth storing. Retaining nothing is also valid. These are agent-owned decisions, not automatic publication or proof."}
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


def last_draft_decision(meta: dict, relative: str) -> dict | None:
    return next((item for item in reversed(meta.get("draft_decisions", [])) if item.get("draft") == relative), None)


def draft_decision(api, store, identifier: str, path: Path, decision: str, reason: str) -> dict:
    meta, body = read_work(api, store, identifier)
    api.require(meta["status"] != "closed", "Resume the workspace before changing draft decisions")
    api.require(decision in {"abandoned", "resumed"}, "Invalid draft decision")
    reason = field(api, reason, "draft decision reason", 2000)
    folder = work_path(api, store, identifier)
    if not path.is_absolute() and path.parts and path.parts[0] == "drafts":
        path = api.safe_path(folder, path.as_posix())
    else:
        path = path.absolute()
    api.require(owner(api, store, path) == identifier, "Choose a draft belonging to this workspace")
    api.require(path.is_file() and path.stat().st_size <= api.MAX_RECORD, "Draft must be a regular file within the record-size budget")
    rel, digest = path.relative_to(folder).as_posix(), sha(path.read_bytes())
    previous = last_draft_decision(meta, rel)
    if previous and all(previous.get(k) == value for k, value in
                        (("decision", decision), ("draft_sha256", digest), ("reason", reason))):
        return previous  # Safe retry after a successful ledger update.
    if decision == "resumed":
        api.require(previous and previous["decision"] == "abandoned", "Draft is not abandoned")
    meta["activity_revision"] += 1
    entry = {"draft": rel, "draft_sha256": digest, "decision": decision, "reason": reason,
             "activity_revision": meta["activity_revision"], "at": api.now()}
    meta["draft_decisions"].append(entry)
    save_work(api, store, meta, body)
    return {**entry, "note": "Draft retained. No accepted record was published, retired, or changed. Run a new checkpoint before closing."}


def update(api, store, identifier: str, status: str | None, next_action: str | None) -> dict:
    work, body = read_work(api, store, identifier)
    api.require(status is None or status in {"open", "paused", "closed"}, "Invalid work status")
    if status == "closed":
        api.require(work["checkpoints"] and work["checkpoints"][-1]["activity_revision"] == work["activity_revision"],
                    "Run a current learning checkpoint before closing; defer/no-update are valid")
        # Do not silently abandon a changed/unpublished draft.
        for path in store.files(f"work/{identifier}/drafts", "*"):
            rel = path.relative_to(work_path(api, store, identifier)).as_posix()
            digest = sha(path.read_bytes())
            published = any(p["draft"] == rel and p["draft_sha256"] == digest for p in work["publications"])
            decision = last_draft_decision(work, rel)
            abandoned = decision and decision["decision"] == "abandoned" and decision["draft_sha256"] == digest
            api.require(published or abandoned,
                        f"Unpublished or changed draft remains: {rel}; publish, explicitly abandon it with a reason, or pause the activity")
    if next_action:
        work["next_action"] = field(api, next_action, "next action")
    if status == "open" and work["status"] != "open":
        work["activity_revision"] += 1
    if status:
        work["status"] = status
    save_work(api, store, work, body)
    return {k: work[k] for k in ("id", "status", "next_action", "activity_revision")}


def token_sequence(text: str) -> tuple[str, ...]:
    """Keep order, repetitions and stop words for phrases; preserve API compounds."""
    return tuple(re.findall(r"[^\W_]+(?:[-_][^\W_]+)*", text.casefold(), re.UNICODE))


def tokens(text: str) -> set[str]:
    return set(token_sequence(text))


def contains_phrase(sequence: tuple[str, ...], phrase: tuple[str, ...]) -> bool:
    return bool(phrase) and any(sequence[i:i + len(phrase)] == phrase
                               for i in range(len(sequence) - len(phrase) + 1))


def query_key(query: list[str]) -> str:
    # Old keys were unordered bags without stop words. Retain them as history,
    # but never reinterpret them as decisions about this phrase-aware query.
    return "phrases-v1:" + " ".join(token_sequence(" ".join(query)))


def query_features(query: list[str], groups: list[list[str]]) -> tuple[set[str], dict[str, tuple[str, ...]]]:
    sequence = token_sequence(" ".join(query))
    original = set(sequence) - STOP_WORDS
    features = {term: (term,) for term in original}
    for group in groups:
        aliases = [token_sequence(alias) for alias in group]
        # Trigger only from the original query, never from another expansion.
        # In particular, "source" does not trigger "source of truth".
        if any(contains_phrase(sequence, alias) for alias in aliases):
            for alias in aliases:
                if alias and (len(alias) > 1 or alias[0] not in STOP_WORDS):
                    features[" ".join(alias)] = alias
    return original, features


def matching_features(features: dict[str, tuple[str, ...]], fields: list[str]) -> set[str]:
    # A phrase must occur within one field, not across unrelated tags/title/scope.
    sequences = [token_sequence(text) for text in fields]
    single_words = set().union(*(set(sequence) for sequence in sequences))
    return {label for label, phrase in features.items()
            if (phrase[0] in single_words if len(phrase) == 1 else
                any(contains_phrase(sequence, phrase) for sequence in sequences))}


def retrieve(api, store, query: list[str], limit: int, scope: str | None, kind: str = "lessons", work_id: str | None = None) -> list[dict]:
    records, lessons = store.snapshot()
    api.require(kind in {"lessons", "episodes"} and 1 <= limit <= 50, "Invalid search kind or limit")
    vocabulary, _ = api.decode(api.read(store.path("memory/vocabulary.md")))
    groups = vocabulary.get("groups")
    api.require(isinstance(groups, list) and all(isinstance(g, list) and all(isinstance(t, str) for t in g) for g in groups), "Invalid vocabulary groups")
    original, features = query_features(query, groups)
    api.require(bool(original), "Use at least one nontrivial search term")
    terms = set(features)
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
        header = matching_features(features, [meta["id"], meta["title"], meta.get("domain", ""),
                                              *meta.get("tags", []), *meta.get("aliases", []), *scopes])
        docs.append((meta, body, path, header, matching_features(features, [body])))
    frequency = {term: sum(term in d[3] or term in d[4] for d in docs) for term in terms}
    rejected = set()
    if work_id:
        work, _ = read_work(api, store, work_id)
        rejected = {(r.get("record"), r.get("query")) for r in work["rejections"] if r.get("activity_revision") == work["activity_revision"]}
    normalized_query = query_key(query)
    results = []
    for meta, body, path, header, body_terms in docs:
        matches = terms & (header | body_terms)
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
            item.update(revision=meta["revision"], status=meta["status"], scope=meta["scope"],
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
    api.require(bool(tokens(" ".join(query)) - STOP_WORDS), "Supply the exact search terms being rejected")
    normalized = query_key(query)
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
        for item in meta["draft_decisions"]:
            parts = api.portable_parts(item.get("draft", ""))
            api.require(len(parts) >= 2 and parts[0] == "drafts" and item.get("decision") in {"abandoned", "resumed"}
                        and isinstance(item.get("draft_sha256"), str) and bool(DIGEST.fullmatch(item["draft_sha256"])),
                        "Invalid retained draft decision")
            field(api, item.get("reason"), "draft decision reason", 2000)
            path = api.safe_path(folder, item["draft"])
            if item == last_draft_decision(meta, item["draft"]) and item["decision"] == "abandoned":
                if not path.is_file() or sha(path.read_bytes()) != item["draft_sha256"]:
                    warnings.append({"work": meta["id"], "draft": item["draft"], "warning": "Abandoned draft is missing or changed; its old decision does not cover new contents"})
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
    p = actions.add_parser("list")
    p.add_argument("--offset", type=int, default=0); p.add_argument("--limit", type=int, default=100)
    p = actions.add_parser("show"); p.add_argument("id")
    p = actions.add_parser("history"); p.add_argument("id")
    p.add_argument("--kind", choices=LEDGER_KEYS, required=True)
    p.add_argument("--offset", type=int, default=0); p.add_argument("--limit", type=int, default=20)
    p = actions.add_parser("repair-storage"); p.add_argument("id")
    for action in ("abandon-draft", "resume-draft"):
        p = actions.add_parser(action); p.add_argument("id"); p.add_argument("file", type=Path)
        p.add_argument("--reason", required=True)
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
        return {"work": summary(api, store, args.limit, args.offset)}
    if command == "show":
        meta, body = read_work(api, store, args.id)
        counts = {key: len(meta[key]) for key in LEDGER_KEYS}
        for key in LEDGER_KEYS:
            meta[key] = meta[key][-10:]
        return {"work": meta, "notes": body, "ledger_counts": counts,
                "omitted": {key: max(0, count - 10) for key, count in counts.items()},
                "note": "Only ten recent entries per ledger are shown. Use work history for older entries."}
    if command == "history":
        api.require(args.offset >= 0 and 1 <= args.limit <= 100, "Use offset >= 0 and limit 1..100")
        meta, _ = read_work(api, store, args.id)
        entries = meta[args.kind]
        end = min(len(entries), args.offset + args.limit)
        return {"work": args.id, "kind": args.kind, "entries": entries[args.offset:end], "total": len(entries),
                "next_offset": end if end < len(entries) else None}
    if command == "repair-storage":
        return repair_storage(api, store, args.id)
    if command in {"abandon-draft", "resume-draft"}:
        return draft_decision(api, store, args.id, args.file,
                              "abandoned" if command == "abandon-draft" else "resumed", args.reason)
    if command == "update":
        return update(api, store, args.id, args.status, args.next_action)
    if command == "checkpoint":
        return checkpoint(api, store, args.id, args.decision, args.reason, args.records, args.next_review, args.limit)
    if command == "evidence":
        return evidence(api, store, args.id, args.file)
    return reject_candidate(api, store, args.id, args.record, args.query, args.reason)
