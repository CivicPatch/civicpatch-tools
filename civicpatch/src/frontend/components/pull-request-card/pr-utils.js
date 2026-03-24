export const pullRequestUrlToNumber = (url) => {
  if (!url) return null;
  const parts = url.split("/");
  const num = parseInt(parts[parts.length - 1], 10);
  return isNaN(num) ? null : num;
};
