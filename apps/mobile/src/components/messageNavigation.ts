type Composer = { measureLayout: (relative: any, callback: (x: number, y: number, ...rest: number[]) => void) => void };
export function jumpToComposerSafely(composer: Composer, content: unknown,
  viewport: { scrollTo: (options: { y: number; animated: boolean }) => void },
  input: { focus: () => void }, current: () => boolean) {
  composer.measureLayout(content, (_x, y) => {
    if (!current()) return;
    viewport.scrollTo({ y: Math.max(0, y - 12), animated: false });
    requestAnimationFrame(() => { if (current()) input.focus(); });
  });
}
