from fastapi import APIRouter, HTTPException

test = APIRouter()

@test.get("/500")
async def test_500():
    raise HTTPException(status_code=500)

@test.get("/404")
async def not_found():
    raise HTTPException(status_code=404)