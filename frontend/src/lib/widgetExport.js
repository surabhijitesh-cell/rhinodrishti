/**
 * Widget export to PNG via html2canvas.
 *
 * html2canvas handles complex CSS (Recharts tooltips, gradients, SVG with
 * CSS-variable colors) more reliably than native SVG serialization, which
 * was producing blank / mis-rasterized output for Recharts widgets.
 *
 * Dynamic import keeps html2canvas out of the main bundle until export used.
 */

export async function exportWidgetAsPNG(containerEl, filename = "widget.png") {
  if (!containerEl) throw new Error("No container");

  // Verify content is visible — html2canvas can't capture display:none nodes
  const rect = containerEl.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) {
    throw new Error("Widget has zero dimensions — scroll it into view first");
  }

  let html2canvas;
  try {
    const mod = await import("html2canvas");
    html2canvas = mod.default || mod;
  } catch (e) {
    throw new Error("html2canvas not installed — run `npm install` in frontend/");
  }

  // Resolve background color from app theme — dark canvas matches app aesthetic
  const bg = getComputedStyle(document.body).backgroundColor || "#0a0f0a";

  const canvas = await html2canvas(containerEl, {
    backgroundColor: bg,
    scale: 2,               // 2x for retina-quality output
    useCORS: true,          // allow cross-origin tile / icon fetches
    logging: false,
    // Walk up to grab the Card title too if container is the CardContent
    onclone: (clonedDoc, clonedEl) => {
      // Force monospace font + visible text so chart axis labels render
      clonedEl.style.fontFamily = "'JetBrains Mono', monospace";
      // Recharts uses CSS vars sometimes — inline fallback colors
      const labels = clonedEl.querySelectorAll(".recharts-text, .recharts-cartesian-axis-tick-value");
      labels.forEach(l => { l.style.fill = "#d4d4d4"; });
    },
  });

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) return reject(new Error("Canvas-to-blob failed"));
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      resolve();
    }, "image/png");
  });
}
