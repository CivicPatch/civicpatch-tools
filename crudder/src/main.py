import datetime
import os
from contextlib import asynccontextmanager
import urllib

import yaml
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Form,
    HTTPException,
    Request,
    Security,
    UploadFile,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import APIKeyCookie, APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_sso.sso.base import OpenID
from fastapi_sso.sso.github import GithubSSO
from jose import jwt  # pip install python-jose[cryptography]

import github_service
from auth import is_authorized
from civicpatch import id_utils
from database import (
    create_api_key,
    get_api_keys_for_user,
    get_jurisdiction_people,
    get_user_details,
    maybe_insert_user,
    pool,
    revoke_api_key,
    update_user_detail,
    user_is_approved,
    get_jurisdiction_states,
    search_jurisdictions
)
from github_sync_service import GitDatabaseSync
from schemas import Jurisdiction
from storage_service import upload_file_to_storage

# Only purpose is to manage users, their API keys, and move data from 3rd party servers
# to GitHub Actions.
# Update 2025/10/24
# Goal has expanded to -- whatever the civicpatch servers need to sync data
# to and from the open-data repo
# Ref: https://github.com/tomasvotava/fastapi-sso/blob/master/docs/how-to-guides/use-with-fastapi-security.md

INSTANCE_URL = os.getenv("INSTANCE_URL", "http://127.0.0.1:8001")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_CALLBACK_URL = f"{INSTANCE_URL}/auth/github/callback"
CRUDDER_DB_URL = os.getenv("CRUDDER_DB_URL")

MAINTAINER_EMAIL = os.getenv("MAINTAINER_EMAIL")
APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT")
GITHUB_WORKFLOW_TOKEN = os.getenv("GITHUB_WORKFLOW_TOKEN")
DATABASE_HASH_KEY = os.getenv("DATABASE_HASH_KEY")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT")
STORAGE_ACCESS_KEY_ID = os.getenv("STORAGE_ACCESS_KEY_ID")
STORAGE_SECRET_ACCESS_KEY = os.getenv("STORAGE_SECRET_ACCESS_KEY")

# db_connection = sqlite3.connect("data/database.db")
# db_cursor = db_connection.cursor()

if not all(
    [
        MAINTAINER_EMAIL,
        GITHUB_CLIENT_ID,
        GITHUB_CLIENT_SECRET,
        CRUDDER_DB_URL,
        APP_ENVIRONMENT,
        GITHUB_WORKFLOW_TOKEN,
        DATABASE_HASH_KEY,
        JWT_SECRET_KEY,
        STORAGE_ENDPOINT,
        STORAGE_ACCESS_KEY_ID,
        STORAGE_SECRET_ACCESS_KEY,
    ]
):
    missing_vars = [
        var
        for var, val in {
            "MAINTAINER_EMAIL": MAINTAINER_EMAIL,
            "GITHUB_CLIENT_ID": GITHUB_CLIENT_ID,
            "GITHUB_CLIENT_SECRET": GITHUB_CLIENT_SECRET,
            "CRUDDER_DB_URL": CRUDDER_DB_URL,
            "APP_ENVIRONMENT": APP_ENVIRONMENT,
            "GITHUB_WORKFLOW_TOKEN": GITHUB_WORKFLOW_TOKEN,
            "DATABASE_HASH_KEY": DATABASE_HASH_KEY,
            "JWT_SECRET_KEY": JWT_SECRET_KEY,
            "STORAGE_ENDPOINT": STORAGE_ENDPOINT,
            "STORAGE_ACCESS_KEY_ID": STORAGE_ACCESS_KEY_ID,
            "STORAGE_SECRET_ACCESS_KEY": STORAGE_SECRET_ACCESS_KEY,
        }.items()
        if not val
    ]
    print(f"Missing environment variables: {', '.join(missing_vars)}")
    raise ValueError("One or more required environment variables are not set.")

github_sso = GithubSSO(
    client_id=GITHUB_CLIENT_ID,
    client_secret=GITHUB_CLIENT_SECRET,
    redirect_uri=GITHUB_CALLBACK_URL,
)

VALID_STATES = [
    "al",
    "ak",
    "az",
    "ar",
    "ca",
    "co",
    "ct",
    "de",
    "fl",
    "ga",
    "hi",
    "id",
    "il",
    "in",
    "ia",
    "ks",
    "ky",
    "la",
    "me",
    "md",
    "ma",
    "mi",
    "mn",
    "ms",
    "mo",
    "mt",
    "ne",
    "nv",
    "nh",
    "nj",
    "nm",
    "ny",
    "nc",
    "nd",
    "oh",
    "ok",
    "or",
    "pa",
    "ri",
    "sc",
    "sd",
    "tn",
    "tx",
    "ut",
    "vt",
    "va",
    "wa",
    "wv",
    "wi",
    "wy",
]


@asynccontextmanager
async def lifespan(instance: FastAPI):
    await pool.open()
    yield
    await pool.close()


app = FastAPI(
    title="Crudder API",
    description="A starter FastAPI application for CRUD operations.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


def is_production() -> bool:
    return APP_ENVIRONMENT.lower() == "production"


async def get_logged_user(cookie: str = Security(APIKeyCookie(name="token"))) -> OpenID:
    """Get user's JWT stored in cookie 'token', parse it and return the user's OpenID."""
    try:
        claims = jwt.decode(cookie, key=JWT_SECRET_KEY, algorithms=["HS256"])
        return OpenID(**claims["pld"])
    except Exception as error:
        raise HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        ) from error


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home(request: Request):
    try:
        user = await get_logged_user(request.cookies.get("token"))
        provider_user_id = user.id
        api_keys = await get_api_keys_for_user(user.provider, provider_user_id)
        approved_user = await user_is_approved(user.provider, provider_user_id)
        user_details = await get_user_details(user.provider, provider_user_id)
    except HTTPException:
        user = None
        api_keys = []
        approved_user = False
        user_details = None

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "user": user,
            "api_keys": api_keys,
            "approved_user": approved_user,
            "maintainer_email": MAINTAINER_EMAIL,
            "user_details": user_details,
        },
    )


api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


@app.post(
    "/api/github_intake",
    summary="Upload zip file containing municipal data",
    description="Accepts a zip file containing municipal data and processes it",
)
async def github_intake(
    file: UploadFile,
    authorization: str = Security(api_key_header),
    request_id: str = Form(...),
    jurisdiction_id: str = Form(...),
):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    api_key = authorization.strip()
    server_detail, error_string = await is_authorized(api_key)
    if error_string:
        raise HTTPException(status_code=401, detail=error_string)

    # Check file type
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are accepted")
    if file.content_type not in ["application/zip", "application/x-zip-compressed"]:
        raise HTTPException(status_code=400, detail="Invalid content type for zip file")

    # Now you have access to the parameters
    print(f"Processing intake for {request_id} - {jurisdiction_id}")

    zip_file_url = await upload_file_to_storage(
        STORAGE_ENDPOINT,
        STORAGE_ACCESS_KEY_ID,
        STORAGE_SECRET_ACCESS_KEY,
        "crudder",
        file,
        with_presigned_url=True,
    )

    github_service.trigger_github_data_intake_workflow(
        GITHUB_WORKFLOW_TOKEN,
        server_detail["user_email"],
        server_detail["server_url"],
        request_id=request_id,
        jurisdiction_id=jurisdiction_id,
        zip_file_url=zip_file_url,
    )

    return {
        "filename": file.filename,
        "status": "uploaded",
        "zip_file_url": zip_file_url,
        "metadata": {"request_id": request_id, "jurisdiction_id": jurisdiction_id},
    }


@app.get("/api_keys", response_class=HTMLResponse, include_in_schema=False)
async def api_keys_page(request: Request):
    try:
        user = await get_logged_user(request.cookies.get("token"))
        # Fetch user's API keys from database
        provider_user_id = user.id

        api_keys = await get_api_keys_for_user("github", provider_user_id)

        return templates.TemplateResponse(
            request=request,
            name="api_keys.html",
            context={"user": user, "api_keys": api_keys},
        )
    except HTTPException:
        return RedirectResponse(url="/", status_code=302)


@app.post("/api_keys", include_in_schema=False)
async def post_api_keys(request: Request, user: OpenID = Depends(get_logged_user)):
    """Create new API key"""
    provider = user.provider
    provider_user_id = user.id

    approved_user = await user_is_approved(user.provider, provider_user_id)
    if not approved_user:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to create an API key. Please contact the maintainer.",
        )

    api_key = await create_api_key(provider, provider_user_id, DATABASE_HASH_KEY)

    return {"api_key": api_key}


@app.delete("/api_keys/{api_key_id}", include_in_schema=False)
async def delete_api_key(request: Request, api_key_id: str):
    await revoke_api_key(api_key_id)


@app.get("/auth/{provider}/login", include_in_schema=False)
async def login(provider: str):
    match provider:
        case "github":
            sso = github_sso
        case _:
            raise HTTPException(
                status_code=400, detail="Unsupported provider: {provider}"
            )

    async with sso:
        return await sso.get_login_redirect()


@app.get("/api/jurisdictions/available")
async def list_available_jurisdictions_endpoint(
    state: str,
    num_jurisdictions: int = 10,
    authorization: str = Security(api_key_header),
):
    if not authorization and not authorization.strip():
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if state.lower() not in VALID_STATES:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    _server_detail, error_string = await is_authorized(authorization)
    if error_string:
        raise HTTPException(status_code=401, detail=error_string)
    jurisdictions_file_content = github_service.get_github_file_contents(
        f"data_source/{state}/government_progress.yml"
    )
    if jurisdictions_file_content is None:
        raise HTTPException(status_code=404, detail="Could not find jurisdictions file")

    open_pull_requests = github_service.get_open_pull_requests(GITHUB_WORKFLOW_TOKEN)
    jurisdictions_data = yaml.safe_load(jurisdictions_file_content)
    jurisdictions = [
        Jurisdiction(
            id=j["jurisdiction"]["id"],
            name=j["jurisdiction"]["name"],
            url=j["jurisdiction"]["url"],
        )
        for j in jurisdictions_data["jurisdictions_by_id"].values()
        if j["jurisdiction"].get("url") and not j.get("updated_at")
    ]
    open_pull_request_ids = [pr.jurisdiction_id for pr in open_pull_requests]

    filtered_jurisdictions = [
        j for j in jurisdictions if j.id not in open_pull_request_ids
    ][:num_jurisdictions]
    return {"jurisdictions": filtered_jurisdictions}


@app.get("/api/jurisdictions/states")
async def get_jurisdiction_states_endpoint(
    authorization: str = Security(api_key_header),
):
    if not authorization and not authorization.strip():
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    _server_detail, error_string = await is_authorized(authorization)
    if error_string:
        raise HTTPException(status_code=403, detail=error_string)

    states = await get_jurisdiction_states()

    return {"total_items": len(states), "data": states}


@app.get("/api/jurisdictions/{state}/search")
async def get_jurisdictions_search_endpoint(
    state: str,
    limit: int = 0,
    skip: int = 0,
    authorization: str = Security(api_key_header),
):
    total_items, jurisdictions = await search_jurisdictions(state, limit, skip)

    next_skip = skip + len(jurisdictions)
    next_link = ""

    if next_skip < total_items:
        # Construct the next link URL (URL-encode the state if necessary, though usually not for path vars)
        query_params = urllib.parse.urlencode({"limit": limit, "skip": next_skip})
        next_link = f"/api/jurisdictions/{state}/search?{query_params}"

    self_query_params = urllib.parse.urlencode({"limit": limit, "skip": skip})
    self_link = f"/api/jurisdictions/{state}/search?{self_query_params}"

    return {
        "total_items": total_items,
        "skip": skip,
        "limit": limit,
        "data": jurisdictions,
        "links": {"next": next_link, "self": self_link},  # TODO!
    }

@app.get("/api/jurisdictions/{jurisdiction_ocdid_slug}/people")
async def get_jurisdiction_people_endpoint(
    jurisdiction_ocdid_slug: str,
    authorization: str = Security(api_key_header),
):
    if not authorization and not authorization.strip():
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    _server_detail, error_string = await is_authorized(authorization)
    if error_string:
        raise HTTPException(status_code=403, detail=error_string)

    jurisdiction_ocdid = id_utils.slug_to_jurisdiction_id(jurisdiction_ocdid_slug)
    people = await get_jurisdiction_people(jurisdiction_ocdid)

    return {
        "total_items": len(people),
        "data": people,
    }


# TODO: rbac perms needed
@app.post("/api/od_sync")
async def sync_people_endpoint(
    background_tasks: BackgroundTasks,
    authorization: str = Security(api_key_header),
):
    if not authorization and not authorization.strip():
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    _server_detail, error_string = await is_authorized(authorization)
    if error_string:
        raise HTTPException(status_code=403, detail=error_string)

    syncer = GitDatabaseSync()
    background_tasks.add_task(syncer.sync)

    return {"status": "running"}


@app.get("/auth/logout", include_in_schema=False)
async def logout():
    """Forget the user's session."""
    response = RedirectResponse(url="/")
    response.delete_cookie(key="token")
    return response


@app.get("/auth/{provider}/callback", include_in_schema=False)
async def login_callback(request: Request, provider: str):
    match provider:
        case "github":
            sso = github_sso
        case _:
            raise HTTPException(status_code=400, detail="Unsupported provider")

    """Process login and redirect the user to the protected endpoint."""
    async with sso:
        openid = await sso.verify_and_process(request)
        if not openid:
            raise HTTPException(status_code=401, detail="Authentication failed")
    # Create a JWT with the user's OpenID
    expiration = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
        days=1
    )
    token = jwt.encode(
        {"pld": openid.model_dump(), "exp": expiration, "sub": openid.id},
        key=JWT_SECRET_KEY,
        algorithm="HS256",
    )
    await maybe_insert_user(openid.provider, openid.id, openid.email)

    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="token",
        value=token,
        expires=expiration,
        httponly=True,
        secure=is_production(),
        samesite="lax",
    )
    return response


@app.post("/user_details", include_in_schema=False)
async def update_user_detail_endpoint(
    request: Request,
    server_url: str = Form(...),
    user: OpenID = Depends(get_logged_user),
):
    # Update the user's server_url in the database
    await update_user_detail(server_url, user.provider, user.id)

    return RedirectResponse(url="/", status_code=302)
