import { execFileSync } from "node:child_process";
import { writeFile } from "node:fs/promises";
import {
  expect,
  test,
  type BrowserContext,
  type Locator,
  type Page,
} from "@playwright/test";
import type { Listing } from "../src/types";

const web = process.env.E2E_WEB_URL!;
const api = process.env.E2E_API_URL!;
const auth = process.env.E2E_AUTH_URL!;
const first = "T20 home 001";
const second = "T20 home 002";
const timestamp = "2026-01-01T00:00:00Z";
const tile = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR1sAAAAASUVORK5CYII=",
  "base64",
);
const homes: Listing[] = Array.from({ length: 100 }, (_, i) => {
  const n = String(i + 1).padStart(3, "0");
  return {
    id: `t20-${n}`,
    title: `T20 home ${n}`,
    city: "Kraków",
    address: `Example Street ${i + 1}`,
    district: "Krowodrza",
    region: "małopolskie",
    description:
      "A synthetic rental for the local accessibility and loading fixture.",
    lat: 50.06 + i / 10000,
    lon: 19.94 + i / 10000,
    area_m2: 55,
    rooms: 2,
    floor: 2,
    rent_pln: 4000 + i * 20,
    fees_pln: 500,
    deposit_pln: null,
    commission_pln: i ? 0 : null,
    total_monthly_pln: 4500 + i * 20,
    advertiser_type: i === 1 ? "agency" : "private",
    property_type: "apartment",
    status: "active",
    images: [`${web}/t20-image/${n}.png`],
    amenities: [],
    is_demo: false,
    first_seen: timestamp,
    last_seen: timestamp,
    risk_score: 0,
    risk_flags: [],
    sources: [],
  };
});

async function allowOwned(context: BrowserContext, fixture = true) {
  const blocked: string[] = [];
  const favorites = new Map<string, Listing>([
    [
      "t20-inactive",
      {
        ...homes[1],
        id: "t20-inactive",
        title: "T20 delisted favorite",
        status: "inactive",
      },
    ],
  ]);
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (![web, api, auth].includes(url.origin) && url.protocol !== "data:") {
      blocked.push(url.origin);
      return route.abort("blockedbyclient");
    }
    const path = url.pathname;
    if (fixture && url.origin === web && path.startsWith("/t20-image/"))
      return route.fulfill({ contentType: "image/png", body: tile });
    if (!fixture || url.origin !== api) return route.continue();

    const json = async (payload: object) =>
      route.fulfill({
        json: payload,
        headers: {
          "Access-Control-Allow-Origin": web,
          "Access-Control-Allow-Credentials": "true",
        },
      });
    if (route.request().method() === "OPTIONS") return route.continue();
    if (path === "/v1/listings") {
      const min = Number(url.searchParams.get("min_price") || 0);
      const page = Number(url.searchParams.get("page") || 1);
      const size = Number(url.searchParams.get("page_size") || 24);
      const matches = homes.filter((home) => home.rent_pln >= min);
      return json({
        items: matches.slice((page - 1) * size, page * size),
        total: matches.length,
        page,
        page_size: size,
        engine: "sql",
      });
    }
    const home = homes.find((item) => path === `/v1/listings/${item.id}`);
    if (home) return json(home);
    if (path === "/v1/me/favorites")
      return json({ items: [...favorites.values()] });
    if (path.startsWith("/v1/me/favorites/t20-")) {
      const item = homes.find((home) => path.endsWith(home.id));
      if (!item) return route.continue();
      if (route.request().method() === "PUT") favorites.set(item.id, item);
      else favorites.delete(item.id);
      return json({ saved: favorites.has(item.id) });
    }
    if (path === "/v1/me/listing-state")
      return json({ seen_ids: [homes[0].id] });
    if (path === "/v1/me/seen/t20-001") return json({ seen: true });
    if (path === "/v1/me/conversations")
      return json({
        next_cursor: null,
        items: [
          {
            id: "t20-thread",
            title: "Fixture conversation",
            listing_id: null,
            updated_at: timestamp,
            unread_count: 0,
            blocked: false,
            can_unblock: false,
          },
        ],
      });
    if (path === "/v1/me/conversations/t20-thread")
      return json({
        id: "t20-thread",
        items: [],
        next_cursor: null,
        blocked: false,
        can_unblock: false,
      });
    return route.continue();
  });
  return blocked;
}

function button(scope: Page | Locator, name: string) {
  return scope.getByRole("button", { name, exact: true });
}

async function keyboardTo(page: Page, target: Locator) {
  await expect(target).toBeVisible();
  for (let i = 0; i < 150; i++) {
    if (await target.evaluate((node) => node === document.activeElement))
      return;
    await page.keyboard.press("Tab");
  }
  await expect(target).toBeFocused();
}

async function keyActivate(page: Page, target: Locator) {
  await keyboardTo(page, target);
  await page.keyboard.press("Enter");
}

async function keyText(page: Page, target: Locator, value: string) {
  await keyboardTo(page, target);
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.insertText(value);
}

async function close(page: Page, dialog: Locator) {
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
}

async function reachable(target: Locator) {
  await target.scrollIntoViewIfNeeded();
  await expect(target).toBeInViewport({ ratio: 0.9 });
  const box = await target.boundingBox();
  expect(box?.x).toBeGreaterThanOrEqual(-1);
  expect(box!.x + box!.width).toBeLessThanOrEqual(
    target.page().viewportSize()!.width + 1,
  );
}

// Chromium's page zoom also changes CSS viewport width. Scale px text and
// line-height independently of viewport size to exercise 200% text alone.
async function doubleText(page: Page) {
  await page.evaluate(() => {
    const sheet = document.createElement("style");
    sheet.id = "t20-text-only";
    document.head.append(sheet);
    let previous = "";
    function collect(rules: CSSRuleList): string[] {
      return Array.from(rules).flatMap((rule) => {
        if (rule instanceof CSSMediaRule)
          return matchMedia(rule.conditionText).matches
            ? collect(rule.cssRules)
            : [];
        if (!(rule instanceof CSSStyleRule)) return [];
        const styles = ["font-size", "line-height"].flatMap((property) => {
          const value = rule.style.getPropertyValue(property).trim();
          return /^[\d.]+px$/.test(value)
            ? [`${property}: ${parseFloat(value) * 2}px !important;`]
            : [];
        });
        return styles.length
          ? [`${rule.selectorText} {${styles.join("")}}`]
          : [];
      });
    }
    function refresh() {
      if (!sheet.isConnected) return;
      const generated = Array.from(document.styleSheets)
        .filter((source) => source.ownerNode !== sheet)
        .flatMap((source) => collect(source.cssRules));
      const inline = new Set<string>();
      for (const element of Array.from(
        document.querySelectorAll<HTMLElement>("[style]"),
      )) {
        for (const [property, name] of [
          ["font-size", "size"],
          ["line-height", "leading"],
        ]) {
          const value = element.style.getPropertyValue(property).trim();
          const attr = `data-t20-${name}`;
          if (/^[\d.]+px$/.test(value)) {
            if (element.getAttribute(attr) !== value)
              element.setAttribute(attr, value);
            inline.add(
              `[${attr}="${value}"][style] {${property}: ${parseFloat(value) * 2}px !important;}`,
            );
          } else if (element.hasAttribute(attr)) {
            element.removeAttribute(attr);
          }
        }
      }
      const output = [...generated, ...inline].join("\n");
      if (output !== previous) sheet.textContent = previous = output;
      requestAnimationFrame(refresh);
    }
    refresh();
  });
}

async function register(page: Page, email: string) {
  await button(page, "Sign in").click();
  await button(page, "New here? Create a free account").click();
  await page.getByLabel("EMAIL", { exact: true }).fill(email);
  await page
    .getByLabel("PASSWORD", { exact: true })
    .fill("synthetic-t20-password-123");
  await button(page, "Create account").click();
  await expect(button(page, "Account")).toBeVisible();
}

test("T20-TC01 primary screens and validation at normal and 200% text size", async ({
  page,
  context,
}, info) => {
  test.setTimeout(180_000);
  const blocked = await allowOwned(context);
  const widths = info.project.name === "desktop" ? [768, 1440] : [320, 390];
  await page.setViewportSize({ width: widths[0], height: 800 });
  await page.goto("/");
  const signIn = button(page, "Sign in");
  await reachable(signIn);
  await signIn.click();
  const authDialog = page.getByRole("dialog", { name: "Welcome back." });
  await reachable(button(authDialog, "Sign in"));
  await close(page, authDialog);
  await register(page, `t20-${info.project.name}@example.test`);

  for (const width of widths) {
    await page.setViewportSize({ width, height: 800 });
    for (const scale of [1, 2]) {
      await test.step(`${width}px · ${scale * 100}% text`, async () => {
        const overflow = async () => {
          const layout = await page.evaluate(() => {
            const root = document.documentElement;
            return {
              width: root.scrollWidth,
              offenders:
                root.scrollWidth > root.clientWidth
                  ? Array.from(root.querySelectorAll("div,button,input"))
                      .filter(
                        (node) =>
                          node.getBoundingClientRect().right >
                            root.clientWidth + 1 &&
                          !node.closest(".leaflet-container"),
                      )
                      .slice(0, 10)
                      .map((node) => node.textContent?.trim().slice(0, 80))
                  : [],
            };
          });
          expect(
            layout.width,
            `Overflow candidates: ${layout.offenders.join(", ")}`,
          ).toBe(width);
        };
        const heading = page.getByRole("heading", {
          name: "Good places. Clear choices.",
        });
        const base = await heading.evaluate((el) =>
          parseFloat(getComputedStyle(el).fontSize),
        );
        if (scale === 2) {
          await doubleText(page);
          await expect
            .poll(() =>
              heading.evaluate((el) =>
                parseFloat(getComputedStyle(el).fontSize),
              ),
            )
            .toBe(base * 2);
        }
        await overflow();
        await reachable(
          page.getByRole("textbox", { name: "City", exact: true }),
        );
        await reachable(button(page, "Find a home →"));
        await reachable(button(page, "More filters"));
        await button(page, "More filters").click();
        const filter = page.getByRole("dialog", { name: "A home that fits." });
        await filter.getByLabel("MIN RENT · PLN").fill("5000");
        const max = filter.getByLabel("RENT BELOW · PLN");
        await max.fill("4000");
        await button(filter, "Show matching homes").click();
        await expect(filter.getByRole("alert")).toContainText("Minimum values");
        await expect(max).toHaveAccessibleDescription(
          "Minimum values must be lower than maximum values.",
        );
        await reachable(button(filter, "Show matching homes"));
        await reachable(button(filter, "Close dialog"));
        await overflow();
        await close(page, filter);

        await button(page, "Map view").click();
        await reachable(button(page, "Enter area coordinates"));
        await expect(
          page.getByRole("region", { name: "Map of rental homes" }),
        ).toBeVisible();
        await overflow();
        await button(page, "List view").click();

        await button(page, first).click();
        const detail = page.getByRole("dialog", { name: "A closer look" });
        await reachable(button(detail, "Save this home"));
        await reachable(button(detail, "Report a concern"));
        await reachable(button(detail, "Close dialog"));
        await overflow();
        await button(detail, "Report a concern").click();
        const report = page.getByRole("dialog", {
          name: "Something worth checking?",
        });
        await reachable(report.getByLabel("WHAT DID YOU NOTICE?"));
        await reachable(button(report, "Submit report"));
        await close(page, report);
        await close(page, detail);

        await button(page, "Saved homes").click();
        await reachable(button(page, "Unsave T20 delisted favorite"));
        await expect(page.getByText("DELISTED", { exact: true })).toBeVisible();
        await overflow();

        await button(page, "Notifications").click();
        await reachable(button(page, "Enable email alerts"));
        await reachable(button(page, "Enable device alerts"));
        await overflow();

        await button(page, "Account").click();
        const account = page.getByRole("dialog", { name: "Your account." });
        await button(account, "Delete account…").click();
        await reachable(account.getByLabel("CURRENT PASSWORD"));
        await reachable(button(account, "Permanently delete my account"));
        await reachable(button(account, "Close dialog"));
        await overflow();
        await button(account, "My rental adverts").click();
        const desk = page.getByRole("dialog", { name: "Your rental desk." });
        const create = button(desk, "Create rental advert");
        if (width === widths[0] && scale === 1) {
          await desk.getByLabel("PUBLIC NAME").fill("Synthetic owner");
          await button(desk, "Save profile").click();
        }
        await create.click();
        await desk
          .getByLabel("TITLE", { exact: true })
          .fill(`Synthetic advert ${width} ${scale}`);
        await desk
          .getByLabel("DESCRIPTION", { exact: true })
          .fill("An accessibility audit fixture with no real occupant.");
        await desk.getByLabel("STREET AND BUILDING").fill("Fixture Street 15");
        const lat = desk.getByLabel("Location latitude");
        await lat.fill("91");
        await expect(lat).toHaveAccessibleDescription(/Enter a latitude/);
        await lat.fill("50.06");
        await desk.getByLabel("Location longitude").fill("19.94");
        await expect(
          desk.getByText("Location set", { exact: true }),
        ).toBeVisible();
        const saveDraft = button(desk, "Save draft");
        await expect(saveDraft).toBeEnabled();
        await reachable(saveDraft);
        await reachable(button(desk, "Close dialog"));
        await overflow();
        if (width === widths[0] && scale === 1) {
          await saveDraft.click();
          await expect(desk.getByText(/DRAFT ·/)).toBeVisible();
        } else {
          await button(desk, "Back to adverts").click();
        }
        await reachable(button(desk, "Publish"));
        await button(desk, "Messages").click();
        await button(desk, "Open conversation: Fixture conversation").click();
        const message = desk.getByLabel("YOUR MESSAGE");
        await message.fill("Local keyboard message draft.");
        await reachable(button(desk, "Send message"));
        await reachable(button(desk, "Close dialog"));
        await overflow();
        if (width === 320 && scale === 2) {
          await button(desk, "Send message").scrollIntoViewIfNeeded();
          await page.screenshot({
            path: info.outputPath("320px-200percent-message.png"),
          });
        }
        await close(page, desk);
        await button(page, "Discover homes").click();
        if (scale === 2)
          await page
            .locator("#t20-text-only")
            .evaluate((node) => node.remove());
      });
    }
  }
  expect(blocked).toEqual([]);
});

test("T20-TC02 opens a listing by keyboard, wraps both directions and restores focus", async ({
  page,
  context,
}) => {
  const blocked = await allowOwned(context);
  await page.goto("/");
  const action = button(page, first);
  await action.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "A closer look" });
  const dismiss = button(dialog, "Close dialog");
  const report = button(dialog, "Report a concern");
  await expect(dismiss).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(report).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(dismiss).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(button(dialog, "Save this home")).toBeFocused();
  await close(page, dialog);
  await expect(action).toBeFocused();
  expect(blocked).toEqual([]);
});

test("T20-TC03 enters, adjusts, removes, finishes and clears a search area by keyboard", async ({
  page,
  context,
}, info) => {
  const blocked = await allowOwned(context, false);
  execFileSync(
    process.env.E2E_PYTHON!,
    ["e2e/fixture.py", "boundaries", info.project.name],
    { stdio: "pipe" },
  );
  await page.goto("/");
  const mapButton = button(page, "Map view");
  await mapButton.focus();
  await page.keyboard.press("Enter");
  const coordinates = button(page, "Enter area coordinates");
  await keyActivate(page, coordinates);
  const dialog = page.getByRole("dialog", { name: "Search area coordinates" });
  const latitude = dialog.getByLabel("Latitude", { exact: true });
  const longitude = dialog.getByLabel("Longitude", { exact: true });
  const add = button(dialog, "Add vertex");
  const finish = button(dialog, "Use this area");
  await keyText(page, latitude, "91");
  await keyText(page, longitude, "19.9");
  await keyActivate(page, add);
  await expect(latitude).toHaveAccessibleDescription(/latitude from/);
  await keyText(page, latitude, "50.02");
  await keyActivate(page, add);
  for (const [lat, lon] of [
    ["50.02", "20.03"],
    ["50.11", "19.9"],
  ]) {
    await keyText(page, latitude, lat);
    await keyText(page, longitude, lon);
    await keyActivate(page, add);
  }
  await keyActivate(page, button(dialog, "Edit vertex 2"));
  await keyText(page, longitude, "20.09");
  await keyActivate(page, button(dialog, "Save vertex"));
  await keyActivate(page, button(dialog, "Remove vertex 3"));
  await keyActivate(page, finish);
  await expect(dialog.getByRole("alert")).toContainText(
    "3 and 64 distinct vertices",
  );
  await keyText(page, latitude, "50.11");
  await keyText(page, longitude, "19.9");
  await keyActivate(page, add);
  const filtered = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.origin === api &&
      url.pathname === "/v1/listings" &&
      url.searchParams.has("polygon")
    );
  });
  await keyActivate(page, finish);
  const response = await filtered;
  expect(response.ok()).toBeTruthy();
  expect(
    JSON.parse(new URL(response.url()).searchParams.get("polygon")!),
  ).toEqual([
    [19.9, 50.02],
    [20.09, 50.02],
    [19.9, 50.11],
  ]);
  const result = await response.json();
  expect(
    result.items.some((home: Listing) =>
      home.title.endsWith(`boundary ${info.project.name} good`),
    ),
  ).toBe(true);
  expect(
    result.items.some((home: Listing) =>
      home.title.endsWith(`boundary ${info.project.name} outside`),
    ),
  ).toBe(false);
  await expect(dialog).toHaveCount(0);
  await expect(button(page, "Edit area coordinates")).toBeFocused();
  const unfiltered = page.waitForResponse(
    (response) =>
      response.url().startsWith(`${api}/v1/listings?`) &&
      !new URL(response.url()).searchParams.has("polygon"),
  );
  await keyActivate(page, button(page, "Clear area"));
  expect((await unfiltered).ok()).toBe(true);
  await expect(coordinates).toBeVisible();
  expect(blocked).toEqual([]);
});

async function textContrast(locator: Locator) {
  return locator.evaluate((node) => {
    const rgb = (value: string) => value.match(/[\d.]+/g)!.map(Number);
    const color = rgb(getComputedStyle(node).color);
    let background = [255, 255, 255];
    for (
      let parent: Element | null = node;
      parent;
      parent = parent.parentElement
    ) {
      const fill = rgb(getComputedStyle(parent).backgroundColor);
      if (fill.length === 3 || fill[3] === 1) {
        background = fill;
        break;
      }
    }
    const luma = (values: number[]) =>
      values
        .slice(0, 3)
        .map((value) => {
          const s = value / 255;
          return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
        })
        .reduce(
          (sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index],
          0,
        );
    const [high, low] = [luma(color), luma(background)].sort((a, b) => b - a);
    return {
      foreground: color.slice(0, 3),
      background: background.slice(0, 3),
      ratio: (high + 0.05) / (low + 0.05),
    };
  });
}

test("T20-TC04 exposes listing states, labels and sufficient contrast in monochrome", async ({
  page,
  context,
}, info) => {
  const blocked = await allowOwned(context);
  await page.goto("/");
  await register(page, `t20-contrast-${info.project.name}@example.test`);
  await page.addStyleTag({
    content: "#root, .app-dialog { filter: grayscale(1); }",
  });
  await expect(button(page, "Discover homes")).toHaveAttribute("aria-current", "page");
  const listMode = button(page, "List view");
  const mapMode = button(page, "Map view");
  await expect(mapMode).toHaveAttribute("aria-pressed", String(info.project.name === "desktop"));
  await listMode.click();
  await expect(listMode).toHaveAttribute("aria-pressed", "true");
  await expect(mapMode).toHaveAttribute("aria-pressed", "false");
  const direct = page.getByText("DIRECT OFFER", { exact: true }).first();
  const agency = page.getByText("AGENCY", { exact: true }).first();
  const commission = page.getByText("Commission not stated", { exact: true });
  const seen = page.getByText("SEEN", { exact: true });
  const measurements: Record<
    string,
    Awaited<ReturnType<typeof textContrast>>
  > = {};
  for (const [label, control] of [
    ["direct", direct],
    ["agency", agency],
    ["commission", commission],
    ["seen", seen],
  ] as const) {
    await expect(control).toBeVisible();
    measurements[label] = await textContrast(control);
  }
  await button(page, `Save ${first}`).click();
  const saved = page.getByRole("button", {
    name: `Unsave ${first}`,
    pressed: true,
  });
  await expect(saved).toBeVisible();
  measurements.saved = await textContrast(
    saved.getByText("Saved", { exact: true }),
  );
  await button(page, `Compare ${second}`).click();
  const compared = page.getByRole("button", {
    name: `Compare ${second}`,
    pressed: true,
  });
  await expect(compared).toBeVisible();
  measurements.compared = await textContrast(
    compared.getByText("Compared", { exact: true }),
  );
  await button(page, "Saved homes").click();
  await expect(button(page, "Saved homes")).toHaveAttribute("aria-current", "page");
  await expect(button(page, "Discover homes")).not.toHaveAttribute("aria-current", "page");
  const delisted = page.getByText("DELISTED", { exact: true });
  await expect(delisted).toBeVisible();
  measurements.delisted = await textContrast(delisted);
  await button(page, "Notifications").click();
  const notifications = page.getByText("YOUR RENTAL UPDATES");
  measurements.notificationLabel = await textContrast(notifications);
  measurements.primaryButton = await textContrast(
    button(page, "Enable email alerts").getByText("Enable email alerts"),
  );
  const input = page.getByRole("textbox", { name: "City", exact: true });
  await button(page, "Discover homes").click();
  await input.focus();
  await page.keyboard.press("Tab");
  const focus = page.getByRole("textbox", {
    name: "Search neighborhood, street or keyword",
  });
  await expect(focus).toBeFocused();
  const outline = await focus.evaluate((node) => {
    const style = getComputedStyle(node);
    return {
      color: style.outlineColor,
      width: style.outlineWidth,
      style: style.outlineStyle,
    };
  });
  expect(outline).toEqual({
    color: "rgb(155, 63, 33)",
    width: "2px",
    style: "solid",
  });
  expect(
    Object.values(measurements).every((sample) => sample.ratio >= 4.5),
  ).toBe(true);
  await writeFile(
    info.outputPath("contrast.json"),
    JSON.stringify({ measurements, outline }, null, 2),
  );
  if (info.project.name === "mobile") {
    await commission.scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath("monochrome-card.png") });
  }
  expect(blocked).toEqual([]);
});

test("T20-TC05 defers unopened map and rental desk code and far-offscreen photos", async ({
  page,
  context,
}) => {
  const blocked = await allowOwned(context);
  await page.setViewportSize({ width: 390, height: 844 });
  const scripts = new Set<string>();
  const photos = new Set<string>();
  page.on("request", (request) => {
    const { pathname } = new URL(request.url());
    if (request.resourceType() === "script")
      scripts.add(pathname.split("/").at(-1)!);
    if (pathname.startsWith("/t20-image/")) photos.add(pathname);
  });
  await page.goto("/");
  await expect(button(page, first)).toBeVisible();
  await expect.poll(() => photos.has("/t20-image/001.png")).toBe(true);
  const lastPhoto = page.getByAltText("Photo of T20 home 024");
  await expect(lastPhoto).toHaveAttribute("loading", "lazy");
  await expect(lastPhoto).toHaveAttribute("width", "400");
  await expect(lastPhoto).toHaveAttribute("height", "210");
  expect(photos.has("/t20-image/024.png")).toBe(false);
  expect(
    [...scripts].some((name) =>
      /PropertyMap|leaflet|MarketplaceDialog/i.test(name),
    ),
  ).toBe(false);
  await lastPhoto.scrollIntoViewIfNeeded();
  await expect.poll(() => photos.has("/t20-image/024.png")).toBe(true);
  await button(page, "Map view").click();
  await expect(
    page.getByRole("region", { name: "Map of rental homes" }),
  ).toBeVisible();
  await expect
    .poll(() => [...scripts].some((name) => /leaflet/i.test(name)))
    .toBe(true);
  expect([...scripts].some((name) => /PropertyMap/i.test(name))).toBe(true);
  expect([...scripts].some((name) => /MarketplaceDialog/i.test(name))).toBe(
    false,
  );
  await register(page, `t20-lazy-${test.info().project.name}@example.test`);
  await button(page, "Account").click();
  await button(page, "My rental adverts").click();
  await expect(
    page.getByRole("dialog", { name: "Your rental desk." }),
  ).toBeVisible();
  expect([...scripts].some((name) => /MarketplaceDialog/i.test(name))).toBe(
    true,
  );
  expect(blocked).toEqual([]);
});

const coldProfile = {
  offline: false,
  latency: 150,
  downloadThroughput: 1_600_000 / 8,
  uploadThroughput: 750_000 / 8,
  connectionType: "cellular3g" as const,
};
const benchmarkViewport = { width: 390, height: 844 };
const warmLimitMs = 200;

async function afterTwoFrames(page: Page) {
  return page.evaluate(
    () =>
      new Promise<number>((resolve) =>
        requestAnimationFrame(() =>
          requestAnimationFrame(() => resolve(performance.now())),
        ),
      ),
  );
}

async function measuredEnter(
  page: Page,
  target: Locator,
  selector: string,
  text?: string,
) {
  await target.focus();
  await expect(target).toBeFocused();
  await page.evaluate(
    ({ selector, text }) => {
      const win = window as Window & { t20Measure?: Promise<number> };
      win.t20Measure = new Promise<number>((resolve, reject) => {
        const observer = new MutationObserver(check);
        let start = 0;
        const timeout = setTimeout(() => {
          observer.disconnect();
          reject(new Error("Measured UI state did not appear"));
        }, 10_000);
        function check() {
          const match = Array.from(document.querySelectorAll(selector)).find(
            (node) =>
              (!text || node.textContent === text) &&
              node.getClientRects().length > 0,
          );
          if (!match) return;
          observer.disconnect();
          clearTimeout(timeout);
          requestAnimationFrame(() =>
            requestAnimationFrame(() => resolve(performance.now() - start)),
          );
        }
        document.addEventListener(
          "keydown",
          () => {
            start = performance.now();
            observer.observe(document.documentElement, {
              childList: true,
              subtree: true,
              attributes: true,
              characterData: true,
            });
            check();
          },
          { capture: true, once: true },
        );
      });
    },
    { selector, text },
  );
  await page.keyboard.press("Enter");
  return page.evaluate(
    () => (window as Window & { t20Measure?: Promise<number> }).t20Measure!,
  );
}

test("T20-TC06 measures 100-result cold loads and 30 warm UI actions", async ({
  browser,
}, info) => {
  test.setTimeout(180_000);
  const cold = [];
  for (let i = 0; i < 3; i++) {
    const context = await browser.newContext({
      baseURL: web,
      viewport: benchmarkViewport,
    });
    try {
      const blocked = await allowOwned(context);
      const page = await context.newPage();
      const cdp = await context.newCDPSession(page);
      await cdp.send("Network.enable");
      await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
      await cdp.send("Network.emulateNetworkConditions", coldProfile);
      await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
      await page.goto("/");
      await expect(
        page.getByText("100 homes in Kraków", { exact: true }),
      ).toBeVisible();
      await expect(button(page, first)).toBeVisible();
      const resultFrameMs = await afterTwoFrames(page);
      const navigation = await page.evaluate(() => ({
        loadEventEndMs: (
          performance.getEntriesByType(
            "navigation",
          )[0] as PerformanceNavigationTiming
        ).loadEventEnd,
        firstContentfulPaintMs:
          performance.getEntriesByName("first-contentful-paint")[0]
            ?.startTime ?? null,
      }));
      cold.push({ resultFrameMs, ...navigation });
      expect(blocked).toEqual([]);
    } finally {
      await context.close();
    }
  }
  const context = await browser.newContext({
    baseURL: web,
    viewport: benchmarkViewport,
  });
  try {
    const blocked = await allowOwned(context);
    const page = await context.newPage();
    await page.goto("/");
    const filters = button(page, "More filters");
    const filterDialog = page.getByRole("dialog", {
      name: "A home that fits.",
    });
    const detailDialog = page.getByRole("dialog", { name: "A closer look" });
    await expect(button(page, first)).toBeVisible();
    await filters.click();
    await close(page, filterDialog);
    await button(page, first).click();
    await close(page, detailDialog);
    await afterTwoFrames(page);
    const samples: { action: string; ms: number }[] = [];
    for (let i = 0; i < 10; i++) {
      samples.push({
        action: "open filters",
        ms: await measuredEnter(
          page,
          filters,
          "dialog[open] h1",
          "A home that fits.",
        ),
      });
      await filterDialog
        .getByLabel("MIN RENT · PLN")
        .fill(String(4020 + i * 20));
      samples.push({
        action: "apply filters",
        ms: await measuredEnter(
          page,
          button(filterDialog, "Show matching homes"),
          '[aria-live="polite"]',
          `${99 - i} homes in Kraków`,
        ),
      });
      samples.push({
        action: "open listing",
        ms: await measuredEnter(
          page,
          button(page, homes[i + 1].title),
          "dialog[open] h1",
          "A closer look",
        ),
      });
      await close(page, detailDialog);
    }
    const sorted = samples.map((sample) => sample.ms).sort((a, b) => a - b);
    const p95Ms = sorted[Math.ceil(sorted.length * 0.95) - 1];
    const report = {
      timestamp: new Date().toISOString(),
      browser: browser.version(),
      viewport: benchmarkViewport,
      fixtureResults: homes.length,
      pageSize: 24,
      coldProfile: { ...coldProfile, cpuRate: 4 },
      cold,
      warmLimitMs,
      p95Ms,
      pass: p95Ms <= warmLimitMs,
      samples,
    };
    await writeFile(
      info.outputPath("web-performance.json"),
      JSON.stringify(report, null, 2),
    );
    expect(blocked).toEqual([]);
    expect(samples).toHaveLength(30);
    expect(p95Ms, "Warm interaction p95 in milliseconds").toBeLessThanOrEqual(
      warmLimitMs,
    );
  } finally {
    await context.close();
  }
});
