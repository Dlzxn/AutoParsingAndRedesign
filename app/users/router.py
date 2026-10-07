from fastapi import APIRouter

from app.auth.deps import DbSession, OptionalUser
from app.catalog.service import get_tariffs

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/user_data")
async def user_data(user: OptionalUser):
    if user is None:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "name": user.email,
        "subscriptionPlan": "Administrator" if user.is_admin else user.subscribe_status,
        "is_admin": user.is_admin,
        "date_end": user.date_end.date().isoformat() if user.date_end else None,
    }


@router.get("/pricing")
async def pricing(db: DbSession):
    return await get_tariffs(db)
