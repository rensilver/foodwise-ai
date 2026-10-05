import type { Schema, StreamEvent } from '../../lib/api/client';
const labels: Record<Schema['AgentRole'], string> = { user_profile_generator: 'Understanding your request', rag_retriever: 'Finding options', food_trend_analyst: 'Checking current trends', food_style_expert: 'Considering food style', nutrition_expert: 'Checking dietary evidence', recommendation_expert: 'Preparing recommendations' };
export function StageProgress({ events, busy }: { events: StreamEvent[]; busy: boolean }) {
  const stages = new Map<Schema['AgentRole'], Schema['ProgressEvent']>();
  for (const event of events) if (event.event === 'progress') stages.set(event.agent, event);
  if (!stages.size && !busy) return null;
  const active = [...stages.values()].filter((event) => event.activity === 'started');
  return <section aria-label="Request activity"><p role="status" aria-live="polite">{busy ? active.length ? active.map((e) => labels[e.agent]).join('; ') : 'Waiting for the next activity update…' : 'Request activity ended.'}</p><details><summary>Activity details</summary><ul>{[...stages.values()].map((event) => <li key={event.agent}>{labels[event.agent]}: {event.activity}</li>)}</ul></details></section>;
}
