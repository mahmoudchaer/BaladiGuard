import path from 'node:path';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  esbuild: {
    jsxInject: "import React from 'react';",
  },
  test: {
    environment: 'node',
    setupFiles: ['./src/test/setup.ts'],
  },
  resolve: {
    alias: [
      { find: '@', replacement: path.resolve(__dirname, './src') },
      {
        find: /^expo-router$/,
        replacement: path.resolve(__dirname, './src/test/mocks/expo-router.tsx'),
      },
      {
        find: /^expo-status-bar$/,
        replacement: path.resolve(__dirname, './src/test/mocks/expo-status-bar.tsx'),
      },
      {
        find: /^react-native(\/.*)?$/,
        replacement: path.resolve(__dirname, './src/test/mocks/react-native-host.tsx'),
      },
      {
        find: /^react-native-safe-area-context$/,
        replacement: path.resolve(__dirname, './src/test/mocks/react-native-safe-area-context.tsx'),
      },
      {
        find: /^react-native-paper$/,
        replacement: path.resolve(__dirname, './src/test/mocks/react-native-paper.tsx'),
      },
      {
        find: /^expo-secure-store$/,
        replacement: path.resolve(__dirname, './src/test/mocks/expo-secure-store.ts'),
      },
      {
        find: /^expo-constants$/,
        replacement: path.resolve(__dirname, './src/test/mocks/expo-constants.ts'),
      },
    ],
  },
});
