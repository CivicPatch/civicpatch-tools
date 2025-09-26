import os
import io
import datetime
from fastapi import FastAPI, Request, Security, HTTPException, Depends, Form, Header, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import APIKeyCookie, APIKeyHeader 
from fastapi_sso.sso.github import GithubSSO
from fastapi_sso.sso.base import OpenID
import sqlite3
from database import maybe_init_db, maybe_insert_user, create_api_key, get_api_keys_for_user, revoke_api_key, get_user_details, get_server_detail_by_active_api_key
from storage_service import upload_file_to_storage
from github_service import trigger_github_data_intake_workflow

from jose import jwt  # pip install python-jose[cryptography]
import os

# Only purpose is to manage users, their API keys, and move data from 3rd party servers
# to GitHub Actions.
# Ref: https://github.com/tomasvotava/fastapi-sso/blob/master/docs/how-to-guides/use-with-fastapi-security.md

INSTANCE_URL = os.getenv("INSTANCE_URL", "http://127.0.0.1:8001")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_CALLBACK_URL = os.getenv("GITHUB_CALLBACK_URL", f"{INSTANCE_URL}/auth/github/callback")
APPROVED_GITHUB_PROVIDER_USER_IDS = os.getenv("APPROVED_GITHUB_PROVIDER_USER_IDS", "").split(",")
MAINTAINER_EMAIL = os.getenv("MAINTAINER_EMAIL")
APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT")
GITHUB_WORKFLOW_TOKEN = os.getenv("GITHUB_WORKFLOW_TOKEN")
DATABASE_HASH_KEY = os.getenv("DATABASE_HASH_KEY")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT")
STORAGE_ACCESS_KEY_ID = os.getenv("STORAGE_ACCESS_KEY_ID")
STORAGE_SECRET_ACCESS_KEY = os.getenv("STORAGE_SECRET_ACCESS_KEY")

db_connection = sqlite3.connect('data/database.db')
db_cursor = db_connection.cursor()
maybe_init_db(db_connection, db_cursor)

if not all([
    APPROVED_GITHUB_PROVIDER_USER_IDS, 
    MAINTAINER_EMAIL, 
    GITHUB_CLIENT_ID, 
    GITHUB_CLIENT_SECRET, 
    APP_ENVIRONMENT, 
    GITHUB_WORKFLOW_TOKEN, 
    DATABASE_HASH_KEY,
    JWT_SECRET_KEY,
    STORAGE_ENDPOINT,
    STORAGE_ACCESS_KEY_ID,
    STORAGE_SECRET_ACCESS_KEY
    ]):
    missing_vars = [var for var, val in {
        "APPROVED_GITHUB_PROVIDER_USER_IDS": APPROVED_GITHUB_PROVIDER_USER_IDS,
        "MAINTAINER_EMAIL": MAINTAINER_EMAIL,
        "GITHUB_CLIENT_ID": GITHUB_CLIENT_ID,
        "GITHUB_CLIENT_SECRET": GITHUB_CLIENT_SECRET,
        "APP_ENVIRONMENT": APP_ENVIRONMENT,
        "GITHUB_WORKFLOW_TOKEN": GITHUB_WORKFLOW_TOKEN,
        "DATABASE_HASH_KEY": DATABASE_HASH_KEY,
        "JWT_SECRET_KEY": JWT_SECRET_KEY,
        "STORAGE_ENDPOINT": STORAGE_ENDPOINT,
        "STORAGE_ACCESS_KEY_ID": STORAGE_ACCESS_KEY_ID,
        "STORAGE_SECRET_ACCESS_KEY": STORAGE_SECRET_ACCESS_KEY
    }.items() if not val]
    print(f"Missing environment variables: {', '.join(missing_vars)}")
    raise ValueError("One or more required environment variables are not set.")

github_sso = GithubSSO(client_id=GITHUB_CLIENT_ID, client_secret=GITHUB_CLIENT_SECRET, redirect_uri=GITHUB_CALLBACK_URL)

app = FastAPI(
    title="Crudder API",
    description="A starter FastAPI application for CRUD operations.",
    version="1.0.0"
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
        raise HTTPException(status_code=401, detail="Invalid authentication credentials") from error

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home(request: Request):
    try:
        user = await get_logged_user(request.cookies.get("token"))
        provider_user_id = user.id
        api_keys = get_api_keys_for_user(db_cursor, user.provider, provider_user_id)
        approved_user = user and user.id in APPROVED_GITHUB_PROVIDER_USER_IDS
        user_details = get_user_details(db_cursor, user.provider, provider_user_id)
    except HTTPException:
        user = None
        api_keys = []
        approved_user = False
        user_details = None

    return templates.TemplateResponse(
        request=request, name="index.html", context={
            "user": user, "api_keys": api_keys, "approved_user": approved_user,
            "maintainer_email": MAINTAINER_EMAIL, "user_details": user_details
        }
    )

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

@app.post("/api/github_intake", 
    summary="Upload zip file containing municipal data",
    description="Accepts a zip file containing municipal data and processes it")
async def github_intake(
    file: UploadFile,
    authorization: str = Security(api_key_header),  # Changed this line
    request_id: str = Form(...),
    jurisdiction_id: str = Form(...)
):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    api_key = authorization.strip()
    server_detail = get_server_detail_by_active_api_key(db_cursor, DATABASE_HASH_KEY, api_key)

    if not server_detail:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    if not server_detail["user_email"]:
        raise HTTPException(status_code=401, detail="No user email associated with the provided API key. Do you have an active API key & user email?")
    
    if not server_detail["server_url"]:
        raise HTTPException(status_code=401, detail="No server URL associated with the provided API key. Please set your CivicPatch Server URL in the user details page.")

    # Check file type
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are accepted")
    if file.content_type not in ["application/zip", "application/x-zip-compressed"]:
        raise HTTPException(status_code=400, detail="Invalid content type for zip file")
    
    # Now you have access to the parameters
    print(f"Processing intake for {request_id} - {jurisdiction_id}")

    zip_url = await upload_file_to_storage(
        STORAGE_ENDPOINT,
        STORAGE_ACCESS_KEY_ID,
        STORAGE_SECRET_ACCESS_KEY,
        "crudder",
        file,
        with_presigned_url=True
    )

    # Use the parameters in your workflow trigger
    trigger_github_data_intake_workflow(
        GITHUB_WORKFLOW_TOKEN, 
        server_detail["user_email"], 
        server_detail["server_url"], 
        zip_url
    )

    return {
        "filename": file.filename, 
        "status": "uploaded", 
        "zip_url": zip_url,
        "metadata": {
            "request_id": request_id,
            "jurisdiction_id": jurisdiction_id
        }
    }

@app.get("/api_keys", response_class=HTMLResponse, include_in_schema=False)
async def api_keys_page(request: Request):
    try:
        user = await get_logged_user(request.cookies.get("token"))
        print(user)
        # Fetch user's API keys from database
        provider_user_id = user.id

        api_keys = get_api_keys_for_user(db_cursor, "github", provider_user_id)

        return templates.TemplateResponse(
            request=request,
            name="api_keys.html",
            context={
                "user": user,
                "api_keys": api_keys
            }
        )
    except HTTPException:
        return RedirectResponse(url="/", status_code=302)

def can_create_api_key(provider, provider_user_id, approved_github_user_ids):
    if provider != "github":
        return False
    return provider_user_id in approved_github_user_ids

@app.post("/api_keys", include_in_schema=False)
async def post_api_keys(request: Request, user: OpenID = Depends(get_logged_user)):
    """Create new API key"""
    provider = user.provider
    provider_user_id = user.id

    if not can_create_api_key(provider, provider_user_id, APPROVED_GITHUB_PROVIDER_USER_IDS):
        raise HTTPException(status_code=403, detail="You are not authorized to create an API key. Please contact the maintainer.") 

    api_key = create_api_key(db_connection, db_cursor, provider, provider_user_id, DATABASE_HASH_KEY)

    return {"api_key": api_key}

@app.delete("/api_keys/{api_key_id}", include_in_schema=False)
async def delete_api_key(request: Request, api_key_id: str):
    revoke_api_key(db_connection, db_cursor, api_key_id)


@app.get("/auth/{provider}/login", include_in_schema=False)
async def login(provider: str):
    match provider:
        case "github":
            sso = github_sso
        case _:
            raise HTTPException(status_code=400, detail="Unsupported provider: {provider}")

    async with sso:
        return await sso.get_login_redirect()


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
    expiration = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(days=1)
    token = jwt.encode({"pld": openid.model_dump(), "exp": expiration, "sub": openid.id}, key=JWT_SECRET_KEY, algorithm="HS256")
    maybe_insert_user(db_connection, db_cursor, openid.provider, openid.id, openid.email)

    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="token",
        value=token,
        expires=expiration,
        httponly=True,
        secure=is_production(),
        samesite="lax"
    )
    return response

@app.post("/user_details", include_in_schema=False)
async def update_user_detail(
    request: Request,
    server_url: str = Form(...),
    user: OpenID = Depends(get_logged_user)
):
    
    # Update the user's server_url in the database
    db_cursor.execute(
        "UPDATE users SET server_url = ? WHERE provider = ? AND provider_user_id = ?",
        (server_url, user.provider, user.id)
    )
    db_connection.commit()
    return RedirectResponse(url="/", status_code=302)
