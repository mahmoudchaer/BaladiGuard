import { describe, expect, it } from 'vitest';
import { clearDraft, loadDraft, newSubmissionId, saveDraft } from '@/services/reportDraft';

describe('account-scoped report drafts', () => {
  it('saves, restores, and clears a draft without persistent browser storage', async () => {
    const userId = `user-${newSubmissionId()}`;
    const draft = {
      userId,
      description: 'A damaged sidewalk blocks wheelchair access.',
      addressText: 'Hamra, Beirut',
      location: {
        latitude: 33.896,
        longitude: 35.478,
        addressText: 'Hamra, Beirut',
        source: 'MANUAL' as const,
      },
      clientSubmissionId: newSubmissionId(),
      updatedAt: Date.now(),
    };

    await saveDraft(draft);
    await expect(loadDraft(userId)).resolves.toEqual(draft);

    await clearDraft(userId);
    await expect(loadDraft(userId)).resolves.toBeNull();
  });

  it('creates a distinct idempotency key for each new submission', () => {
    expect(newSubmissionId()).not.toBe(newSubmissionId());
  });
});
