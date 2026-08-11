/**
 * Lightweight expo-file-system (SDK 54 File API) stand-in for Vitest.
 * Avoids loading expo-modules-core (native EventEmitter) in Node.
 */

type ExistsResolver = (fileUri: string) => boolean;

const defaultResolver: ExistsResolver = () => false;
let existsResolver: ExistsResolver = defaultResolver;

/**
 * Minimal File mock matching the SDK 54 public shape used by photoReference.
 */
export class File {
  readonly uri: string;

  constructor(...uris: (string | File)[]) {
    const parts = uris.map((part) => (typeof part === 'string' ? part : part.uri));
    this.uri = parts.length === 1 ? parts[0]! : parts.join('/');
  }

  get exists(): boolean {
    return existsResolver(this.uri);
  }
}

export function __setFileExistsResolver(next: ExistsResolver | null): void {
  existsResolver = next ?? defaultResolver;
}

/** Make constructing / reading File throw (native-unavailable scenarios). */
export function __setFileExistsThrows(error: Error | null): void {
  if (!error) {
    existsResolver = defaultResolver;
    return;
  }
  existsResolver = () => {
    throw error;
  };
}

export function __resetFileSystemMock(): void {
  existsResolver = defaultResolver;
}
