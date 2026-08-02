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

export function TextInput({ children, ...props }: HostProps) {
  return React.createElement('TextInput', props, children);
}

export function HelperText({ children, ...props }: HostProps) {
  return React.createElement('HelperText', props, children);
}

export function Banner({ children, visible = true, ...props }: HostProps & { visible?: boolean }) {
  return visible ? React.createElement('Banner', props, children) : null;
}

export function ActivityIndicator(props: HostProps) {
  return React.createElement('ActivityIndicator', props);
}

export function Chip({ children, ...props }: HostProps) {
  return React.createElement('Chip', props, children);
}

export function Switch(props: HostProps) {
  return React.createElement('Switch', props);
}

function CardRoot({ children, ...props }: HostProps) {
  return React.createElement('Card', props, children);
}

function CardContent({ children, ...props }: HostProps) {
  return React.createElement('Card.Content', props, children);
}

export const Card = Object.assign(CardRoot, {
  Content: CardContent,
});

export const MD3LightTheme = {
  colors: {},
};
