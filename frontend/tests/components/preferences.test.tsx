import { fireEvent, render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import { PreferencesPanel } from '../../src/features/preferences/preferences-panel';
test('retained hard restrictions stay visible and removal uses an explicit key', () => {
  const change = vi.fn();
  render(<PreferencesPanel saved={{ cuisines: [], flavors: [], constraints: [{ kind: 'allergen', value: 'peanut', strength: 'hard', origin: 'explicit' }] }} onChange={change} />);
  expect(screen.getByText('peanut (allergen, explicit)')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Remove peanut' }));
  expect(change).toHaveBeenCalledWith({ constraints: [], remove_constraints: [{ kind: 'allergen', value: 'peanut' }] });
});
