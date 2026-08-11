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
export const FlatList = ({
  data = [],
  renderItem,
  keyExtractor,
  ListEmptyComponent,
  children,
  ...props
}: HostProps & {
  data?: unknown[];
  renderItem?: (info: { item: unknown; index: number }) => React.ReactNode;
  keyExtractor?: (item: unknown, index: number) => string;
  ListEmptyComponent?: React.ReactNode | (() => React.ReactNode);
}) => {
  const items = Array.isArray(data) ? data : [];
  const empty =
    typeof ListEmptyComponent === 'function' ? ListEmptyComponent() : ListEmptyComponent;
  return React.createElement(
    'FlatList',
    props,
    items.length === 0
      ? empty
      : items.map((item, index) => {
          const key = keyExtractor ? keyExtractor(item, index) : String(index);
          return React.createElement(
            React.Fragment,
            { key },
            renderItem ? renderItem({ item, index }) : null,
          );
        }),
    children,
  );
};
export const Text = createHostComponent('Text');
export const TextInput = createHostComponent('TextInput');
export const View = createHostComponent('View');
export const KeyboardAvoidingView = createHostComponent('KeyboardAvoidingView');
// Keep Image as a function component (not a host string) so event props like
// onError are preserved under react-test-renderer / React 19.
export function Image({ children, ...props }: HostProps) {
  return React.createElement('RNImage', props, children);
}
export const ActivityIndicator = createHostComponent('ActivityIndicator');
export const RefreshControl = createHostComponent('RefreshControl');
// Function component (same idea as Image) so we do not collide with any ambient Modal types.
export function Modal({
  children,
  visible = true,
  ...props
}: HostProps & { visible?: boolean }) {
  if (!visible) {
    return null;
  }
  return React.createElement('RNModal', { visible, ...props }, children);
}

export const Alert = {
  alert: (
    _title: string,
    _message?: string,
    buttons?: Array<{ text?: string; onPress?: () => void; style?: string }>,
  ) => {
    // Auto-confirm the last non-cancel action in tests when present.
    const action =
      buttons?.find((button) => button.style === 'destructive') ?? buttons?.[buttons.length - 1];
    action?.onPress?.();
  },
};

export const Platform = {
  OS: 'ios',
  select: (options: Record<string, unknown>) => options.ios ?? options.default,
};

export const useWindowDimensions = () => ({ width: 390, height: 844, scale: 2, fontScale: 1 });

export const StyleSheet = {
  create: <T extends Record<string, unknown>>(styles: T) => styles,
  flatten: (style: unknown) => style,
};

export const useColorScheme = () => 'light';
