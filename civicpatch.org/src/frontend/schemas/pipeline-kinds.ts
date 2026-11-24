// Mirrors PipelineRunKind in shared/utils/statuses.py: the three pipelines, in run order.
export const PipelineKind = {
  GOVERNING_LAW: "governing_law_collector",
  ORGANIZATIONS: "organizations_collector",
  PEOPLE: "people_collector",
} as const;

export type PipelineKind = (typeof PipelineKind)[keyof typeof PipelineKind];

export const PIPELINE_KINDS: PipelineKind[] = [
  PipelineKind.GOVERNING_LAW,
  PipelineKind.ORGANIZATIONS,
  PipelineKind.PEOPLE,
];

export const PIPELINE_LABELS: Record<PipelineKind, string> = {
  [PipelineKind.GOVERNING_LAW]: "Governing law",
  [PipelineKind.ORGANIZATIONS]: "Organizations",
  [PipelineKind.PEOPLE]: "People",
};
