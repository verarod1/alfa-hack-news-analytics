from fastapi import APIRouter
from app.schemas.profile import RolesResponse, DemoProfilesResponse
from app.services.profile_service import ROLES, get_demo_profiles

router = APIRouter(prefix="/api/v1", tags=["Profiles"])


@router.get("/roles", response_model=RolesResponse)
def roles():
    return {"items": list(ROLES)}


@router.get("/demo-profiles", response_model=DemoProfilesResponse)
def demo_profiles():
    return get_demo_profiles()
