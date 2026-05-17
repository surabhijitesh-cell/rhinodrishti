/**
 * Widget export utilities.
 *
 * Strategy: Recharts renders SVG. We serialize the first <svg> inside the
 * widget container, rasterize it onto a Canvas, and download as PNG.
 *
 * Non-SVG widgets (the heatmap is HTML) fall back to a notice.
 */

export function exportWidgetAsPNG(containerEl, filename = "widget.png") {
  if (!containerEl) return Promise.reject(new Error("No container"));

  const svg = containerEl.querySelector("svg");
  if (!svg) {
    return Promise.reject(new Error("HTML widget — PNG export not supported. Use browser screenshot."));
  }

  const clone = svg.cloneNode(true);
  // Ensure white-on-dark background for legibility (matches app)
  clone.setAttribute("style", `background:#0a0f0a;font-family:'JetBrains Mono',monospace;${clone.getAttribute("style") || ""}`);

  // Inline computed colors for elements that rely on CSS vars
  const rect = svg.getBoundingClientRect();
  const width  = Math.max(rect.width, 600);
  const height = Math.max(rect.height, 300);
  clone.setAttribute("width", width);
  clone.setAttribute("height", height);

  const xml = new XMLSerializer().serializeToString(clone);
  const svg64 = btoa(unescape(encodeURIComponent(xml)));
  const dataUri = `data:image/svg+xml;base64,${svg64}`;

  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width  = width  * 2;  // 2x for retina
      canvas.height = height * 2;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#0a0f0a";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.scale(2, 2);
      ctx.drawImage(img, 0, 0, width, height);
      try {
        const png = canvas.toDataURL("image/png");
        const a = document.createElement("a");
        a.href = png;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        resolve();
      } catch (e) { reject(e); }
    };
    img.onerror = (e) => reject(e);
    img.src = dataUri;
  });
}
