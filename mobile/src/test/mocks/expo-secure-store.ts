const store = new Map<string, string>();
let error: Error | null = null;

export async function getItemAsync(key: string): Promise<string | null> {
  if (error) throw error;
  return store.has(key) ? (store.get(key) as string) : null;
}

export async function setItemAsync(key: string, value: string): Promise<void> {
  if (error) throw error;
  store.set(key, value);
}

export async function deleteItemAsync(key: string): Promise<void> {
  if (error) throw error;
  store.delete(key);
}

export function __resetSecureStoreMock() {
  store.clear();
  error = null;
}

export function __setSecureStoreError(next: Error | null) {
  error = next;
}

export function __getSecureStoreMock() {
  return store;
}
