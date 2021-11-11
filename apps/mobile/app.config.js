const { expo } = require("./app.json");
const scheme = process.env.EXPO_PUBLIC_LINK_SCHEME || expo.scheme;
const reserved = [
  "http",
  "https",
  "javascript",
  "data",
  "file",
  "about",
  "ftp",
  "blob",
  "content",
  "intent",
  "exp",
  "exps",
  "mailto",
  "tel",
  "sms",
];
if (!/^[a-z][a-z0-9+.-]{1,39}$/.test(scheme) || reserved.includes(scheme)) {
  throw new Error("EXPO_PUBLIC_LINK_SCHEME must be a custom app scheme.");
}

module.exports = {
  ...expo,
  scheme,
  plugins: [...expo.plugins, "expo-notifications"],
  extra: {
    ...expo.extra,
    ...(process.env.EXPO_PUBLIC_EAS_PROJECT_ID
      ? { eas: { projectId: process.env.EXPO_PUBLIC_EAS_PROJECT_ID } }
      : {}),
  },
  android: {
    ...expo.android,
    config: {
      googleMaps: { apiKey: process.env.GOOGLE_MAPS_ANDROID_API_KEY || "" },
    },
  },
};
