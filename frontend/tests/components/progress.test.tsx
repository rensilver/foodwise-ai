import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import { StageProgress } from '../../src/features/chat/stage-progress';
test('parallel experts use actual activity and unavailable outcomes without percentages', () => {
  render(<StageProgress busy events={[{ event: 'progress', conversation_id: 'c', run_id: 'r', agent: 'nutrition_expert', activity: 'started' }, { event: 'progress', conversation_id: 'c', run_id: 'r', agent: 'food_style_expert', activity: 'started' }, { event: 'progress', conversation_id: 'c', run_id: 'r', agent: 'food_trend_analyst', activity: 'unavailable' }]} />);
  expect(screen.getByRole('status')).toHaveTextContent('Checking dietary evidence; Considering food style'); expect(screen.queryByText(/%/)).toBeNull();
});
