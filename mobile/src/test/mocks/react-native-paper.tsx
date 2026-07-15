import React from 'react';

type HostProps = {
  children?: React.ReactNode;
  [key: string]: unknown;
};

export function PaperProvider({ children }: { children: React.ReactNode }) {
  return children;
}

export function Text({ children, ...props }: HostProps) {
  return React.createElement('Text', props, children);
}

export function Button({ children, ...props }: HostProps) {
  return React.createElement('Button', props, children);
}

export const MD3LightTheme = {
  colors: {},
};
