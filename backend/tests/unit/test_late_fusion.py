import pytest
from test_text_fusion import hit

from food_recommender.domain.values import Category
from food_recommender.retrieval.fusion import fuse
from food_recommender.retrieval.late_fusion import late_fuse
from food_recommender.retrieval.models import ImageHit


def image(identity, score, media=None, category=Category.RESTAURANT):
    text = hit(identity, f"image:{media or identity}", category=category)
    return ImageHit(
        text.entity,
        text.name,
        text.citation,
        media or identity,
        score,
        text.ingredients,
        text.allergens,
    )


def test_late_fusion_normalizes_modalities_and_retains_raw_components():
    text = fuse((hit("a", "text:a"), hit("b", "text:b")), (), 20)
    result = late_fuse(text, (image("a", 0.1), image("b", 0.9)), 20)
    assert [
        (c.evidence.entity.id, c.evidence.relevance) for c in result.candidates
    ] == [("a", 0.6), ("b", 0.4)]
    assert result.candidates[0].rrf_score == text[0].rrf_score
    assert result.candidates[1].image_cosine_similarity == 0.9
    assert result.candidates[0].evidence.text_score == 1
    assert result.candidates[0].evidence.image_score == 0
    assert len(result.candidates[0].evidence.citations) == 2


def test_maximum_image_evidence_per_entity_does_not_reward_duplicates():
    text = fuse((hit("a", "text:a"), hit("b", "text:b")), (), 20)
    images = (image("a", 0.2, "a1"), image("a", 0.8, "a2"), image("b", 0.9))
    first = late_fuse(text, images, 20)
    second = late_fuse(text, (*images, *images), 20)
    assert first == second
    assert first.candidates[0].image_cosine_similarity == 0.8
    assert first.candidates[0].media_ids == ("a1", "a2")


def test_equal_scores_ties_and_empty_modalities_are_explicit():
    assert late_fuse((), (), 20).candidates == ()
    result = late_fuse((), (image("b", 0.2), image("a", 0.2)), 20)
    assert [c.evidence.entity.id for c in result.candidates] == ["a", "b"]
    assert all(
        c.evidence.image_score == c.evidence.relevance == 1 for c in result.candidates
    )
    assert (result.text_weight, result.image_weight) == (0, 1)
    assert result.limitations
    text = fuse((hit("a", "text:a"),), (), 20)
    result = late_fuse(text, (), 20)
    assert (result.text_weight, result.image_weight) == (1, 0)
    assert result.candidates[0].evidence.relevance == 1
    assert (
        late_fuse(text, (image("b", 0.1),), 20).candidates[0].evidence.image_score == 0
    )


def test_weight_validation_disabled_branches_and_incompatible_duplicate_media():
    from food_recommender.retrieval.late_fusion import FusionWeights

    for weights in [(0, 0), (-1, 1), (float("nan"), 1), (float("inf"), 1)]:
        with pytest.raises(ValueError):
            FusionWeights(*weights)
    assert (
        late_fuse((), (image("a", 0.5),), 20, weights=FusionWeights(1, 0)).candidates
        == ()
    )
    with pytest.raises(ValueError, match="media"):
        late_fuse((), (image("a", 0.3, "same"), image("b", 0.3, "same")), 20)
    with pytest.raises(ValueError):
        late_fuse((), (image("a", float("nan")),), 20)


def test_duplicate_text_candidates_keep_maximum_score_and_all_citations():
    from dataclasses import replace

    text = fuse((hit("a", "t1"),), (), 20)[0]
    other = fuse((hit("a", "t2"),), (), 20)[0]
    result = late_fuse((text, replace(other, rrf_score=text.rrf_score / 2)), (), 20)
    assert result.candidates[0].rrf_score == text.rrf_score
    assert {c.id for c in result.candidates[0].evidence.citations} == {"t1", "t2"}
