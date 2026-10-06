# Original course screenshot requirements

Reviewed on 2026-10-06 (America/Recife) by extracting the text of all 12 local
assignment PDFs with `pdftotext -layout`. Each explicit screenshot requirement
appears on PDF page 1. The
[source identity map](course_screenshot_map.json) records SHA-256 hashes of the
reviewed PDFs, original filenames and capture subjects. PDFs/notebooks remain
Git-ignored and must be restored separately on a clean checkout.

These are original course submission requirements, separate from the
[replacement-stack portfolio gallery](portfolio.md). No course screenshot is
claimed completed by P11-06. Do not rename the portfolio PNGs to these `.jpg`
filenames or present Next.js/OpenAI/PostgreSQL captures as the lab's required
code/output. Course grading acceptance and any replacement-stack exceptions
require the course's own rules or instructor confirmation; none is established
here. Preserved notebook outputs may contain historical failures and are not
new successful executions. Inspect and sanitize code, outputs, environment
views and terminal chrome before making any course capture.

| Original source (local PDF) | Required filename | Original required view | Relevant current implementation/evidence; course capture status |
| --- | --- | --- | --- |
| [01: structure restaurant data](<../../docs/01_Assignment Overview: Structure Unstructured Restaurant Data with an LLM.pdf>) | `M1L1_structure_for_loop.jpg` | Python implementation and task output. | [Validated extraction](../../backend/src/food_recommender/ingestion/extraction.py); original lab capture still separate. |
| [02: multimodal preprocessing](<../../docs/02_Assignment Overview_ Process Multimodal Data with LLMs.pdf>) | `M1L2_caption_all_recipes.jpg` | Python implementation and task output. | [Caption provenance](../../backend/src/food_recommender/ingestion/captions.py) and [media/import evidence](../phase3/README.md); imported captions do not prove fresh vision generation. Original lab capture still separate. |
| [03: CLI data management](<../../docs/03_Assignment Overview_ Build a Command-Line Data Management UI for Restaurant Data.pdf>) | `M1L3_new_data_entry_process.jpg` | Function implementation. | [Admin use cases](../../backend/src/food_recommender/application/catalog/admin.py) and [P11-05 evidence](README.md#p11-05--administrator-preview-searchable-crud-and-recovery); browser preview is separate from the requested function capture. |
| [04: multimodal index](<../../docs/04_Assignment Overview_ Construct a Multimodal Vector Index.pdf>) | `M2L1_multimodal_vector_index.jpg` | Final code cell and its output. | [Text indexing](../../backend/src/food_recommender/infrastructure/persistence/indexing/text.py), [image indexing](../../backend/src/food_recommender/infrastructure/persistence/indexing/image.py) and [Phase 5 evidence](../phase5/README.md); pgvector evidence does not establish the original notebook/Chroma submission. |
| [05: similarity/metadata](<../../docs/05_Assignment Overview_ Similarity Retrieval with Metadata Filtering.pdf>) | `M2L2_similarity_retrieval.jpg` | Final code cell and its output. | [Retrieval service](../../backend/src/food_recommender/retrieval/service.py) and [Phase 4 evidence](../phase4/README.md); original lab capture still separate. |
| [06: multimodal fusion](<../../docs/06_Assignment Overview_ Multimodal Similarity Fusion and Retrieval Ranking.pdf>) | `M2L3_multimodal_fusion_results.jpg` | Final code cell and its output. | [Entity-level fusion](../../backend/src/food_recommender/retrieval/late_fusion.py) and [Phase 5 evidence](../phase5/README.md); original lab capture still separate. |
| [07: specialized agents](<../../docs/07_Assignment Overview_ Design Specialized Agents for a Recommendation System.pdf>) | `M3L1_food_style_expert_goal.jpg` | Python task implementation. | [Versioned prompts](../../backend/src/food_recommender/agents/prompts.py) and [style node](../../backend/src/food_recommender/agents/nodes/style.py); original lab goal capture still separate. |
| [08: agent orchestration](<../../docs/08_Assignment Overview_ Implement and Test a Multi-Agent Recommendation System.pdf>) | `M3L2_node_analyze_styles.jpg` | Python task implementation. | [Style node](../../backend/src/food_recommender/agents/nodes/style.py), [graph](../../backend/src/food_recommender/agents/graph.py) and [P11-04 evidence](README.md#p11-04--live-text-image-six-agent-and-follow-up-demonstration); original lab capture still separate. |
| [09: chatbot/preferences](<../../docs/09_Reading_ Assignment Overview_ Build a Chatbot Interface for the Recommendation System.pdf>) | `M3L3_preference_extraction_test.jpg` | Final code cell and its output. | [Profile rules](../../backend/src/food_recommender/application/recommendations/profile_rules.py) and gallery restriction scene; Next.js follow-ups do not establish the original notebook test submission. |
| [10: MCP server](<../../docs/10_Assignment Overview_ Build an MCP Server.pdf>) | `M4L1_Configure_Tools_Data_MCP_Server.jpg` | Successful search execution returning JSON. | [FastMCP server](../../backend/src/food_recommender/mcp/server.py) and [Phase 6 transport/tool evidence](../phase6/README.md); a source card is not the requested JSON execution screenshot. |
| [11: MCP client](<../../docs/11_Assignment Overview_ Build an MCP Client.pdf>) | `M4L2_Build_Test_MCP_Client.jpg` | Terminal discovery of tools, resources and project roots. | [Client discovery](../../backend/src/food_recommender/mcp/client.py) and [Phase 6 evidence](../phase6/README.md); advisory roots and legacy sampling are reassessed in the new runtime. The original terminal capture remains separate. |
| [12: full MCP application](<../../docs/12_Assignment Overview_ Build a Full MCP Application.pdf>) | No screenshot filename specified in this PDF. | Runtime tool discovery/schema conversion, ReAct loop, Gradio chat/placeholder/examples, single-command execution are listed as deliverables. | [P11-04](../../infra/live-demo.md) and the portfolio show the replacement FastAPI/Next.js/OpenAI stack. No equivalence to the original WatsonX/Gradio deliverables or unprovided final rubric is claimed. |

The map covers only the supplied overview PDFs. It does not infer additional
screenshots from unprovided lab steps, a final-project rubric or notebook cell
names. Existing course artifacts and their historical status remain unchanged.
