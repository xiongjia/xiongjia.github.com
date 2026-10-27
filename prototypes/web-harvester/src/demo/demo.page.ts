/**
 * The self-check page.
 *
 * Kept as an inline string on purpose: no static-asset copying in `nest build`,
 * no external requests, no dependency on any real site's markup. When
 * `/demo/visit` fails, the browser engine is broken — not the page.
 */
export const DEMO_PAGE_HTML = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>harvester demo</title>
    <style>
      body { font-family: system-ui, sans-serif; margin: 32px; }
      #delayed { visibility: hidden; margin-top: 16px; }
      #status { margin-left: 8px; color: #0a7; }
    </style>
  </head>
  <body>
    <h1 id="title">harvester demo page</h1>

    <p>Stable, offline target used to verify the browser pipeline.</p>

    <p>
      <input id="name" placeholder="type here" />
      <button id="bump" type="button"
        onclick="document.getElementById('status').textContent = 'clicked'">
        click me
      </button>
      <span id="status">idle</span>
    </p>

    <svg width="120" height="40" role="img" aria-label="inline box">
      <rect x="1" y="1" width="118" height="38" fill="#0af" />
    </svg>

    <div id="delayed">delayed-ready</div>

    <script>
      setTimeout(function () {
        document.getElementById("delayed").style.visibility = "visible";
      }, 1000);
    </script>
  </body>
</html>
`;

/** Selectors the visitor waits on — kept next to the markup they describe. */
export const DEMO_SELECTORS = {
  title: "#title",
  delayed: "#delayed",
  bump: "#bump",
  status: "#status",
  name: "#name",
} as const;
