export function shouldRenderVerifyCta({ toReviewCount }: { toReviewCount: number }): boolean {
  return toReviewCount > 0;
}
