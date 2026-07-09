export function shouldRenderVerifyCta({
  isLoggedIn,
  toReviewCount,
}: {
  isLoggedIn: boolean;
  toReviewCount: number;
}): boolean {
  return isLoggedIn && toReviewCount > 0;
}
