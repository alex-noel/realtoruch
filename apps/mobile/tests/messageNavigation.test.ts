import { afterEach, expect, it, vi } from "vitest";
import { jumpToComposerSafely } from "../src/components/messageNavigation";
afterEach(() => vi.unstubAllGlobals());
it("ignores native measurement after switching or closing a conversation", () => {
  let measured!: (x: number, y: number) => void, current = true;
  const viewport = { scrollTo: vi.fn() }, input = { focus: vi.fn() };
  const frame = vi.fn(); vi.stubGlobal("requestAnimationFrame", frame);
  jumpToComposerSafely({ measureLayout: (_, callback) => { measured = callback; } }, {}, viewport, input, () => current);
  current = false; measured(0, 500);
  expect(viewport.scrollTo).not.toHaveBeenCalled(); expect(frame).not.toHaveBeenCalled();
});
it("rechecks identity between scrolling and focusing", () => {
  let frame!: () => void, current = true;
  const viewport = { scrollTo: vi.fn() }, input = { focus: vi.fn() };
  vi.stubGlobal("requestAnimationFrame", (callback: () => void) => { frame = callback; });
  jumpToComposerSafely({ measureLayout: (_, callback) => callback(0, 500) }, {}, viewport, input, () => current);
  expect(viewport.scrollTo).toHaveBeenCalledWith({ y: 488, animated: false });
  current = false; frame(); expect(input.focus).not.toHaveBeenCalled();
});
