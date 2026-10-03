from food_recommender.domain.evidence import Citation, CitationKind
from food_recommender.domain.values import Category, EntityRef
from food_recommender.retrieval.fusion import fuse
from food_recommender.retrieval.models import TextHit


def hit(entity_id, doc, *, category=Category.RESTAURANT, lexical=1.0, cosine=None):
    ref = EntityRef(category, entity_id)
    citation = Citation(
        doc, CitationKind.CATALOG, "source", "excerpt", ref, "record", doc
    )
    return TextHit(ref, entity_id, citation, lexical, cosine, None, None, "restaurant")


def test_duplicates_do_not_reward_entity_and_ties_are_stable():
    a, b = hit("a", "a1"), hit("b", "b1")
    first = fuse((a, b), (b, a), 20)
    repeated = fuse((a, hit("a", "a2"), b), (b, a), 20)
    assert [(c.evidence.entity.id, c.rrf_score) for c in first] == [
        (c.evidence.entity.id, c.rrf_score) for c in repeated
    ]
    assert first[0].evidence.entity.id == "a"
    assert all(c.evidence.relevance == 1 for c in first)
    assert len(repeated[0].evidence.citations) == 2
    assert first[0].rrf_score == 0.5 / 61 + 0.5 / 62


def test_empty_single_and_limit_keep_original_scores():
    assert fuse((), (), 20) == ()
    result = fuse((hit("a", "a"), hit("b", "b")), (), 1)
    assert len(result) == 1 and result[0].evidence.relevance == 1
    assert result[0].lexical_score == 1
    assert result[0].cosine_similarity is None
