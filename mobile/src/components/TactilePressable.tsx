import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
  AccessibilityInfo,
  Animated,
  Pressable,
  type PressableProps,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

type TactilePressableProps = Omit<PressableProps, 'children' | 'style'> & {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  pressedScale?: number;
};

/** Immediate, subtle physical feedback without delaying the underlying action. */
export function TactilePressable({
  children,
  style,
  pressedScale = 0.975,
  onPressIn,
  onPressOut,
  ...props
}: TactilePressableProps) {
  const scale = useRef(new Animated.Value(1)).current;
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    void AccessibilityInfo.isReduceMotionEnabled().then(setReduceMotion);
    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduceMotion);
    return () => subscription.remove();
  }, []);

  const moveTo = (value: number) => {
    scale.stopAnimation();
    if (reduceMotion) {
      scale.setValue(value);
      return;
    }
    Animated.spring(scale, {
      toValue: value,
      stiffness: 420,
      damping: 32,
      mass: 0.7,
      useNativeDriver: true,
    }).start();
  };

  return (
    <Pressable
      {...props}
      onPressIn={(event) => {
        moveTo(pressedScale);
        onPressIn?.(event);
      }}
      onPressOut={(event) => {
        moveTo(1);
        onPressOut?.(event);
      }}
    >
      <Animated.View style={[style, { transform: [{ scale }] }]}>{children}</Animated.View>
    </Pressable>
  );
}
