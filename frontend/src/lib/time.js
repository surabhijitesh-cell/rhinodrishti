// One way to show times across the app: always India Standard Time.

function toDate(value) {
  if (!value) return null;
  if (value instanceof Date) return isNaN(value) ? null : value;
  const s = String(value);
  // Server times without a zone are UTC.
  const withZone = /[zZ]|[+-]\d\d:?\d\d$/.test(s) || /^\d{4}-\d\d-\d\d$/.test(s) ? s : `${s}Z`;
  const d = new Date(withZone);
  return isNaN(d) ? null : d;
}

export function formatIST(value, { dateOnly = false } = {}) {
  const d = toDate(value);
  if (!d) return "";
  const opts = dateOnly
    ? { timeZone: "Asia/Kolkata", day: "numeric", month: "short", year: "numeric" }
    : { timeZone: "Asia/Kolkata", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false };
  return `${d.toLocaleString("en-IN", opts)}${dateOnly ? "" : " IST"}`;
}

export function timeAgo(value, now = Date.now()) {
  const d = toDate(value);
  if (!d) return "";
  const mins = Math.max(0, Math.round((now - d.getTime()) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}
