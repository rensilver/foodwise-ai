import type { Schema } from "../../src/lib/api/client";
export const citation: Schema["Citation"] = {
  id: "doc-rice",
  kind: "catalog",
  source_id: "fixture-source",
  excerpt: "Rice with tomato and basil.",
  entity: { category: "recipe", id: "rice" },
  record_id: "rice",
  document_id: "doc-rice",
  attribution: "source",
};
export const rice: Schema["CatalogDetail"] = {
  data: {
    id: "rice",
    name: "Tomato rice",
    source_id: "fixture",
    source_record_id: "rice",
    ingredients: ["rice", "tomato", "basil"],
    directions: ["Simmer rice with tomato."],
    total_time: "30 mins",
  },
  version: 1,
  citations: [citation],
  synthetic: true,
  images: [
    {
      id: "rice-image",
      mime_type: "image/png",
      byte_size: 100,
      width: 2,
      height: 2,
    },
  ],
};
export const recommendations: Schema["RecommendationsEvent"] = {
  event: "recommendations",
  conversation_id: "11111111-1111-4111-8111-111111111111",
  run_id: "22222222-2222-4222-8222-222222222222",
  result: {
    recommendations: [
      {
        entity: citation.entity!,
        explanation: "Rice with tomato and basil.",
        citation_ids: ["doc-rice"],
        limitations: [],
      },
    ],
    limitations: [],
  },
  evidence: [
    {
      entity: citation.entity!,
      relevance: 0.8,
      citations: [citation],
      limitations: [],
    },
  ],
  trend: { status: "unavailable", code: "trends_unavailable" },
  nutrition: {
    status: "success",
    result: {
      assessments: [
        {
          entity: citation.entity!,
          state: "unknown",
          citation_ids: [],
          limitations: ["Cross-contact is not verified."],
        },
      ],
    },
  },
};
