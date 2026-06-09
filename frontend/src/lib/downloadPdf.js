/**
 * downloadPdf.js — authenticated PDF download helper.
 *
 * Backend PDF endpoints require Authorization: Bearer <token>. window.open(url)
 * opens a new tab without that header → 401. This helper does an authenticated
 * axios GET, wraps the response in a Blob, and triggers a download via an
 * anchor click. axios already has the auth interceptor (AuthContext L10-L34),
 * so the token is attached automatically.
 *
 * @param {object} axiosInstance - the project's axios (with auth interceptor)
 * @param {string} url           - absolute or API-relative URL to GET
 * @param {string} filename      - filename for the downloaded file
 * @returns {Promise<{ok: boolean, error?: string, status?: number}>}
 */
export async function downloadPdf(axiosInstance, url, filename) {
  try {
    const res = await axiosInstance.get(url, { responseType: "blob" });
    const blob = new Blob([res.data], { type: "application/pdf" });
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    // Revoke after a tick so the browser commits the download
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    return { ok: true };
  } catch (e) {
    const status = e?.response?.status;
    let detail = "";
    if (e?.response?.data) {
      // If backend returned a JSON error, try to read it (response is a blob)
      try {
        const text = await e.response.data.text();
        const parsed = JSON.parse(text);
        detail = parsed?.detail || text.slice(0, 200);
      } catch {
        detail = String(e.message || "PDF download failed");
      }
    } else {
      detail = String(e?.message || "PDF download failed");
    }
    return { ok: false, status, error: detail };
  }
}
