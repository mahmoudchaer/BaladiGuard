import type { ValidatedLocation } from '@/services/contributions';

export type ReportDraft = {
  userId: string;
  description: string;
  addressText: string;
  location: ValidatedLocation | null;
  clientSubmissionId: string;
  imageObjectKey?: string;
  updatedAt: number;
};

const DB = 'baladiguard-citizen-web';
const STORE = 'report-drafts';
export const GUEST_DRAFT_USER_ID = 'guest';
const memory = new Map<string, ReportDraft>();

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB, 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE)) {
        request.result.createObjectStore(STORE, { keyPath: 'userId' });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export function newSubmissionId(): string {
  return (
    globalThis.crypto?.randomUUID?.() ?? `web-${Date.now()}-${Math.random().toString(16).slice(2)}`
  );
}

export async function loadDraft(userId: string): Promise<ReportDraft | null> {
  if (!('indexedDB' in globalThis)) return memory.get(userId) ?? null;
  try {
    const db = await openDb();
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE);
      const request = transaction.objectStore(STORE).get(userId);
      request.onsuccess = () => resolve((request.result as ReportDraft | undefined) ?? null);
      request.onerror = () => reject(request.error);
      transaction.oncomplete = () => db.close();
    });
  } catch {
    return memory.get(userId) ?? null;
  }
}

export async function saveDraft(draft: ReportDraft): Promise<void> {
  memory.set(draft.userId, draft);
  if (!('indexedDB' in globalThis)) return;
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE, 'readwrite');
      transaction.objectStore(STORE).put(draft);
      transaction.oncomplete = () => {
        db.close();
        resolve();
      };
      transaction.onerror = () => {
        db.close();
        reject(transaction.error);
      };
    });
  } catch {
    // The in-memory copy still protects the draft for this tab when IndexedDB is unavailable.
  }
}

export async function clearDraft(userId: string): Promise<void> {
  memory.delete(userId);
  if (!('indexedDB' in globalThis)) return;
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE, 'readwrite');
      transaction.objectStore(STORE).delete(userId);
      transaction.oncomplete = () => {
        db.close();
        resolve();
      };
      transaction.onerror = () => {
        db.close();
        reject(transaction.error);
      };
    });
  } catch {
    // Memory was cleared above; an unavailable browser database must not block sign-out/discard.
  }
}
