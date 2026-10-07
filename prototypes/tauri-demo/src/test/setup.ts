/**
 * jsdom gaps that the components rely on.
 *
 * - `ResizeObserver` does not exist in jsdom, and Recharts' `ResponsiveContainer`
 *   (which shadcn's `ChartContainer` wraps) needs it to learn its size. Without
 *   the shim every chart renders zero SVGs; with it the charts render with real
 *   geometry, so tests can assert on `.recharts-surface` / `.recharts-curve`.
 * - `window.matchMedia` is used by the theme toggle to pick the initial theme.
 */

const CHART_WIDTH = 800;
const CHART_HEIGHT = 400;

function fakeRect(width: number, height: number): DOMRectReadOnly {
  const rect = { width, height, top: 0, left: 0, bottom: height, right: width, x: 0, y: 0 };
  return { ...rect, toJSON: () => rect };
}

class ResizeObserverStub implements ResizeObserver {
  constructor(private readonly callback: ResizeObserverCallback) {}

  observe(target: Element): void {
    this.callback(
      [
        {
          target,
          contentRect: fakeRect(CHART_WIDTH, CHART_HEIGHT),
          borderBoxSize: [],
          contentBoxSize: [],
          devicePixelContentBoxSize: [],
        },
      ],
      this,
    );
  }

  unobserve(): void {}

  disconnect(): void {}
}

globalThis.ResizeObserver = ResizeObserverStub;

if (!window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string): MediaQueryList => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}
