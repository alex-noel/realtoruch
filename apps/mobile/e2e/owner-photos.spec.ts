import { expect, test, type Page, type Response } from "@playwright/test";
import { readFile, readdir } from "node:fs/promises";
import { join } from "node:path";

type FilePayload = { name: string; mimeType: string; buffer: Buffer };

const password = "synthetic-photos-password-123";
const api = process.env.E2E_API_URL!;
const auth = process.env.E2E_AUTH_URL!;
const media = `${api}/v1/me/media`;
const adverts = `${api}/v1/me/adverts`;
const routeStatus = (response: Response, method: string, url: string) =>
  response.url() === url && response.request().method() === method;

async function registerVerifiedOwner(page: Page, email: string) {
  await page.goto("/", { waitUntil: "commit" });
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page
    .getByRole("button", { name: "New here? Create a free account" })
    .click();
  await page.getByPlaceholder("you@example.com").fill(email);
  await page.getByPlaceholder("At least 12 characters").fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Account", exact: true }),
  ).toBeVisible();
  let token = "";
  await expect
    .poll(
      async () => {
        const files = await readdir(process.env.E2E_MAIL_DIR!).catch(() => []);
        for (const name of files.filter((name) => name.endsWith(".eml"))) {
          const msg = (
            await readFile(join(process.env.E2E_MAIL_DIR!, name), "utf8")
          )
            .replace(/=\r?\n/g, "")
            .replace(/=3D/gi, "=");
          if (msg.includes(email))
            token = msg.match(/#verify_account=([^\s]+)/)?.[1] ?? "";
        }
        return !!token;
      },
      { timeout: 20_000 },
    )
    .toBe(true);
  await page.evaluate((value) => {
    window.location.hash = `verify_account=${value}`;
  }, token);
  const verification = page.waitForResponse((r) =>
    routeStatus(r, "POST", `${auth}/v1/auth/verify-email`),
  );
  await page.reload({ waitUntil: "commit" });
  expect((await verification).status()).toBe(200);
  await page.getByRole("button", { name: "Account", exact: true }).click();
  await page.getByRole("button", { name: "My rental adverts" }).click();
  await page.getByLabel("PUBLIC NAME").fill("Synthetic photo owner");
  await page.getByRole("button", { name: "Save profile" }).click();
}

async function png(
  page: Page,
  name: string,
  rgb: string,
): Promise<FilePayload> {
  const base64 = await page.evaluate((fill) => {
    const canvas = document.createElement("canvas");
    canvas.width = 24;
    canvas.height = 16;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = fill;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(4, 4, 5, 5);
    return canvas.toDataURL("image/png").split(",")[1];
  }, rgb);
  return { name, mimeType: "image/png", buffer: Buffer.from(base64, "base64") };
}

async function choose(page: Page, files: FilePayload[], keyboard = false) {
  const chooser = page.waitForEvent("filechooser");
  const button = page.getByRole("button", {
    name: "Choose photos",
    exact: true,
  });
  if (keyboard) {
    await button.focus();
    await expect(button).toBeFocused();
    await page.keyboard.press("Enter");
  } else {
    await button.click();
  }
  await (await chooser).setFiles(files);
}

test("owner uploads generated photos, blocks unfinished saves, and resolves stale editing safely", async ({
  page,
  context,
  request,
}, info) => {
  test.setTimeout(90_000);
  if (info.project.name === "mobile")
    await page.setViewportSize({ width: 320, height: 800 });
  const allowed = new Set((process.env.E2E_ALLOWED_PORTS ?? "").split(","));
  const blocked: string[] = [];
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (
      ["data:", "blob:"].includes(url.protocol) ||
      (url.hostname === "127.0.0.1" && allowed.has(url.port))
    )
      await route.continue();
    else {
      blocked.push(url.origin);
      await route.abort("blockedbyclient");
    }
  });
  await page.addInitScript(() => {
    const create = URL.createObjectURL.bind(URL);
    const revoke = URL.revokeObjectURL.bind(URL);
    const urls = { active: new Set<string>(), created: 0 };
    Object.assign(window, { __photoURLs: urls });
    URL.createObjectURL = (blob) => {
      const url = create(blob);
      if ("type" in blob && blob.type.startsWith("image/")) {
        urls.active.add(url);
        urls.created++;
      }
      return url;
    };
    URL.revokeObjectURL = (url) => {
      urls.active.delete(url);
      revoke(url);
    };
  });

  const email = `owner-photos-${info.project.name}@example.test`;
  const originalTitle = `Photo fixture home ${info.project.name}`;
  const originalDescription =
    "A synthetic rental advert with generated test images and no personal data.";
  await registerVerifiedOwner(page, email);
  await page.getByRole("button", { name: "Create rental advert" }).click();
  await page.getByLabel("TITLE", { exact: true }).fill(originalTitle);
  await page
    .getByLabel("DESCRIPTION", { exact: true })
    .fill(originalDescription);
  await page.getByLabel("Location latitude").fill("50.0647");
  await page.getByLabel("Location longitude").fill("19.945");
  await page.getByLabel("STREET AND BUILDING").fill("Testowa 24");
  await page.getByLabel("MONTHLY BASE RENT (PLN)").fill("4400");

  const fixtures = await Promise.all([
    png(page, "red.png", "#ec4839"),
    png(page, "green.png", "#2a9e64"),
    png(page, "blue.png", "#3269eb"),
    png(page, "yellow.png", "#e0b331"),
    png(page, "local.png", "#9568d5"),
    png(page, "latest.png", "#fb751a"),
  ]);
  const attempts: Record<string, string[]> = {};
  const received: Record<string, string> = {};
  const cors = { "Access-Control-Allow-Origin": process.env.E2E_WEB_URL! };
  let releaseYellow!: () => void;
  const yellow = new Promise<void>((resolve) => {
    releaseYellow = resolve;
  });
  let activeDescriptions = 0;
  let activeDeletes = 0;
  await page.route(`${media}/**`, async (route) => {
    if (route.request().method() === "PATCH") activeDescriptions++;
    if (
      route.request().method() === "DELETE" &&
      !route.request().url().includes("/by-key/")
    )
      activeDeletes++;
    await route.fallback();
  });
  await page.route(media, async (route) => {
    const req = route.request();
    if (req.method() !== "POST") return route.fallback();
    const raw = req.postDataBuffer();
    const file = fixtures.find((fixture) => raw?.equals(fixture.buffer));
    if (!file) return route.abort("failed");
    const keys = (attempts[file.name] ??= []);
    keys.push(req.headers()["idempotency-key"]);
    if (file.name === "red.png" && keys.length === 1) {
      return route.fulfill({
        status: 401,
        json: { detail: "Synthetic token expiration" },
        headers: cors,
      });
    }
    if (file.name === "blue.png" && keys.length === 1) {
      return route.fulfill({
        status: 503,
        json: { detail: "Synthetic connection interruption" },
        headers: cors,
      });
    }
    if (file.name === "yellow.png") {
      await yellow;
      // The UI cancels by key while this upload has no response/ID.
      await route.abort().catch(() => {});
      return;
    }
    const forwarded = await route.fetch();
    if (forwarded.ok()) received[file.name] = (await forwarded.json()).id;
    await route.fulfill({ response: forwarded });
  });

  try {
    const refreshed = page.waitForResponse((r) =>
      routeStatus(r, "POST", `${auth}/v1/auth/refresh`),
    );
    await choose(
      page,
      [
        ...fixtures.slice(0, 4),
        {
          name: "invalid.txt",
          mimeType: "text/plain",
          buffer: Buffer.from("not a picture"),
        },
        {
          name: "oversized.png",
          mimeType: "image/png",
          buffer: Buffer.alloc(10 * 1024 * 1024 + 1),
        },
      ],
      true,
    );
    expect((await refreshed).status()).toBe(200);
    await expect(
      page.getByText("invalid.txt: Choose a JPEG, PNG or WebP image."),
    ).toBeVisible();
    await expect(
      page.getByText("oversized.png: Choose an image no larger than 10 MiB."),
    ).toBeVisible();
    await expect(page.getByText(/^Ready(?: · Cover photo)?$/)).toHaveCount(2);
    await expect(page.getByText("Failed", { exact: true })).toHaveCount(1);
    await expect(page.getByText("Uploading…", { exact: true })).toHaveCount(1);
    expect(attempts["red.png"]).toHaveLength(2);
    expect(new Set(attempts["red.png"]).size).toBe(1);
    expect(attempts["invalid.txt"]).toBeUndefined();
    expect(attempts["oversized.png"]).toBeUndefined();
    await expect(page.getByLabel("TITLE", { exact: true })).toHaveValue(
      originalTitle,
    );
    await expect(page.getByLabel("DESCRIPTION", { exact: true })).toHaveValue(
      originalDescription,
    );

    const move = page.getByRole("button", {
      name: "Move photo 2, green.png earlier",
    });
    await move.focus();
    await expect(move).toBeFocused();
    await page.keyboard.press("Enter");
    const redDescription = "Red wall with a white square";
    await page
      .getByLabel("Description for photo 2, red.png")
      .fill(redDescription);
    let prematureSaves = 0;
    await page.route(adverts, async route => {
      if (route.request().method() === "POST") prematureSaves++;
      await route.fallback();
    });
    await expect(page.getByRole("button", { name: "Save draft", exact: true })).toBeDisabled();
    expect(prematureSaves).toBe(0);

    const cancel = page.getByRole("button", {
      name: "Cancel upload for photo 4, yellow.png",
    });
    await cancel.focus();
    await expect(cancel).toBeFocused();
    const cancelResponse = page.waitForResponse((r) =>
      routeStatus(r, "DELETE", `${media}/by-key/${attempts["yellow.png"][0]}`),
    );
    await page.keyboard.press("Enter");
    const tombstone = await cancelResponse;
    expect(tombstone.status()).toBe(200);
    expect((await tombstone.json()).state).toBe("deleted");
    releaseYellow();
    await page.getByRole("button", { name: "Retry photo 3, blue.png" }).click();
    await expect(page.getByText(/^Ready(?: · Cover photo)?$/)).toHaveCount(3);
    expect(attempts["blue.png"]).toHaveLength(2);
    expect(new Set(attempts["blue.png"]).size).toBe(1);

    const firstSave = page.waitForResponse(r => routeStatus(r, "POST", adverts));
    await page.getByRole("button", { name: "Save draft", exact: true }).click();
    const first = await firstSave;
    expect(first.status()).toBe(201);
    const created = await first.json();
    const advertUrl = `${adverts}/${created.id}`;
    expect(created.advert.media_ids).toEqual([
      received["green.png"], received["red.png"], received["blue.png"],
    ]);
    expect(created.advert.images).toEqual([]);
    expect(prematureSaves).toBe(1);
    await expect(page.getByRole("button", { name: "Review and publish", exact: true })).toBeVisible();
    const resources = () =>
      page.evaluate(() => {
        const data = (
          window as unknown as {
            __photoURLs: { active: Set<string>; created: number };
          }
        ).__photoURLs;
        return { active: data.active.size, created: data.created };
      });
    await expect.poll(async () => (await resources()).active).toBe(0);
    expect((await resources()).created).toBeGreaterThan(0);
    await expect(page.locator('input[type="file"]')).toHaveCount(0);

    await page.getByRole("button", { name: "Edit", exact: true }).click();
    await expect(page.getByLabel("TITLE", { exact: true })).toHaveValue(
      originalTitle,
    );
    await expect(page.getByLabel("Description for photo 2")).toHaveValue(
      redDescription,
    );
    const privateDisplay = page.waitForResponse((r) =>
      routeStatus(r, "GET", `${media}/${received["red.png"]}/display`),
    );
    await page
      .getByRole("button", { name: "View larger preview for photo 2" })
      .click();
    expect((await privateDisplay).status()).toBe(200);
    expect(
      (await request.get(`${media}/${received["red.png"]}/thumbnail`)).status(),
    ).toBe(401);
    if (info.project.name === "mobile") {
      const fits = await page
        .getByRole("dialog")
        .evaluate(
          (dialog) =>
            dialog.getBoundingClientRect().width <= 320 &&
            dialog.scrollWidth <= dialog.clientWidth,
        );
      expect(fits).toBe(true);
    }
    await page.getByRole("button", { name: "Back to adverts" }).click();
    await expect.poll(async () => (await resources()).active).toBe(0);
    const published = page.waitForResponse((r) =>
      routeStatus(r, "POST", `${advertUrl}/publish`),
    );
    await page.getByRole("button", { name: "Review and publish", exact: true }).click();
    await page.getByRole("button", { name: "Publish advert", exact: true }).click();
    expect((await published).status()).toBe(200);
    await expect(page.getByText(/PUBLISHED.*4\s?400/)).toBeVisible();

    // Open a truly separate authenticated session and edit its latest version.
    const login = await request.post(`${auth}/v1/auth/login`, {
      data: { email, password, client: "native" },
    });
    expect(login.status()).toBe(200);
    const second = {
      Authorization: `Bearer ${(await login.json()).access_token}`,
    };
    const newRemote = await request.post(media, {
      data: fixtures[5].buffer,
      headers: {
        ...second,
        "Content-Type": "image/png",
        "Idempotency-Key": "synthetic-remote-photo",
      },
    });
    expect(newRemote.ok()).toBe(true);
    const remoteId = (await newRemote.json()).id;
    const latestDescription =
      "The newer description from a separate authenticated owner session.";
    const versions = await request.get(adverts, { headers: second });
    const previous = (await versions.json()).items.find(
      (item: { id: string }) => item.id === created.id,
    );

    await page.getByRole("button", { name: "Edit", exact: true }).click();
    await expect(page.getByText(/^Ready(?: · Cover photo)?$/)).toHaveCount(3);
    await page
      .getByLabel("TITLE", { exact: true })
      .fill(originalTitle + " merged");
    await page
      .getByLabel("Description for photo 2")
      .fill("Edited description stays local until the advert saves");
    await page
      .getByRole("button", { name: "Remove photo 3", exact: true })
      .click();
    await choose(page, [fixtures[4]]);
    await expect(page.getByText(/^Ready(?: · Cover photo)?$/)).toHaveCount(3);
    const remoteWrite = await request.put(advertUrl, {
      headers: second,
      data: {
        version: previous.version,
        advert: {
          ...previous.advert,
          description: latestDescription,
          media_ids: [...previous.advert.media_ids, remoteId],
        },
      },
    });
    expect(remoteWrite.status()).toBe(200);
    const stale = page.waitForResponse((r) => routeStatus(r, "PUT", advertUrl));
    await page.getByRole("button", { name: "Review published changes" }).click();
    await page.getByRole("button", { name: "Apply published changes" }).click();
    expect((await stale).status()).toBe(409);
    await expect(page.getByText(/This advert changed on another device/).first()).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Reload latest version" }),
    ).toBeVisible();
    expect(activeDeletes).toBe(0);
    expect(activeDescriptions).toBe(1); // Only the accepted initial draft edit.
    const stillRemote = (
      await (await request.get(adverts, { headers: second })).json()
    ).items.find((item: { id: string }) => item.id === created.id);
    expect(stillRemote.advert.description).toBe(latestDescription);
    expect(stillRemote.advert.title).toBe(originalTitle);
    await page.getByRole("button", { name: "Use mine for title" }).click();
    await page.getByRole("button", { name: "Use latest for description" }).click();
    // Keep the remote addition using Q30’s explicit whole-field choice.
    await page.getByRole("button", { name: "Use latest for media_ids" }).click();
    await page.getByRole("button", { name: "Save selected values" }).click();
    await expect(page.getByText("Review this rental")).toBeVisible();
    const merged = page.waitForResponse((r) =>
      routeStatus(r, "PUT", advertUrl),
    );
    await page.getByRole("button", { name: "Apply published changes" }).click();
    const saved = await merged;
    expect(saved.status()).toBe(200);
    expect((await saved.json()).advert.media_ids).toEqual([
      received["green.png"],
      received["red.png"],
      received["blue.png"],
      remoteId,
    ]);
    const accepted = await saved.json();
    expect(accepted.advert.title).toBe(originalTitle + " merged");
    expect(accepted.advert.description).toBe(latestDescription);
    await expect.poll(async () => (await (await request.get(`${media}/${received["local.png"]}`, { headers: second })).json()).state).toBe("deleted");
    // Choosing latest must preserve its published assets and clean the rejected local upload.
    expect(activeDeletes).toBe(0);
    await page.getByRole("button", { name: "Edit", exact: true }).click();
    await expect(page.getByText(/^Ready(?: · Cover photo)?$/)).toHaveCount(4);
    await page.getByRole("button", { name: "Remove photo 3", exact: true }).click();
    const detached = page.waitForResponse(r => routeStatus(r, "DELETE", `${media}/${received["blue.png"]}`));
    await page.getByRole("button", { name: "Review published changes" }).click();
    const removalSave = page.waitForResponse(r => routeStatus(r, "PUT", advertUrl));
    await page.getByRole("button", { name: "Apply published changes" }).click();
    expect((await removalSave).status()).toBe(200);
    expect((await detached).status()).toBe(200);
    await expect(
      page.getByRole("button", { name: "Edit", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Close dialog" }).click();
    const home = page.getByRole("button", {
      name: `View ${originalTitle} merged`,
      exact: true,
    });
    await expect(home.locator("img")).toHaveAttribute(
      "src",
      `${api}/v1/media/${received["green.png"]}/thumbnail`,
    );
    await expect(home.locator("img")).toHaveAttribute(
      "alt",
      "Illustrative apartment interior",
    );
    await page.getByRole("button", { name: "Account", exact: true }).click();
    await page.getByRole("button", { name: "My rental adverts" }).click();
    let withdrawals = 0;
    await page.route(`${advertUrl}/withdraw`, async route => {
      if (route.request().method() === "POST") withdrawals++;
      await route.fallback();
    });
    await page.getByRole("button", { name: "Withdraw", exact: true }).click();
    await expect(page.getByRole("region", { name: "Confirm withdrawal" })).toContainText(originalTitle + " merged");
    await page.getByRole("button", { name: "Keep published" }).click();
    expect(withdrawals).toBe(0);
    await page.getByRole("button", { name: "Withdraw", exact: true }).click();
    const withdrawn = page.waitForResponse(r => routeStatus(r, "POST", `${advertUrl}/withdraw`));
    await page.getByRole("button", { name: "Confirm withdrawal", exact: true }).click();
    expect((await withdrawn).status()).toBe(200);
    expect(withdrawals).toBe(1);
    await expect(page.getByText(/^WITHDRAWN ·/)).toBeVisible();
    // Q33 retains already published photos; private management remains authenticated.
    expect((await request.get(`${api}/v1/media/${received["green.png"]}/thumbnail`)).status()).toBe(200);
    expect((await request.get(`${media}/${received["green.png"]}/thumbnail`)).status()).toBe(401);
    expect(blocked).toEqual([]);
  } finally {
    releaseYellow();
  }
});
