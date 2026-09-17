// Every WebSocket pubsub channel the app subscribes to is declared here. Mirrors
// lib/pubsub.py on the backend — the two languages keep their own copy since neither
// can import the other, but each side names its channels in exactly one place.

// Every message on here is a publish today (the backend only announces live-worthy activity
// types, see LIVE_ACTIVITY_TYPES in shared/utils/statuses.py, and publishes are the only one
// with a listener) — so nothing here needs to check the message's own `type`.
export const ACTIVITY_CHANNEL = "activity";

export function pipelineRunStatusChannel(jurisdictionOcdid: string): string {
  return `pipeline_run_status:${jurisdictionOcdid}`;
}
