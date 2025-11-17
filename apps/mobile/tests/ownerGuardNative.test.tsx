import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
const native = vi.hoisted(() => ({ onRequestClose: undefined as (() => void) | undefined }));
vi.mock('react-native', () => {
  const element = ({ children }: { children?: React.ReactNode }) => React.createElement('div', null, children);
  return {
    Platform: { OS: 'android', select: (v: Record<string, unknown>) => v.android ?? v.default },
    Modal: ({ children, onRequestClose }: { children?: React.ReactNode; onRequestClose: () => void }) => {
      native.onRequestClose = onRequestClose; return React.createElement('div', null, children);
    },
    KeyboardAvoidingView: element, ActivityIndicator: element, Pressable: element,
    ScrollView: element, Text: element, TextInput: element, View: element,
    StyleSheet: { create: (styles: unknown) => styles, hairlineWidth: 1 },
  };
});
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }: { children?: React.ReactNode }) => React.createElement('div', null, children) }));
vi.mock('lucide-react-native/icons/check', () => ({ default: () => null }));
vi.mock('lucide-react-native/icons/x', () => ({ default: () => null }));
import { Panel } from '../src/components/UI';

describe('native modal close adapter', () => {
  it('routes the hardware back request through the same close callback', () => {
    const onClose = vi.fn(); native.onRequestClose = undefined;
    renderToStaticMarkup(<Panel title="Editor" onClose={onClose}><span>Draft</span></Panel>);
    const callback = native.onRequestClose as (() => void) | undefined;
    expect(callback).toBeTypeOf('function');
    callback?.();
    expect(onClose).toHaveBeenCalledOnce();
  });
});
