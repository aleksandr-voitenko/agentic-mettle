"""Transient comparison packets. Selection is mechanical; judgments belong to the agent."""
from __future__ import annotations

import json
import re

MAX_BYTES = 16_000
MAX_SEEDS = 8
MAX_CONTEXTS = 8
MAX_REVIEW_CONTEXTS = 8
LEXICAL_LIMIT = 5


def serialized(packet):
    """Match the work command's JSON output, including its final newline."""
    return json.dumps(packet, ensure_ascii=False, indent=2) + "\n"


def split_ref(api, ref):
    identifier, separator, revision = ref.partition("@")
    api.require(bool(api.ID_PATTERN.fullmatch(identifier)), f"Invalid accepted reference: {ref}")
    api.require(not separator or (identifier.startswith("L-") and re.fullmatch(r"[1-9][0-9]*", revision)),
                f"Use a lesson ID@revision: {ref}")
    return identifier, int(revision) if separator else None


def detail(ref):
    identifier, separator, revision = ref.partition("@")
    return ["show", identifier] + (["--revision", revision] if separator else [])


def packet(api, store, identifier, records=(), query=(), limit=12, offset=0):
    api.require(type(limit) is int and 1 <= limit <= 30 and type(offset) is int and offset >= 0,
                "Use --limit 1..30 and --offset >= 0")
    api.require(len(records) <= MAX_SEEDS, "Use at most eight explicit references; split the comparison")
    api.require(len(json.dumps([list(records), list(query)], ensure_ascii=False).encode("utf-8")) <= 2048,
                "Comparison inputs exceed 2048 UTF-8 bytes; split the comparison")
    work_api = api.local_module("mettle_work")
    work, _ = work_api.read_work(api, store, identifier)
    publications = list(dict.fromkeys(p["record"] for p in reversed(work["publications"])))
    seeds = list(dict.fromkeys(records)) if records else publications[:MAX_SEEDS]
    with api.local_module("mettle_catalogue").open_catalogue(api, store) as catalogue:
        # Validate every requested seed even when a later page omits it. No
        # cached body, draft, workspace note, or old current.md supplies evidence.
        seeds = [work_api.reference(catalogue.get(*split_ref(api, ref))[0]) for ref in seeds]
        seeds = list(dict.fromkeys(seeds))
        metadata = {work_api.reference(meta): meta for meta in catalogue.metadata()}
        heads = {}
        for ref, meta in metadata.items():
            if meta["kind"] == "lesson" and meta["revision"] > heads.get(meta["id"], {}).get("revision", 0):
                heads[meta["id"]] = meta
        candidates, counter = {}, set()

        def add(ref, reason, priority=2, counterevidence=False):
            if ref.startswith("L-") and "@" not in ref:
                api.require(ref in heads, f"Missing linked lesson: {ref}; run check")
                ref = work_api.reference(heads[ref])
            api.require(ref in metadata, f"Missing linked record: {ref}; run check")
            if ref not in candidates or priority < candidates[ref][0]:
                candidates[ref] = (priority, reason)
            if counterevidence:
                counter.add(ref)

        def review_sources(ref):
            for target in metadata[ref]["episodes"]:
                add(target, f"observation for {ref}", 3)

        def edges(ref):
            meta = metadata[ref]
            kind = meta["kind"]
            if kind == "episode":
                for target in meta["corrects"]:
                    add(target, f"corrected by {ref}")
            elif kind == "review":
                target = f"{meta['lesson']}@{meta['lesson_revision']}"
                add(target, f"assessed by {ref}")
                review_sources(ref)
            elif kind == "reconciliation":
                for target in meta["inputs"] + meta["evidence"]:
                    add(target, f"input/evidence for plan {ref}", 3)
            else:
                for field in ("origin", "support", "counterevidence", "reconciliations", "supersedes", "superseded_by"):
                    for target in meta[field]:
                        add(target, f"{field} of {ref}", 1 if field == "counterevidence" else 3,
                            field == "counterevidence")

        for ref in seeds:
            add(ref, "explicit input" if records else "activity publication", 0)
            edges(ref)
        corrected = {target for ref in seeds if metadata[ref]["kind"] == "episode"
                     for target in metadata[ref]["corrects"]}
        discovery_inputs = set(seeds) | corrected
        # One correction hop can expose the observations behind earlier guidance.
        # Reverse discovery across activities uses cached metadata, not bodies;
        # newly found episodes do not recursively extend these discovery inputs.
        for ref, meta in metadata.items():
            kind = meta["kind"]
            if kind == "review" and discovery_inputs.intersection(meta["episodes"]):
                add(ref, "review of corrected observation" if corrected.intersection(meta["episodes"])
                    else "review of triggering observation")
                add(f"{meta['lesson']}@{meta['lesson_revision']}", f"assessed by {ref}")
            elif kind == "lesson" and (meta == heads[meta["id"]] or discovery_inputs.intersection(meta["reconciliations"])):
                if discovery_inputs.intersection(meta["origin"] + meta["support"] + meta["counterevidence"] + meta["reconciliations"]):
                    add(ref, "lesson referencing corrected observation" if corrected.intersection(meta["origin"])
                        else "lesson referencing input")
            elif kind == "reconciliation" and discovery_inputs.intersection(meta["evidence"] + meta["inputs"]):
                add(ref, "reconciliation plan referencing input", 3)
                for target in meta["inputs"]:
                    add(target, f"input to plan {ref}")

        ranked = work_api.rank_candidates(api, store, catalogue, list(query), None, "lessons", identifier,
                                          history=True, work=work) if query else []
        for item in ranked[:LEXICAL_LIMIT]:
            add(f"{item['id']}@{item['revision']}", "lexical candidate; relationship unassessed", 4)
        # Exact old revisions retain their own identity; the head is a separate
        # item. Limit context expansion, not the existence of these pointers.
        for ref in list(candidates):
            meta = metadata[ref]
            if meta["kind"] == "lesson" and ref != work_api.reference(heads[meta["id"]]):
                add(meta["id"], f"latest revision of {meta['id']}")
        contexts = sorted((r for r in candidates if metadata[r]["kind"] == "lesson"),
                          key=lambda r: (candidates[r][0], r))
        for ref in contexts[:MAX_CONTEXTS]:
            edges(ref)
        # Include reviews absent from current evidence before expanding sources.
        lesson_ids = {metadata[r]["id"] for r in candidates if metadata[r]["kind"] == "lesson"}
        for ref, meta in metadata.items():
            if meta["kind"] == "review" and meta["lesson"] in lesson_ids:
                target = f"{meta['lesson']}@{meta['lesson_revision']}"
                is_counter = meta["assessment"] == "counterexample"
                state = "incorporated" if ref in heads[meta["lesson"]]["counterevidence"] else "pending"
                reason = f"counterexample for {target}; {state} in latest" if is_counter else f"{meta['assessment']} review of {target}"
                add(ref, reason, 1 if is_counter else 3, is_counter)

        # Follow only review -> source episodes -> corrections, not a graph walk.
        # Explicit review seeds are first and were already expanded by edges().
        reviews = sorted((r for r in candidates if metadata[r]["kind"] == "review"),
                         key=lambda r: (candidates[r][0], r))
        expanded_reviews = set(reviews[:MAX_REVIEW_CONTEXTS])
        unexpanded_reviews = reviews[MAX_REVIEW_CONTEXTS:]
        for ref in reviews[:MAX_REVIEW_CONTEXTS]:
            if ref not in seeds:
                review_sources(ref)
        episode_ids = {r for r in candidates if metadata[r]["kind"] == "episode"}
        for ref, meta in metadata.items():
            if meta["kind"] == "episode":
                targets = sorted(episode_ids.intersection(meta["corrects"]))
                if targets:
                    add(ref, f"corrects {targets[0]}", 1, True)
        ordered = sorted(candidates, key=lambda r: (candidates[r][0], r))
        base_argv = ["work", "consolidate", identifier]
        if records:
            base_argv += ["--records", *records]
        if query:
            base_argv += ["--query=" + " ".join(query)]
        base_argv += ["--limit", str(limit)]

        def expand_sources(ref):
            return ["work", "consolidate", identifier, "--records", ref]

        def page(items, end, oversized=()):
            included = {item["ref"] for item in items}
            return {
                "work": identifier, "activity_revision": work["activity_revision"], "seeds": seeds,
                "items": items, "total_selected": len(ordered), "offset": offset,
                "remaining": max(0, len(ordered) - end),
                "next_argv": base_argv + ["--offset", str(end)] if end < len(ordered) else None,
                "omissions": {
                    "explicit_not_on_page": [r for r in seeds if records and r not in included],
                    "older_activity_seeds": max(0, len(publications) - MAX_SEEDS) if not records else 0,
                    "activity_history_argv": ["work", "history", identifier, "--kind", "publications", "--limit", "20"],
                    "lexical_matches": max(0, len(ranked) - LEXICAL_LIMIT),
                    "lexical_next_argv": ["search", "--kind", "lessons", "--history", "--work", identifier,
                                          "--offset", str(LEXICAL_LIMIT), "--limit", "5", "--", *query] if len(ranked) > LEXICAL_LIMIT else None,
                    "lesson_contexts_not_expanded": max(0, len(contexts) - MAX_CONTEXTS),
                    "review_sources_not_expanded": len(unexpanded_reviews),
                    "review_sources_next_argv": expand_sources(unexpanded_reviews[0]) if unexpanded_reviews else None,
                    "counterevidence_known": len(counter), "counterevidence_not_on_page": len(counter - included),
                    "path_exceeds_page": list(oversized),
                },
                "notice": "Informational comparison, not a checkpoint or applied change. Read full records using show ID [--revision N] before judgment. "
                          "Page offsets cover this selected set on an unchanged store; refresh after changes. Follow next_argv, or select an exact ref with --records for more context. "
                          "Expansion is not recursive: none included does not mean none exists. Cached metadata/query work grows with the archive; canonical validation is targeted. "
                          "Reconciliation records describe intent, not proof of publication. See CONSOLIDATION_REFERENCE.md.",
            }

        items, end, oversized = [], min(offset, len(ordered)), []
        result = page(items, end)
        for ref in ordered[offset:offset + limit]:
            meta, body, path = catalogue.get(*split_ref(api, ref))
            item = {"ref": ref, "kind": meta["kind"], "path": path.relative_to(store.root).as_posix(),
                    "reason": candidates[ref][1], "detail_argv": detail(ref)}
            if meta["kind"] == "lesson":
                head = heads[meta["id"]]
                latest = meta["revision"] == head["revision"]
                item.update(status=meta["status"], latest_revision=head["revision"], latest_status=head["status"],
                            is_latest=latest, current_candidate=latest and meta["status"] not in {"retired", "superseded"})
            elif meta["kind"] == "review":
                item.update(assessment=meta["assessment"], lesson_ref=f"{meta['lesson']}@{meta['lesson_revision']}",
                            source_episodes_expanded=ref in expanded_reviews)
                if ref not in expanded_reviews:
                    item["expand_sources_argv"] = expand_sources(ref)
                if meta["assessment"] == "counterexample":
                    item["counterevidence_state"] = "incorporated" if ref in heads[meta["lesson"]]["counterevidence"] else "pending"
            else:
                item["status"] = "observation-not-instruction" if meta["kind"] == "episode" else "intent-not-proof-of-publication"
            item["preview"] = {"title": meta["title"][:160], "body": body[:240], "shortened": len(meta["title"]) > 160 or len(body) > 240}
            candidate = page(items + [item], end + 1, oversized)
            if len(serialized(candidate).encode("utf-8")) > MAX_BYTES:
                del item["preview"]
                candidate = page(items + [item], end + 1, oversized)
            if len(serialized(candidate).encode("utf-8")) > MAX_BYTES:
                if items:
                    break
                # A legal canonical path can itself exceed this context budget.
                # Advance with an explicit exact reference, never a truncated path.
                oversized.append({"ref": ref, "detail_argv": detail(ref)})
                end += 1
                result = page(items, end, oversized)
                break
            items.append(item)
            end += 1
            result = candidate
        api.require(len(serialized(result).encode("utf-8")) <= MAX_BYTES, "Packet wrapper exceeds budget; split inputs")
        return result
