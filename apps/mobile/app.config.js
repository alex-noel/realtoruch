const { expo } = require("./app.json");
module.exports = {
  ...expo,
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
