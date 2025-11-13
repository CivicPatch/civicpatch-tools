from fastapi import APIRouter
import database

def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def list_people_endpoint(
        jurisdiction_ocdid: str,
    ):
        people = await database.get_jurisdiction_people(jurisdiction_ocdid)
        return {
            "data": people
        }

    @router.get("/geo")
    async def list_people_by_geo_endpoint(
        lat: float,
        long: float,
    ):
        people = await database.get_people_by_geo(lat, long)
        return {
            "data": people
        }
    return router
