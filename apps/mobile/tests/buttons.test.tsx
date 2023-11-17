import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
vi.mock("react-native", async () => vi.importActual("react-native-web"));
vi.mock("react-native-safe-area-context", () => ({ SafeAreaView: "div" }));
vi.mock("lucide-react-native/icons/check", () => ({ default: "span" }));
vi.mock("lucide-react-native/icons/x", () => ({ default: "span" }));
import { Button } from "../src/components/UI";

describe("shared Button states", () => {
  it("makes a busy operation unavailable and names the progress", () => {
    const html = renderToStaticMarkup(<Button busy busyLabel="Saving changes…" onPress={() => {}}>Save</Button>);
    expect(html).toContain('aria-busy="true"');
    expect(html).toContain('aria-disabled="true"');
    expect(html).toContain('aria-label="Saving changes…"');
    expect(html).toContain('tabindex="-1"');
  });
  it("keeps legacy outlined consumers and explicit destructive labels usable", () => {
    const html = renderToStaticMarkup(<Button outline onPress={() => {}}>Cancel</Button>);
    expect(html).toContain("Cancel");
    expect(html).not.toContain('aria-disabled="true"');
    expect(renderToStaticMarkup(<Button variant="danger" onPress={() => {}}>Delete saved search</Button>)).toContain("Delete saved search");
  });
});
