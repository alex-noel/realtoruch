import React, { ComponentRef, ReactNode, RefObject } from "react";
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import Check from "lucide-react-native/icons/check";
import X from "lucide-react-native/icons/x";
import { c, s } from "../theme";
import { SafeAreaView } from "react-native-safe-area-context";

export function Button({
  children,
  onPress,
  outline = false,
  disabled = false,
  label,
}: {
  children: ReactNode;
  onPress: () => void;
  outline?: boolean;
  disabled?: boolean;
  label?: string;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        outline ? s.outline : s.button,
        { opacity: disabled ? 0.5 : pressed ? 0.75 : 1 },
      ]}
    >
      <Text
        style={
          outline ? [s.text, { fontSize: 13, fontWeight: "600" }] : s.buttonText
        }
      >
        {children}
      </Text>
    </Pressable>
  );
}
export function Chip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: !!selected }}
      style={[
        s.outline,
        {
          minHeight: 38,
          paddingVertical: 8,
          paddingHorizontal: 12,
          borderColor: selected ? c.green : c.line,
          backgroundColor: selected ? c.pale : "white",
        },
      ]}
    >
      {selected && <Check size={13} color={c.green} />}
      <Text
        style={[s.text, { fontSize: 12, fontWeight: selected ? "600" : "400" }]}
      >
        {label}
      </Text>
    </Pressable>
  );
}
export function Field({
  label,
  value,
  onChange,
  placeholder,
  secure = false,
  numeric = false,
  multiline = false,
}: {
  label: string;
  value: string;
  onChange: (text: string) => void;
  placeholder?: string;
  secure?: boolean;
  numeric?: boolean;
  multiline?: boolean;
}) {
  return (
    <View style={{ gap: 8, flex: 1 }}>
      <Text style={s.label}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor={c.muted}
        secureTextEntry={secure}
        keyboardType={numeric ? "numeric" : "default"}
        multiline={multiline}
        autoCapitalize="none"
        style={[
          s.input,
          multiline && { minHeight: 100, textAlignVertical: "top" },
        ]}
      />
    </View>
  );
}
export function Panel({
  title,
  children,
  onClose,
  wide = false,
  inboxViewport,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
  inboxViewport?: {
    ref: RefObject<ComponentRef<typeof ScrollView> | null>;
    onChange: () => void;
  };
}) {
  const panel = (
    <View
      style={{
        flex: 1,
        backgroundColor: "#102620AA",
        justifyContent: "center",
        alignItems: "center",
        padding: 18,
      }}
    >
      <View
        style={{
          width: "100%",
          maxWidth: wide ? 1000 : 560,
          maxHeight: "94%",
          backgroundColor: c.bg,
        }}
        accessibilityViewIsModal
      >
        <View
          style={[
            s.row,
            {
              padding: 22,
              justifyContent: "space-between",
              borderBottomWidth: 1,
              borderColor: c.line,
            },
          ]}
        >
          <Text
            accessibilityRole="header"
            style={[s.title, { fontSize: 21, flex: 1 }]}
          >
            {title}
          </Text>
          <Pressable
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Close dialog"
            style={{ padding: 10 }}
          >
            <X color={c.ink} size={22} />
          </Pressable>
        </View>
        <ScrollView
          // React Native Web forwards the host ref when mounting the scroll
          // node. Recreate it when entering/leaving the inbox viewport.
          key={inboxViewport ? "inbox" : "panel"}
          ref={inboxViewport?.ref}
          testID={inboxViewport ? "messages-scroll" : undefined}
          onScroll={inboxViewport?.onChange}
          onLayout={inboxViewport?.onChange}
          onContentSizeChange={inboxViewport?.onChange}
          scrollEventThrottle={inboxViewport ? 32 : undefined}
          contentContainerStyle={{ padding: 24, gap: 22 }}
          keyboardShouldPersistTaps="handled"
        >
          {children}
        </ScrollView>
      </View>
    </View>
  );
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      {inboxViewport && Platform.OS !== "web" ? (
        <SafeAreaView style={{ flex: 1, backgroundColor: "#102620AA" }}>
          <KeyboardAvoidingView
            behavior={Platform.OS === "ios" ? "padding" : undefined}
            style={{ flex: 1 }}
          >
            {panel}
          </KeyboardAvoidingView>
        </SafeAreaView>
      ) : (
        panel
      )}
    </Modal>
  );
}
export const money = (amount: number | null) =>
  amount === null
    ? "Not stated"
    : `${new Intl.NumberFormat("pl-PL").format(amount)} zł`;
