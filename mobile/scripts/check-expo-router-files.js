#!/usr/bin/env node

const fs = require('node:fs');
const path = require('node:path');

const ROUTE_EXTENSIONS = new Set(['.js', '.jsx', '.ts', '.tsx']);
const IGNORED_FILENAMES = new Set(['.gitkeep', '.DS_Store']);
const SPECIAL_ROUTE_FILES = new Set(['+html', '+native-intent', '+not-found', '+middleware']);
const INVALID_ROUTE_FILE_PATTERNS = [
  /\.test\.[jt]sx?$/i,
  /\.spec\.[jt]sx?$/i,
  /\.stories\.[jt]sx?$/i,
  /\.story\.[jt]sx?$/i,
];
const INVALID_ROUTE_DIR_NAMES = new Set(['__tests__', '__mocks__', '__fixtures__']);

function validateExpoRouterFiles(appDir = path.join(process.cwd(), 'app')) {
  const errors = [];

  if (!fs.existsSync(appDir)) {
    return [`Expo Router app directory does not exist: ${appDir}`];
  }

  for (const filePath of walkFiles(appDir)) {
    const relativePath = path.relative(appDir, filePath).split(path.sep).join('/');
    const filename = path.basename(filePath);

    if (IGNORED_FILENAMES.has(filename)) {
      continue;
    }

    const directoryParts = path.dirname(relativePath).split('/').filter(Boolean);
    const invalidDirectory = directoryParts.find((part) => INVALID_ROUTE_DIR_NAMES.has(part));
    if (invalidDirectory) {
      errors.push(
        `${relativePath}: ${invalidDirectory} directories are not valid inside app/. Move tests, mocks, and fixtures to src/test or another non-route directory.`,
      );
      continue;
    }

    if (INVALID_ROUTE_FILE_PATTERNS.some((pattern) => pattern.test(filename))) {
      errors.push(
        `${relativePath}: test/spec/story files are not valid inside app/. Expo Router treats files in app/ as routes; move this file to src/test or another non-route directory.`,
      );
      continue;
    }

    const extension = path.extname(filename);
    if (!ROUTE_EXTENSIONS.has(extension)) {
      errors.push(
        `${relativePath}: unsupported file type in app/. Keep assets, tests, mocks, and fixtures outside Expo Router route directories.`,
      );
      continue;
    }

    const routeName = filename.slice(0, -extension.length);
    if (isSpecialRouteFile(routeName)) {
      continue;
    }

    const contents = fs.readFileSync(filePath, 'utf8');
    if (!hasDefaultExport(contents)) {
      errors.push(
        `${relativePath}: route files must export a React component as the default export. Add "export default ..." or move non-route code outside app/.`,
      );
    }
  }

  return errors;
}

function walkFiles(directory) {
  const entries = fs.readdirSync(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkFiles(entryPath));
    } else if (entry.isFile()) {
      files.push(entryPath);
    }
  }

  return files;
}

function isSpecialRouteFile(routeName) {
  return SPECIAL_ROUTE_FILES.has(routeName);
}

function hasDefaultExport(contents) {
  return /\bexport\s+default\b/.test(contents);
}

if (require.main === module) {
  const appDir = process.argv[2] ? path.resolve(process.argv[2]) : path.join(process.cwd(), 'app');
  const errors = validateExpoRouterFiles(appDir);

  if (errors.length > 0) {
    console.error('Invalid Expo Router files found:');
    for (const error of errors) {
      console.error(`- ${error}`);
    }
    process.exit(1);
  }

  console.log('Expo Router file check passed.');
}

module.exports = {
  validateExpoRouterFiles,
};
