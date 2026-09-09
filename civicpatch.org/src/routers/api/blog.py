import lib.blog as blog
from fastapi import APIRouter, Query


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("/posts")
    async def get_blog_posts_endpoint(limit: int = Query(3, ge=1, le=50)):
        posts = await blog.get_all_posts()
        return {"data": posts[:limit]}

    return router
