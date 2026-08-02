import React from 'react';

type HostProps = {
  children?: React.ReactNode;
  [key: string]: unknown;
};

const createHostComponent =
  (name: string) =>
  ({ children, ...props }: HostProps) =>
    React.createElement(name, props, children);

export const Button = createHostComponent('Button');
export const Pressable = createHostComponent('Pressable');
export const ScrollView = createHostComponent('ScrollView');
export const Text = createHostComponent('Text');
export const TextInput = createHostComponent('TextInput');
export const View = createHostComponent('View');
export const Image = createHostComponent('Image');
export const ActivityIndicator = createHostComponent('ActivityIndicator');

export const Platform = {
  OS: 'ios',
  select: (options: Record<string, unknown>) => options.ios ?? options.default,
};

export const StyleSheet = {
  create: <T extends Record<string, unknown>>(styles: T) => styles,
  flatten: (style: unknown) => style,
};

export const useColorScheme = () => 'light';
