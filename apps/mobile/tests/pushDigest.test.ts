import { createHash } from "node:crypto";
import { expect, it } from "vitest";
import { pushSubscriptionId } from "../src/pushDigest";

it.each(["", "abc", "x".repeat(55), "x".repeat(56), "x".repeat(128), "zażółć 🏠", "ExponentPushToken[fixture]"])("matches the server SHA-256 for %s", value => {
  expect(pushSubscriptionId(value)).toBe(createHash("sha256").update(value, "utf8").digest("hex"));
});
