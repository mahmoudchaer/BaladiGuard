/**
 * Lightweight expo-file-system stand-in for Vitest.
 * Avoids loading expo-modules-core (native EventEmitter) in Node.
 */

export type FileInfo = {
  exists: boolean;
  uri?: string;
  size?: number;
  isDirectory?: boolean;
  modificationTime?: number;
};

type InfoResolver = (fileUri: string) => Promise<FileInfo> | FileInfo;

const defaultResolver: InfoResolver = async () => ({ exists: false });
let resolver: InfoResolver = defaultResolver;

export async function getInfoAsync(fileUri: string): Promise<FileInfo> {
  return resolver(fileUri);
}

export function __setFileInfoResolver(next: InfoResolver | null): void {
  resolver = next ?? defaultResolver;
}

export function __resetFileSystemMock(): void {
  resolver = defaultResolver;
}
