"""Observable domain invariants and JSON contracts, without service dependencies."""

import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from food_recommender.application.contracts import (
    contract_json_schema,
    event_adapter,
    nutrition_outcome_adapter,
    profile_adapter,
    profile_outcome_adapter,
    recommendation_outcome_adapter,
    retrieval_outcome_adapter,
    style_outcome_adapter,
    trend_outcome_adapter,
)
from food_recommender.domain.events import (
    ClarificationEvent,
    DoneEvent,
    ErrorEvent,
    ProgressEvent,
    RecommendationsEvent,
)
from food_recommender.domain.evidence import CandidateEvidence, Citation, CitationKind
from food_recommender.domain.experts import (
    AgentFailure,
    AgentSuccess,
    AgentUnavailable,
    NutritionAnalysis,
    NutritionAssessment,
    ProfileResult,
    RetrievalResult,
    StyleAnalysis,
    StyleAssessment,
    TrendAnalysis,
    TrendClaim,
)
from food_recommender.domain.preferences import Constraint, Preferences
from food_recommender.domain.recommendations import (
    Recommendation,
    RecommendationResult,
    validate_recommendations,
)
from food_recommender.domain.values import (
    AgentRole,
    Category,
    ConstraintKind,
    EntityRef,
    EvidenceState,
    Origin,
    Strength,
)

IDENTIFIER = UUID("11111111-1111-4111-8111-111111111111")
RECIPE = EntityRef(Category.RECIPE, "1")
RESTAURANT = EntityRef(Category.RESTAURANT, "1")


def citation(entity=RECIPE, identity="citation-1"):
    return Citation(
        id=identity,
        kind=CitationKind.CATALOG,
        source_id="course-recipes",
        excerpt="Ingredients: rice, peanuts.",
        entity=entity,
        record_id="1",
        document_id="document-1",
        retrieved_at=datetime(2026, 10, 3, tzinfo=UTC),
    )


def candidate(entity=RECIPE, identity="citation-1"):
    return CandidateEvidence(
        entity=entity,
        citations=(citation(entity, identity),),
        relevance=0.8,
        text_score=0.8,
        image_score=None,
    )


def recommendation(entity=RECIPE, identity="citation-1"):
    return Recommendation(
        entity, "Source-backed explanation.", (identity,), ("Unknown nutrients.",)
    )


def test_preferences_distinguish_unknown_empty_soft_and_explicit_hard():
    soft = Constraint(
        ConstraintKind.DIETARY, "plant-based", Strength.SOFT, Origin.INFERRED
    )
    hard = Constraint(ConstraintKind.ALLERGEN, "peanut", Strength.HARD, Origin.EXPLICIT)
    preferences = Preferences(constraints=(soft, hard))
    assert preferences.location is None and preferences.price_band is None
    assert preferences.constraints == (soft, hard)
    assert Preferences().constraints == ()
    with pytest.raises(ValueError, match="explicit"):
        replace(hard, origin=Origin.INFERRED)
    with pytest.raises(FrozenInstanceError):
        preferences.location = "California"
    with pytest.raises(ValueError):
        Preferences(price_band=0)


def test_profile_roundtrip_preserves_origins_and_restrictions():
    profile = ProfileResult(
        categories=(Category.RECIPE, Category.RESTAURANT),
        preferences=Preferences(
            constraints=(
                Constraint(
                    ConstraintKind.ALLERGEN, "peanut", Strength.HARD, Origin.EXPLICIT
                ),
            )
        ),
        clarification=None,
    )
    payload = profile_adapter.dump_json(profile)
    assert profile_adapter.validate_json(payload) == profile
    assert json.loads(payload)["preferences"]["constraints"][0]["origin"] == "explicit"
    assert (
        contract_json_schema(profile_adapter)["$defs"]["Constraint"][
            "additionalProperties"
        ]
        is False
    )
    raw = json.loads(payload)
    raw["preferences"]["constraints"][0]["origin"] = "inferred"
    with pytest.raises(ValidationError):
        profile_adapter.validate_json(json.dumps(raw))
    raw["preferences"]["constraints"][0]["origin"] = "explicit"
    raw["preferences"]["arbitrary_tool"] = "shell"
    with pytest.raises(ValidationError):
        profile_adapter.validate_json(json.dumps(raw))


def test_identity_and_evidence_are_source_backed_and_category_scoped():
    assert RECIPE != RESTAURANT
    assert citation().published_on is None
    assert citation().attribution == "imported"
    assert candidate().image_score is None
    with pytest.raises(ValueError):
        EntityRef(Category.RECIPE, " ")
    for change in (
        {"excerpt": " "},
        {"document_id": None},
        {"entity": None},
        {"retrieved_at": datetime(2026, 10, 3)},
    ):
        with pytest.raises(ValueError):
            replace(citation(), **change)
    with pytest.raises(ValueError, match="entity"):
        replace(candidate(), citations=(citation(RESTAURANT),))
    for score in (-0.01, 1.01, float("nan"), float("inf"), True):
        with pytest.raises(ValueError):
            replace(candidate(), relevance=score)


def test_trend_claim_requires_publication_date_and_actual_web_evidence():
    web = Citation(
        "trend-1",
        CitationKind.WEB,
        "tavily",
        "Regional interest in rice dishes.",
        url="https://example.org/food",
        retrieved_at=datetime(2026, 10, 3, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="publication"):
        TrendClaim("Rice dishes are trending.", (RECIPE,), (web,))
    dated = replace(web, published_on=date(2026, 9, 20))
    assert TrendAnalysis(
        (TrendClaim("Rice dishes are trending.", (RECIPE,), (dated,)),)
    ).claims
    with pytest.raises(ValueError):
        replace(web, url="file:///etc/passwd")
    with pytest.raises(ValueError):
        TrendClaim("Claim", (RECIPE,), (citation(),))


def test_expert_outcomes_preserve_failure_unavailable_empty_and_unknown():
    assert len(AgentRole) == 6
    empty = AgentSuccess(RetrievalResult((), attempts=1))
    unavailable = AgentUnavailable("trends_unavailable")
    failure = AgentFailure("dependency_unavailable", retryable=True)
    assert empty.status == "success"
    assert unavailable.status == "unavailable" and failure.status == "failure"
    unknown = NutritionAssessment(
        RECIPE, EvidenceState.UNKNOWN, (), ("Ingredients incomplete.",)
    )
    assert NutritionAnalysis((unknown,)).assessments[0].state == EvidenceState.UNKNOWN
    assert StyleAnalysis(
        (
            StyleAssessment(
                RECIPE, EvidenceState.UNKNOWN, (), (), ("Style evidence unavailable.",)
            ),
        )
    ).assessments
    with pytest.raises(ValueError):
        NutritionAssessment(RECIPE, EvidenceState.SUPPORTED, (), ())
    with pytest.raises(ValueError):
        StyleAssessment(RECIPE, EvidenceState.SUPPORTED, (), ("Spicy.",))
    with pytest.raises(ValueError):
        StyleAssessment(RECIPE, EvidenceState.UNKNOWN, (), ("Spicy.",))


@pytest.mark.parametrize(
    "adapter,result",
    [
        (profile_outcome_adapter, ProfileResult((Category.RECIPE,), Preferences())),
        (retrieval_outcome_adapter, RetrievalResult((candidate(),), 1)),
        (trend_outcome_adapter, TrendAnalysis(())),
        (
            style_outcome_adapter,
            StyleAnalysis(
                (
                    StyleAssessment(
                        RECIPE,
                        EvidenceState.SUPPORTED,
                        ("citation-1",),
                        ("Peanut flavor.",),
                    ),
                )
            ),
        ),
        (
            nutrition_outcome_adapter,
            NutritionAnalysis(
                (
                    NutritionAssessment(
                        RECIPE, EvidenceState.UNKNOWN, (), ("Unknown compliance.",)
                    ),
                )
            ),
        ),
        (recommendation_outcome_adapter, RecommendationResult((recommendation(),))),
    ],
)
def test_every_agent_result_roundtrips_with_explicit_outcome(adapter, result):
    for outcome in (
        AgentSuccess(result),
        AgentFailure("invalid_response"),
        AgentUnavailable("trends_unavailable"),
    ):
        encoded = adapter.dump_json(outcome)
        assert adapter.validate_json(encoded) == outcome
        assert (
            contract_json_schema(adapter)["discriminator"]["propertyName"] == "status"
        )
    raw = json.loads(adapter.dump_json(AgentFailure("invalid_response")))
    raw["status"] = "success"
    with pytest.raises(ValidationError):
        adapter.validate_json(json.dumps(raw))


def test_strict_json_rejects_coercion_and_nested_untrusted_arguments():
    raw = json.loads(
        profile_adapter.dump_json(ProfileResult((Category.RECIPE,), Preferences()))
    )
    for price in ("2", True, 2.5):
        raw["preferences"]["price_band"] = price
        with pytest.raises(ValidationError):
            profile_adapter.validate_json(json.dumps(raw))
    encoded = json.loads(
        retrieval_outcome_adapter.dump_json(
            AgentSuccess(RetrievalResult((candidate(),), 1))
        )
    )
    encoded["result"]["candidates"][0]["citations"][0]["shell_command"] = "untrusted"
    with pytest.raises(ValidationError):
        retrieval_outcome_adapter.validate_json(json.dumps(encoded))


def test_exact_result_limits_and_cross_entity_citation_rejection():
    candidates = tuple(
        candidate(EntityRef(category, str(i)), f"{category}-{i}")
        for category in Category
        for i in range(20)
    )
    assert len(RetrievalResult(candidates, 3).candidates) == 40
    result = RecommendationResult(
        tuple(
            recommendation(EntityRef(category, str(i)), f"{category}-{i}")
            for category in Category
            for i in range(5)
        )
    )
    validate_recommendations(result, candidates)
    with pytest.raises(ValueError, match="citation"):
        validate_recommendations(
            RecommendationResult((recommendation(RECIPE, "restaurant-1"),)), candidates
        )


def test_retrieval_and_result_bounds_deduplicate_with_separate_namespaces():
    assert (
        len(
            RetrievalResult(
                (candidate(), candidate(RESTAURANT, "citation-2")), 1
            ).candidates
        )
        == 2
    )
    with pytest.raises(ValueError):
        RetrievalResult((candidate(), candidate()), 1)
    for attempts in (0, 4):
        with pytest.raises(ValueError):
            RetrievalResult((), attempts)
    with pytest.raises(ValueError):
        RetrievalResult(
            tuple(
                candidate(EntityRef(Category.RECIPE, str(i)), f"cite-{i}")
                for i in range(21)
            ),
            1,
        )
    with pytest.raises(ValueError):
        RecommendationResult((recommendation(), recommendation()))
    with pytest.raises(ValueError):
        RecommendationResult(
            tuple(
                recommendation(EntityRef(Category.RECIPE, str(i)), f"cite-{i}")
                for i in range(6)
            )
        )
    assert RecommendationResult((), ("Insufficient evidence.",)).recommendations == ()


def test_synthesis_validation_rejects_invented_ids_citations_and_unsafe_results():
    result = RecommendationResult((recommendation(),))
    validate_recommendations(result, (candidate(),))
    with pytest.raises(ValueError, match="candidate"):
        validate_recommendations(result, (candidate(RESTAURANT),))
    with pytest.raises(ValueError, match="citation"):
        validate_recommendations(result, (candidate(identity="other"),))
    for state in (EvidenceState.UNKNOWN, EvidenceState.CONFLICTING):
        assessment = NutritionAnalysis(
            (
                NutritionAssessment(
                    RECIPE, state, ("citation-1",), ("Restriction unresolved.",)
                ),
            )
        )
        with pytest.raises(ValueError, match="restriction"):
            validate_recommendations(
                result, (candidate(),), nutrition=assessment, hard_constraints=True
            )
    with pytest.raises(ValueError, match="restriction"):
        validate_recommendations(result, (candidate(),), hard_constraints=True)
    supported = NutritionAnalysis(
        (NutritionAssessment(RECIPE, EvidenceState.SUPPORTED, ("citation-1",), ()),)
    )
    validate_recommendations(
        result, (candidate(),), nutrition=supported, hard_constraints=True
    )
    conflicting = replace(
        supported,
        assessments=(
            replace(supported.assessments[0], state=EvidenceState.CONFLICTING),
        ),
    )
    with pytest.raises(ValueError):
        validate_recommendations(result, (candidate(),), nutrition=conflicting)


@pytest.mark.parametrize(
    "event",
    [
        ProgressEvent(IDENTIFIER, IDENTIFIER, AgentRole.RAG_RETRIEVER, "started"),
        ClarificationEvent(IDENTIFIER, IDENTIFIER, "Which city?"),
        RecommendationsEvent(
            IDENTIFIER, IDENTIFIER, RecommendationResult((recommendation(),))
        ),
        ErrorEvent(IDENTIFIER, IDENTIFIER, "dependency_unavailable", True),
        DoneEvent(IDENTIFIER, IDENTIFIER, "completed"),
    ],
)
def test_all_five_events_have_discriminated_roundtrip_and_schema(event):
    encoded = event_adapter.dump_json(event)
    assert event_adapter.validate_json(encoded) == event
    assert json.loads(encoded)["conversation_id"] == str(IDENTIFIER)
    assert event_adapter.json_schema()["discriminator"]["propertyName"] == "event"
    raw = json.loads(encoded)
    raw["event"] = "chain_of_thought"
    with pytest.raises(ValidationError):
        event_adapter.validate_json(json.dumps(raw))


def test_event_validation_rejects_unknown_fields_and_free_form_failures():
    raw = json.loads(
        event_adapter.dump_json(
            ErrorEvent(IDENTIFIER, IDENTIFIER, "internal_error", False)
        )
    )
    raw["stack_trace"] = "private"
    with pytest.raises(ValidationError):
        event_adapter.validate_json(json.dumps(raw))
    del raw["stack_trace"]
    raw["code"] = "provider credential details"
    with pytest.raises(ValidationError):
        event_adapter.validate_json(json.dumps(raw))
