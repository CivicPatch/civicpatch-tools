import os
import datetime
from fastapi import FastAPI, Request, Security, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import APIKeyCookie  # this is the part that puts the lock icon to the docs
from fastapi_sso.sso.github import GithubSSO
from fastapi_sso.sso.base import OpenID

from jose import jwt  # pip install python-jose[cryptography]

# Only purpose is to manage users, their API keys, and move data from 3rd party servers
# to GitHub Actions.
# Ref: https://github.com/tomasvotava/fastapi-sso/blob/master/docs/how-to-guides/use-with-fastapi-security.md

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_CALLBACK_URL = os.getenv("GITHUB_CALLBACK_URL", "http://127.0.0.1:8000/auth/github/callback")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not all([GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, JWT_SECRET_KEY]):
    missing_vars = [var for var, val in {
        "GITHUB_CLIENT_ID": GITHUB_CLIENT_ID,
        "GITHUB_CLIENT_SECRET": GITHUB_CLIENT_SECRET,
        "JWT_SECRET_KEY": JWT_SECRET_KEY
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
    except HTTPException:
        user = None

    return templates.TemplateResponse(
        request=request, name="index.html", context={"user": user}
    )

@app.get("/api_keys", response_class=HTMLResponse, include_in_schema=False)
async def api_keys_page(request: Request):
    try:
        user = await get_logged_user(request.cookies.get("token"))
        # Fetch user's API keys from database

        api_keys = [{
            "id": "key1blahblah",
            "suffix": "1234",
            "name": "My First API Key",
            "created_at": datetime.datetime.now(tz=datetime.timezone.utc).date()
        }]

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

@app.post("/api_keys", include_in_schema=False)
async def create_api_key(request: Request):
    """Create new API key"""
    pass

@app.delete("/api_keys/{key_id}", include_in_schema=False)
async def revoke_api_key(request: Request, key_id: str):
    """Revoke specific API key"""
    pass

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
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="token", value=token, expires=expiration
    )  # This cookie will make sure /protected knows the user
    return response
