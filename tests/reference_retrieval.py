"""Frozen 0.3.0 retrieval oracle for synthetic parity/operation-count checks.

Keep independent of the optimized enrichment path. No production imports of this module.
"""
import math
from mettle_work import (query_features, matching_features, read_work, query_key,
                         reference, GENERIC_WORDS)

def retrieve_reference(api, store, query: list[str], limit: int, scope: str | None, kind: str = "lessons", work_id: str | None = None) -> list[dict]:
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
