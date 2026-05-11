export function buildCoverageMap(
  dashboardData: Record<string, any> | null,
  selectedState: string,
): Record<string, number> {
  if (!dashboardData || !selectedState) return {};
  const notScraped: string[] =
    dashboardData?.states?.[selectedState]?.locality_gaps?.not_yet_scraped ?? [];
  const result: Record<string, number> = {};
  for (const ocdid of notScraped) {
    result[ocdid] = 0;
  }
  return result;
}
