import { useEffect, useState } from "haunted";
import {
  readJurisdictionParam,
  writeJurisdictionParam,
} from "../../utils/jurisdiction-param.js";

export interface JurisdictionSelection {
  jurisdiction_ocdid: string;
  display_name?: string | null;
  parent_names?: string[];
}

// The open modal and the URL param are one piece of state; keeping them together stops
// them drifting apart. A link, a refresh, the back button and a click all land here.
export function useJurisdictionModal() {
  const [selection, setSelection] = useState<JurisdictionSelection | null>(null);

  const fromParam = (): JurisdictionSelection | null => {
    const ocdid = readJurisdictionParam();
    return ocdid ? { jurisdiction_ocdid: ocdid, parent_names: [] } : null;
  };

  // A pasted link with ?jurisdiction=… opens the modal already populated.
  useEffect(() => {
    const initial = fromParam();
    if (initial) setSelection(initial);
  }, []);

  // Back/forward should close or reopen the modal, not leave the page.
  useEffect(() => {
    const handler = () => setSelection(fromParam());
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, []);

  const open = (next: JurisdictionSelection) => {
    setSelection(next);
    writeJurisdictionParam(next.jurisdiction_ocdid);
  };

  const close = () => {
    setSelection(null);
    writeJurisdictionParam(null);
  };

  return { selection, open, close };
}
