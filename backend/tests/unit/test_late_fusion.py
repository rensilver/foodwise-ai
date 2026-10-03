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
