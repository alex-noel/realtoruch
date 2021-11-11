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
};
export const font =
  Platform.OS === "web"
    ? 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    : undefined;
export const s = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center" },
  label: {
    color: c.muted,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 1.4,
    fontFamily: font,
  },
  title: {
    color: c.ink,
    fontSize: 26,
    fontWeight: "600",
    letterSpacing: -1,
    fontFamily: font,
  },
  text: { color: c.ink, fontSize: 14, lineHeight: 22, fontFamily: font },
  muted: { color: c.muted, fontSize: 12, lineHeight: 19, fontFamily: font },
  button: {
    backgroundColor: c.green,
    paddingVertical: 13,
    paddingHorizontal: 18,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 8,
    minHeight: 44,
  },
  buttonText: {
    color: "white",
    fontSize: 13,
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
    gap: 8,
    minHeight: 44,
  },
  input: {
    borderWidth: 1,
    borderColor: "#7A897F",
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: c.ink,
    backgroundColor: "white",
    minHeight: 46,
    fontSize: 14,
    fontFamily: font,
  },
  card: { backgroundColor: c.paper, borderWidth: 1, borderColor: c.line },
});
