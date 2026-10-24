const NEXT_PARAM = "next";
const HOME_PATH = "/";

// Resolved the way the browser will (it drops tabs and newlines, so "/\t/host" is another site),
// then kept only if it stays on this origin.
export function afterLoginPath(search: string, origin: string): string {
  const next = new URLSearchParams(search).get(NEXT_PARAM);
  if (!next || !URL.canParse(next, origin)) return HOME_PATH;
  const target = new URL(next, origin);
  if (target.origin !== origin) return HOME_PATH;
  return target.pathname + target.search + target.hash;
}
