import { Platform, StyleSheet } from "react-native";
export const c = {
  bg: "#F6F6F1",
  paper: "#FFFFFF",
  ink: "#172D2A",
  muted: "#536259",
  line: "#E0E5DD",
  green: "#234D3D",
  pale: "#E9EEE4",
  orange: "#A84625",
  cream: "#F0E9D8",
  warning: "#935C2F",
  danger: "#9B302B",
};
export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 };
export const typeSize = { label: 10, caption: 12, control: 13, body: 14, title: 26 };
export const controlHeight = 44;
export const font =
  Platform.OS === "web"
    ? 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    : undefined;
export const s = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center" },
  label: {
    color: c.muted,
    fontSize: typeSize.label,
    fontWeight: "700",
    letterSpacing: 1.4,
    fontFamily: font,
  },
  title: {
    color: c.ink,
    fontSize: typeSize.title,
    fontWeight: "600",
    letterSpacing: -1,
    fontFamily: font,
  },
  text: { color: c.ink, fontSize: typeSize.body, lineHeight: 22, fontFamily: font },
  muted: { color: c.muted, fontSize: typeSize.caption, lineHeight: 19, fontFamily: font },
  button: {
    backgroundColor: c.green,
    paddingVertical: 13,
    paddingHorizontal: 18,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: space.sm,
    minHeight: controlHeight,
  },
  buttonText: {
    color: "white",
    fontSize: typeSize.control,
    fontWeight: "600",
    fontFamily: font,
  },
  outline: {
    borderColor: c.line,
    borderWidth: 1,
    backgroundColor: c.paper,
    paddingVertical: 11,
    paddingHorizontal: 15,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: space.sm,
    minHeight: controlHeight,
  },
  input: {
    borderWidth: 1,
    borderColor: "#7A897F",
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: c.ink,
    backgroundColor: "white",
    minHeight: 46,
    fontSize: typeSize.body,
    fontFamily: font,
  },
  card: { backgroundColor: c.paper, borderWidth: 1, borderColor: c.line },
});
