from datetime import timedelta

# Maximum wall-clock time for a single people-collector workflow execution.
# Covers the full run including any retry after human_approval.
PEOPLE_COLLECTOR_EXECUTION_TIMEOUT = timedelta(hours=2)
