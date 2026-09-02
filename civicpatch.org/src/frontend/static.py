import os

from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

# Vite writes a content hash into every filename under build/assets, so one of those
# URLs can never serve different bytes and the browser never has to ask again.
HASHED_ASSET_PREFIX = "/build/assets/"
IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"


def is_hashed_asset(path: str, root_path: str) -> bool:
    """Starlette leaves the mount prefix on scope["path"] and reports it as root_path,
    so the prefix has to come off before the path means anything relative to the mount."""
    return path.removeprefix(root_path).startswith(HASHED_ASSET_PREFIX)


class HashedAssetStaticFiles(StaticFiles):
    """Serves src/frontend, marking the content-hashed build output immutable.

    Only the hashed files get a header. Everything else here keeps its original
    name across deploys, so it is left to revalidate as before.
    """

    def file_response(
        self,
        full_path: str | os.PathLike[str],
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        if is_hashed_asset(scope["path"], scope.get("root_path", "")):
            response.headers["Cache-Control"] = IMMUTABLE_CACHE_CONTROL
        return response
