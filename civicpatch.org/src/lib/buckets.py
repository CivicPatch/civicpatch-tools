"""Which object-storage buckets this environment writes to.

Read from the environment, defaulting to the NONPROD buckets. Production must name its own.

The direction matters. Defaulting to production would mean a deployment that forgets these
writes to production storage silently, which is the failure cp-infrastructure's base manifest
already designs against ("an overlay that forgets one fails loud instead of silently hitting
prod"). Defaulting to nonprod makes the mistake harmless instead: the worst case is a
production deployment writing where nobody is looking, which is visible and recoverable.

They were constants until 2026-08-17, which meant a dev publish copied images straight into the
bucket production serves: the repo was isolated to test-open-data, the object storage was not.

Setting these is only half of it — the credential has to be scoped to the buckets named here,
or every call 403s.
"""

import os

ARTIFACTS = os.environ.get("STORAGE_ARTIFACTS_BUCKET", "civicpatch-artifacts-nonprod")
CDN = os.environ.get("STORAGE_CDN_BUCKET", "civicpatch-nonprod")
DEBUG = os.environ.get("STORAGE_DEBUG_BUCKET", "civicpatch-debug-nonprod")
