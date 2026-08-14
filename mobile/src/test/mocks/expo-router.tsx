import type { ReactNode } from 'react';
import { createElement, useState } from 'react';

type HrefValue = string | { pathname?: string; params?: Record<string, unknown> };

const routerState = {
  replaceCalls: [] as HrefValue[],
  pushCalls: [] as HrefValue[],
  searchParams: {} as Record<string, string | string[] | undefined>,
  canGoBack: true,
};

export function __resetExpoRouterMock() {
  routerState.replaceCalls = [];
  routerState.pushCalls = [];
  routerState.searchParams = {};
}

export function __setSearchParams(params: Record<string, string | string[] | undefined>) {
  routerState.searchParams = params;
}

export function __getRouterMockState() {
  return routerState;
}

export function Link({ children }: { children: ReactNode }) {
  return children;
}

export function Tabs({ children, ...props }: { children: ReactNode; [key: string]: unknown }) {
  return createElement('Tabs', props, children);
}

Tabs.Screen = function TabsScreen(props: Record<string, unknown>) {
  return createElement('TabsScreen', props);
};

export function Stack({ children, ...props }: { children: ReactNode; [key: string]: unknown }) {
  return createElement('Stack', props, children);
}

Stack.Screen = function StackScreen(props: Record<string, unknown>) {
  return createElement('StackScreen', props);
};

export function Redirect({ href }: { href: HrefValue }) {
  routerState.replaceCalls.push(href);
  return null;
}

export function useRouter() {
  return {
    replace: (href: HrefValue) => {
      routerState.replaceCalls.push(href);
    },
    push: (href: HrefValue) => {
      routerState.pushCalls.push(href);
    },
    back: () => undefined,
    canGoBack: () => routerState.canGoBack,
  };
}

export function useLocalSearchParams<
  T extends Record<string, unknown> = Record<string, unknown>,
>() {
  return routerState.searchParams as T;
}

export type Href = string;
