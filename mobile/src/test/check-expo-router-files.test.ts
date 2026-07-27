import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';

const { validateExpoRouterFiles } = require('../../scripts/check-expo-router-files');

const tempDirs: string[] = [];

afterEach(() => {
  for (const tempDir of tempDirs.splice(0)) {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

describe('validateExpoRouterFiles', () => {
  it('allows valid Expo Router layouts, screens, and special route files', () => {
    const appDir = createAppFixture({
      '_layout.tsx': 'export default function Layout() { return null; }',
      'index.tsx': 'export default function HomeScreen() { return null; }',
      'report/index.tsx': 'export default function ReportScreen() { return null; }',
      '+not-found.tsx': 'export const NotFoundScreen = () => null;',
      '.gitkeep': '',
    });

    expect(validateExpoRouterFiles(appDir)).toEqual([]);
  });

  it('allows named re-exports as default route exports', () => {
    const appDir = createAppFixture({
      'report/index.tsx': 'const ReportScreen = () => null; export { ReportScreen as default };',
    });

    expect(validateExpoRouterFiles(appDir)).toEqual([]);
  });

  it('rejects test files because Expo Router treats app files as routes', () => {
    const appDir = createAppFixture({
      'index.tsx': 'export default function HomeScreen() { return null; }',
      'index.test.tsx': "import { describe } from 'vitest';",
    });

    expect(validateExpoRouterFiles(appDir)).toEqual([
      expect.stringContaining('index.test.tsx: test/spec/story files are not valid inside app/'),
    ]);
  });

  it('rejects normal route files without a default export', () => {
    const appDir = createAppFixture({
      'report/index.tsx': 'export const ReportScreen = () => null;',
    });

    expect(validateExpoRouterFiles(appDir)).toEqual([
      expect.stringContaining('report/index.tsx: route files must export a React component'),
    ]);
  });

  it('does not count comments as default exports', () => {
    const appDir = createAppFixture({
      'report/index.tsx':
        '// export default function ReportScreen() { return null; }\nexport const ReportScreen = () => null;',
    });

    expect(validateExpoRouterFiles(appDir)).toEqual([
      expect.stringContaining('report/index.tsx: route files must export a React component'),
    ]);
  });

  it('rejects test and mock directories inside app', () => {
    const appDir = createAppFixture({
      'index.tsx': 'export default function HomeScreen() { return null; }',
      '__tests__/index.tsx': 'export default function TestRoute() { return null; }',
      'report/__mocks__/mock.tsx': 'export default function MockRoute() { return null; }',
    });

    const errors = validateExpoRouterFiles(appDir);

    expect(errors).toHaveLength(2);
    expect(errors).toEqual(
      expect.arrayContaining([
        expect.stringContaining(
          '__tests__/index.tsx: __tests__ directories are not valid inside app/',
        ),
        expect.stringContaining(
          'report/__mocks__/mock.tsx: __mocks__ directories are not valid inside app/',
        ),
      ]),
    );
  });

  it('rejects unsupported files inside route directories', () => {
    const appDir = createAppFixture({
      'index.tsx': 'export default function HomeScreen() { return null; }',
      'report/data.json': '{}',
    });

    expect(validateExpoRouterFiles(appDir)).toEqual([
      expect.stringContaining('report/data.json: unsupported file type in app/'),
    ]);
  });
});

function createAppFixture(files: Record<string, string>) {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'expo-router-check-'));
  const appDir = path.join(tempDir, 'app');
  tempDirs.push(tempDir);

  for (const [relativePath, contents] of Object.entries(files)) {
    const filePath = path.join(appDir, relativePath);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, contents);
  }

  return appDir;
}
