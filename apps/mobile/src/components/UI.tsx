import React, {
  ComponentRef,
  ReactNode,
  RefObject,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import {
  KeyboardAvoidingView,
  ActivityIndicator,
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
import { c, s, controlHeight, typeSize } from "../theme";
import { SafeAreaView } from "react-native-safe-area-context";

export function Button({
  children,
  onPress,
  outline = false,
  disabled = false,
  label,
  expanded,
  variant,
  busy = false,
  busyLabel = "Working…",
}: {
  children: ReactNode;
  onPress: () => void;
  outline?: boolean;
  disabled?: boolean;
  label?: string;
  expanded?: boolean;
  variant?: "primary" | "secondary" | "danger" | "quiet";
  busy?: boolean;
  busyLabel?: string;
}) {
  const [hovered, setHovered] = useState(false);
  const kind = variant ?? (outline ? "secondary" : "primary");
  const filled = kind === "primary" || kind === "danger";
  const unavailable = disabled || busy;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={busy ? busyLabel : label}
      accessibilityState={{ disabled: unavailable, busy }}
      {...(Platform.OS === "web" ? { "aria-busy": busy || undefined } : {})}
      aria-expanded={expanded}
      disabled={unavailable}
      onPress={onPress}
      onHoverIn={() => setHovered(true)}
      onHoverOut={() => setHovered(false)}
      style={({ pressed }) => [
        filled ? s.button : s.outline,
        kind === "danger" && { backgroundColor: c.danger },
        kind === "quiet" && { borderColor: "transparent", backgroundColor: "transparent" },
        { maxWidth: "100%", minWidth: controlHeight, opacity: unavailable ? 0.55 : pressed ? 0.75 : hovered ? 0.88 : 1 },
      ]}
    >
      {busy && <ActivityIndicator size="small" color={filled ? c.paper : c.green} aria-hidden accessibilityElementsHidden importantForAccessibility="no-hide-descendants" />}
      <Text
        style={[
          filled ? s.buttonText : [s.text, { fontSize: typeSize.control, fontWeight: "600" }],
          { flexShrink: 1, textAlign: "center" },
        ]}
      >
        {busy ? busyLabel : children}
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
      {...(Platform.OS === "web" ? { "aria-pressed": !!selected } : {})}
      style={[
        s.outline,
        {
          minHeight: controlHeight,
          minWidth: controlHeight,
          maxWidth: "100%",
          paddingVertical: 8,
          paddingHorizontal: 12,
          borderColor: selected ? c.green : c.line,
          backgroundColor: selected ? c.pale : "white",
        },
      ]}
    >
      {selected && <Check size={13} color={c.green} />}
      <Text
        style={[
          s.text,
          { flexShrink: 1, fontSize: 12, fontWeight: selected ? "600" : "400" },
        ]}
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
  errorId,
  inputPurpose,
  autoComplete,
  helperText,
  error,
  onSubmitEditing,
  submitBehavior,
}: {
  label: string;
  value: string;
  onChange: (text: string) => void;
  placeholder?: string;
  secure?: boolean;
  numeric?: boolean;
  multiline?: boolean;
  /** Purpose controls browser autofill and the matching native keyboard hint. */
  inputPurpose?: "email" | "current-password" | "new-password";
  autoComplete?: "email" | "current-password" | "new-password";
  helperText?: string;
  /** A present message marks this field invalid and is announced by its input. */
  error?: string;
  errorId?: string;
  onSubmitEditing?: () => void;
  submitBehavior?: "submit" | "blurAndSubmit" | "newline";
}) {
  const labelId = useId();
  const helperId = helperText ? `${labelId}-helper` : undefined;
  const invalid = !!error || !!errorId;
  const errorDescriptionId =
    errorId ?? (error ? `${labelId}-error` : undefined);
  const describedBy =
    [errorDescriptionId, helperId].filter(Boolean).join(" ") || undefined;
  const purpose = inputPurpose ?? autoComplete;
  return (
    <View style={{ gap: 8, flex: 1, minWidth: 0 }}>
      <Text nativeID={labelId} style={s.label}>
        {label}
      </Text>
      <TextInput
        accessibilityLabel={label}
        {...(Platform.OS === "web"
          ? {
              "aria-labelledby": labelId,
              "aria-invalid": invalid || undefined,
              "aria-describedby": describedBy,
              autoComplete: purpose,
            }
          : {})}
        {...(Platform.OS !== "web" ? nativeFieldPurposeProps(purpose) : {})}
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor={c.muted}
        secureTextEntry={
          secure || purpose === "current-password" || purpose === "new-password"
        }
        keyboardType={
          numeric
            ? "numeric"
            : purpose === "email"
              ? "email-address"
              : "default"
        }
        multiline={multiline}
        {...(Platform.OS === "web"
          ? {
              returnKeyType: multiline ? undefined : "done",
              blurOnSubmit: !multiline,
            }
          : {
              returnKeyType: multiline ? undefined : "done",
              submitBehavior:
                submitBehavior ?? (multiline ? "newline" : "submit"),
            })}
        onSubmitEditing={onSubmitEditing}
        autoCapitalize="none"
        style={[
          s.input,
          multiline && { minHeight: 100, textAlignVertical: "top" },
        ]}
      />
      {helperText ? (
        <Text nativeID={helperId} style={s.muted}>
          {helperText}
        </Text>
      ) : null}
      {error ? (
        <Text
          nativeID={errorId ?? `${labelId}-error`}
          accessibilityLiveRegion="polite"
          style={s.muted}
        >
          {error}
        </Text>
      ) : null}
    </View>
  );
}

/** Native TextInput autofill and keyboard hints for supported field purposes. */
export function nativeFieldPurposeProps(
  purpose: "email" | "current-password" | "new-password" | undefined,
) {
  return {
    autoComplete: purpose,
    ...(purpose === "current-password" || purpose === "new-password"
      ? { secureTextEntry: true }
      : {}),
    textContentType:
      purpose === "email"
        ? ("emailAddress" as const)
        : purpose === "current-password"
          ? ("password" as const)
          : purpose === "new-password"
            ? ("newPassword" as const)
            : undefined,
    ...(purpose === "email" ? { keyboardType: "email-address" as const } : {}),
  };
}

// The web dialog enters the browser's top layer, making the rest of the page
// inert. Wrap Tab at both ends so the browser toolbar stays out of the loop.
function WebPanel({
  titleId,
  onClose,
  children,
}: {
  titleId: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useLayoutEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    const opener = document.activeElement;
    dialog.showModal();
    dialog.querySelector<HTMLElement>('[aria-label="Close dialog"]')?.focus();
    return () => {
      dialog.close();
      if (opener instanceof HTMLElement && opener.isConnected)
        opener.focus({ preventScroll: true });
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="app-dialog"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const stops = Array.from(
          event.currentTarget.querySelectorAll<HTMLElement>(
            "a[href],button,input,select,textarea,[tabindex]",
          ),
        ).filter(
          (node) =>
            node.tabIndex >= 0 &&
            !node.matches(":disabled,[aria-disabled=true]") &&
            !node.closest("[inert]") &&
            node.getClientRects().length > 0 &&
            getComputedStyle(node).visibility === "visible",
        );
        const index = stops.indexOf(document.activeElement as HTMLElement);
        if (
          index < 0 ||
          (event.shiftKey ? index === 0 : index === stops.length - 1)
        ) {
          event.preventDefault();
          (event.shiftKey ? stops.at(-1) : stops[0])?.focus();
        }
      }}
    >
      {children}
    </dialog>
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
  const titleId = useId();
  const web = Platform.OS === "web";
  const panel = (
    <View
      style={{
        flex: 1,
        backgroundColor: "#102620AA",
        justifyContent: "center",
        alignItems: "center",
        padding: web ? 12 : 18,
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
              padding: web ? 16 : 22,
              justifyContent: "space-between",
              borderBottomWidth: 1,
              borderColor: c.line,
            },
          ]}
        >
          <Text
            accessibilityRole="header"
            nativeID={web ? titleId : undefined}
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
          style={web ? { minHeight: 0, flexShrink: 1 } : undefined}
          onScroll={inboxViewport?.onChange}
          onLayout={inboxViewport?.onChange}
          onContentSizeChange={inboxViewport?.onChange}
          scrollEventThrottle={inboxViewport ? 32 : undefined}
          contentContainerStyle={{ padding: web ? 18 : 24, gap: 22 }}
          keyboardShouldPersistTaps="handled"
        >
          {children}
        </ScrollView>
      </View>
    </View>
  );
  if (web)
    return (
      <WebPanel titleId={titleId} onClose={onClose}>
        {panel}
      </WebPanel>
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
