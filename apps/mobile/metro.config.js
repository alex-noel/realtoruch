const { getDefaultConfig } = require("expo/metro-config");
const config = getDefaultConfig(__dirname);
// The app is small; the portable crawler avoids host Watchman synchronization problems.
config.resolver.useWatchman = false;
config.maxWorkers = 2;
module.exports = config;
