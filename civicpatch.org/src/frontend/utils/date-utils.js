export const toLocalDateStr = (d) => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
};

export const dateStringToFriendly = (d) => {
    if (!d) return "";
    const p = new Date(d);
    if (isNaN(p)) return String(d);
    return `${String(p.getMonth() + 1).padStart(2, "0")}/${String(p.getDate()).padStart(2, "0")}/${p.getFullYear()}`;
}

export const durationBetween = (created_at, updated_at) => {
  if (!created_at || !updated_at) return "";
  const seconds = Math.floor((new Date(updated_at) - new Date(created_at)) / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  if (hours > 0) return `${hours}h ${minutes % 60}m`;
  if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
  return `${seconds}s`;
}