// Metadata Doctor panel.
// Plugin API v1 panels are deliberately read-only. This gives Metadata Doctor
// a visible home in Settings > Plugins and explains where diagnosis is triggered.
const root = document.body;
root.innerHTML = `
<style>
  :root { color-scheme: dark; font-family: system-ui, sans-serif; }
  body { margin: 0; padding: 18px; background: transparent; color: #e7e9ee; }
  .card { border: 1px solid rgba(255,255,255,.12); border-radius: 14px; padding: 18px; }
  h1 { margin: 0 0 6px; font-size: 20px; }
  p { color: #aeb4c0; line-height: 1.45; }
  .status { display:inline-block; padding:4px 8px; border-radius:999px; background:rgba(252,163,17,.15); color:#fca311; font-size:12px; font-weight:700; }
  code { font-size: 12px; }
</style>
<div class="card">
  <span class="status">Metadata Doctor installed</span>
  <h1>Metadata Doctor</h1>
  <p>The plugin is loaded and ready.</p>
  <p><strong>Trigger:</strong> open an album's <em>Read-only identity desk</em> and use the Metadata Doctor action there.</p>
  <p>If that action is not present, your DroppedNeedle host does not yet include the Identify Desk integration patch. Plugin API v1 does not allow this sandboxed panel to start identity repair itself.</p>
</div>
`;
