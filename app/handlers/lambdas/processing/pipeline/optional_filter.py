import logging
from urllib.parse import urlparse

from shared.logging import log_decision
from shared.pipeline.processing_types import OptionalCandidate, OptionalDecision
from shared.pipeline.url_norm import canonical_host, canonical_url


logger = logging.getLogger(__name__)


CATEGORY_PRIORITY = {
    "tutorial_example": 0,
    "sitemap": 1,
    "contact": 2,
    "social_x": 3,
    "creator_team": 4,
    "repository": 5,
}

CATEGORY_CAP = {
    "contact": 2,
    "social_x": 1,
    "creator_team": 2,
    "sitemap": 1,
    "repository": 2,
    "tutorial_example": 3,
}

SOURCE_SCORE = {
    "homepage": 2,
    "root_page": 1,
}

CONTACT_KEYWORDS = {"contact", "support", "help", "email"}
CREATOR_TEAM_KEYWORDS = {
    "creator",
    "creators",
    "team",
    "about",
    "founder",
    "founders",
    "company",
    "who-we-are",
}
TUTORIAL_EXAMPLE_KEYWORDS = {
    "tutorial",
    "tutorials",
    "example",
    "examples",
    "sample",
    "samples",
    "getting-started",
    "quickstart",
    "guide",
    "playground",
}


def filter_optionals(
    candidates: list[OptionalCandidate],
    core_urls: set[str],
    *,
    decision_context: dict[str, str] | None = None,
) -> list[tuple[OptionalCandidate, OptionalDecision]]:
    context_fields = decision_context or {}
    decision_candidates: list[tuple[OptionalCandidate, OptionalDecision]] = []
    decision_candidates.extend(_filter_by_category(candidates, "tutorial_example"))
    decision_candidates.extend(_filter_by_category(candidates, "sitemap"))
    decision_candidates.extend(_filter_by_category(candidates, "contact"))
    decision_candidates.extend(_filter_by_category(candidates, "social_x"))
    decision_candidates.extend(_filter_by_category(candidates, "creator_team"))
    decision_candidates.extend(_filter_by_category(candidates, "repository"))

    sorted_candidates = sorted(
        decision_candidates,
        key=lambda candidate_and_decision: _decision_sort_key(
            candidate_and_decision[0],
            candidate_and_decision[1],
        ),
    )
    deduped_candidates = _dedupe_by_canonical_url(sorted_candidates)
    conflict_free_candidates = _drop_core_conflicts(deduped_candidates, core_urls)
    capped_candidates = _apply_category_caps(conflict_free_candidates)

    log_decision(
        logger,
        decision_name="optional_filter.completed",
        reason="optional links classified, deduped, conflict-filtered, and capped",
        candidate_count=len(candidates),
        classified_count=len(decision_candidates),
        deduped_count=len(deduped_candidates),
        conflict_free_count=len(conflict_free_candidates),
        selected_count=len(capped_candidates),
        **context_fields,
    )

    return capped_candidates


def build_optional_description(
    decision: OptionalDecision,
    candidate: OptionalCandidate,
) -> str:
    if decision.category == "contact":
        return "Contact channel for support or questions"
    if decision.category == "social_x":
        return "Official X profile for updates"
    if decision.category == "creator_team":
        return "Creator or team profile"
    if decision.category == "sitemap":
        return "Machine-readable sitemap for site discovery"
    if decision.category == "repository":
        return "Official source repository and related code resources"
    if decision.category == "tutorial_example":
        return "Tutorial or example resource for practical learning"
    return f"Secondary resource discovered from {candidate.source_kind}"


def classify_optional_category(candidate: OptionalCandidate) -> str | None:
    parsed_candidate_url = urlparse(candidate.url)
    normalized_host = canonical_host(parsed_candidate_url.hostname or "")
    normalized_path = parsed_candidate_url.path.lower()
    candidate_context = _combined_context(candidate)

    if normalized_path in {"/sitemap.xml", "/sitemap_index.xml"}:
        return "sitemap"
    if candidate.url.startswith("mailto:"):
        return "contact"
    if normalized_host in {"x.com", "twitter.com"}:
        return "social_x"
    if _is_github_repository_link(parsed_candidate_url):
        return "repository"
    if _contains_keyword(candidate_context, CREATOR_TEAM_KEYWORDS):
        return "creator_team"
    if _contains_keyword(candidate_context, TUTORIAL_EXAMPLE_KEYWORDS):
        return "tutorial_example"
    if _contains_keyword(candidate_context, CONTACT_KEYWORDS):
        return "contact"
    return None


def _filter_by_category(
    candidates: list[OptionalCandidate],
    target_category: str,
) -> list[tuple[OptionalCandidate, OptionalDecision]]:
    filtered_candidates: list[tuple[OptionalCandidate, OptionalDecision]] = []
    for candidate in candidates:
        detected_category = classify_optional_category(candidate)
        if detected_category != target_category:
            continue

        decision_score, decision_reason = _score_candidate(candidate, detected_category)
        filtered_candidates.append(
            (
                candidate,
                OptionalDecision(
                    category=detected_category,
                    score=decision_score,
                    reason=decision_reason,
                ),
            )
        )
    return filtered_candidates


def _score_candidate(candidate: OptionalCandidate, category: str) -> tuple[int, str]:
    score = SOURCE_SCORE.get(candidate.source_kind, 0)
    scoring_reasons: list[str] = [f"source:{candidate.source_kind}"]
    parsed_candidate_url = urlparse(candidate.url)

    if category == "contact":
        if candidate.url.startswith("mailto:"):
            score += 2
            scoring_reasons.append("bonus:mailto")
        if _contains_keyword(_combined_context(candidate), CONTACT_KEYWORDS):
            score += 2
            scoring_reasons.append("bonus:contact_keyword")

    if category == "social_x":
        normalized_host = canonical_host(parsed_candidate_url.hostname or "")
        if normalized_host in {"x.com", "twitter.com"}:
            score += 2
            scoring_reasons.append("bonus:x_host")

    if category == "creator_team" and _contains_keyword(
        _combined_context(candidate), CREATOR_TEAM_KEYWORDS
    ):
        score += 1
        scoring_reasons.append("bonus:creator_keyword")

    if category == "sitemap":
        normalized_path = parsed_candidate_url.path.lower()
        if normalized_path in {"/sitemap.xml", "/sitemap_index.xml"}:
            score += 2
            scoring_reasons.append("bonus:sitemap_exact")

    return score, ",".join(scoring_reasons)


def _decision_sort_key(
    candidate: OptionalCandidate,
    decision: OptionalDecision,
) -> tuple[int, int, str]:
    category_priority = CATEGORY_PRIORITY.get(decision.category, 999)
    normalized_candidate_url = _optional_sort_url(candidate.url)
    return (-decision.score, category_priority, normalized_candidate_url)


def _optional_sort_url(raw_url: str) -> str:
    if raw_url.startswith("mailto:"):
        return raw_url.lower()
    return canonical_url(raw_url)


def _dedupe_by_canonical_url(
    candidate_decisions: list[tuple[OptionalCandidate, OptionalDecision]],
) -> list[tuple[OptionalCandidate, OptionalDecision]]:
    deduped_candidates: list[tuple[OptionalCandidate, OptionalDecision]] = []
    seen_urls: set[str] = set()

    for candidate, decision in candidate_decisions:
        normalized_candidate_url = _optional_sort_url(candidate.url)
        if normalized_candidate_url in seen_urls:
            continue
        seen_urls.add(normalized_candidate_url)
        deduped_candidates.append((candidate, decision))

    return deduped_candidates


def _drop_core_conflicts(
    candidate_decisions: list[tuple[OptionalCandidate, OptionalDecision]],
    core_urls: set[str],
) -> list[tuple[OptionalCandidate, OptionalDecision]]:
    conflict_free_candidates: list[tuple[OptionalCandidate, OptionalDecision]] = []
    for candidate, decision in candidate_decisions:
        if candidate.url.startswith("mailto:"):
            conflict_free_candidates.append((candidate, decision))
            continue

        normalized_candidate_url = canonical_url(candidate.url)
        if normalized_candidate_url in core_urls:
            continue
        conflict_free_candidates.append((candidate, decision))
    return conflict_free_candidates


def _apply_category_caps(
    candidate_decisions: list[tuple[OptionalCandidate, OptionalDecision]],
) -> list[tuple[OptionalCandidate, OptionalDecision]]:
    category_counts: dict[str, int] = {category: 0 for category in CATEGORY_CAP}
    capped_candidates: list[tuple[OptionalCandidate, OptionalDecision]] = []

    for candidate, decision in candidate_decisions:
        max_allowed = CATEGORY_CAP.get(decision.category)
        if max_allowed is None:
            continue

        category_count = category_counts[decision.category]
        if category_count >= max_allowed:
            continue

        category_counts[decision.category] = category_count + 1
        capped_candidates.append((candidate, decision))

    return capped_candidates


def _contains_keyword(candidate_text: str, keywords: set[str]) -> bool:
    return any(keyword in candidate_text for keyword in keywords)


def _combined_context(candidate: OptionalCandidate) -> str:
    context_parts = [
        candidate.url,
        candidate.anchor_text or "",
        candidate.raw_context or "",
    ]
    return " ".join(context_parts).lower()


def _is_github_repository_link(parsed_url) -> bool:
    normalized_host = canonical_host(parsed_url.hostname or "")
    if normalized_host != "github.com":
        return False
    path_parts = [path_part for path_part in parsed_url.path.split("/") if path_part]
    return len(path_parts) >= 2
