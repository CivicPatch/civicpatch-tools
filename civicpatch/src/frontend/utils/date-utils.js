export const dateStringToFriendly = (d) => {
    if (!d) return "";
    const p = new Date(d);
    if (isNaN(p)) return String(d);
    return `${String(p.getMonth() + 1).padStart(2, "0")}/${String(p.getDate()).padStart(2, "0")}/${p.getFullYear()}`;
}