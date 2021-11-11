import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { request } from "./api";
const KEY = "realtoruch.push.v1";
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});
export async function pushEnabled() {
  return !!(await AsyncStorage.getItem(KEY));
}
export async function enablePush() {
  const config = await request<{ expo_push_enabled: boolean }>(
    "/v1/notifications/config",
  );
  if (!config.expo_push_enabled)
    throw new Error(
      "Mobile push is not configured yet. Your alerts are saved in the inbox.",
    );
  const projectId =
    Constants.easConfig?.projectId ||
    Constants.expoConfig?.extra?.eas?.projectId;
  if (!projectId)
    throw new Error(
      "Use a configured development or release build to enable mobile push.",
    );
  if (Platform.OS === "android")
    await Notifications.setNotificationChannelAsync("rentals", {
      name: "Rental alerts",
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  const permissions = await Notifications.requestPermissionsAsync();
  if (permissions.status !== "granted")
    throw new Error("Allow notifications in device settings to enable alerts.");
  const token = (await Notifications.getExpoPushTokenAsync({ projectId })).data;
  const result = await request<{ id: string }>("/v1/me/push-subscriptions", {
    method: "POST",
    body: JSON.stringify({ kind: "expo", token }),
  });
  await AsyncStorage.setItem(KEY, result.id);
}
export async function disablePush() {
  const id = await AsyncStorage.getItem(KEY);
  try {
    if (id)
      await request(`/v1/me/push-subscriptions/${id}`, { method: "DELETE" });
  } finally {
    if (id) await Notifications.unregisterForNotificationsAsync();
    await AsyncStorage.removeItem(KEY);
  }
}
export function listenForPush(
  onOpen: (id: string) => void,
  onUpdate: () => void,
) {
  let active = true;
  const open = (response: Notifications.NotificationResponse) => {
    const id = response.notification.request.content.data?.listing_id;
    if (active && typeof id === "string") {
      onOpen(id);
      Notifications.clearLastNotificationResponseAsync().catch(() => {});
    }
  };
  const receive = Notifications.addNotificationReceivedListener(onUpdate);
  const response = Notifications.addNotificationResponseReceivedListener(open);
  Notifications.getLastNotificationResponseAsync()
    .then((value) => {
      if (value) open(value);
    })
    .catch(() => {});
  return () => {
    active = false;
    receive.remove();
    response.remove();
  };
}
