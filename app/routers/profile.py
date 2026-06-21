import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.database import getDb
from app.core.deps import getCurrentCitizen
from app.models.citizen import Citizen
from app.models.issue import Issue
from app.models.participation import Participation
from app.schemas.citizen import UpdateProfileRequest
from app.schemas.district import DistrictResponse

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("/me", summary="Get authenticated citizen's full profile")
async def getMyProfile(
    citizen: Annotated[Citizen, Depends(getCurrentCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    await db.refresh(citizen, ["homeDistrict", "livingInDistrict"])
    return {
        "id": str(citizen.id),
        "phoneNumber": citizen.phoneNumber,
        "email": citizen.email,
        "displayName": citizen.displayName,
        "originalName": citizen.originalName,
        "dateOfBirth": citizen.dateOfBirth,
        "address": citizen.address,
        "aadhaarNumber": citizen.aadhaarNumber,
        "verificationStatus": citizen.verificationStatus,
        "accountStatus": citizen.accountStatus,
        "role": citizen.role,
        "homeDistrict": DistrictResponse.model_validate(citizen.homeDistrict).model_dump() if citizen.homeDistrict else None,
        "livingInDistrict": DistrictResponse.model_validate(citizen.livingInDistrict).model_dump() if citizen.livingInDistrict else None,
        "createdAt": citizen.createdAt.isoformat() if citizen.createdAt else None,
        "lastActiveAt": citizen.lastActiveAt.isoformat() if citizen.lastActiveAt else None,
    }


@router.patch("/me", summary="Update citizen display name")
async def updateMyProfile(
    body: UpdateProfileRequest,
    citizen: Annotated[Citizen, Depends(getCurrentCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    updateData = body.model_dump(exclude_none=True)
    if updateData:
        await db.execute(
            update(Citizen).where(Citizen.id == citizen.id).values(**updateData)
        )
    return {"message": "Profile updated successfully"}


@router.get("/{citizenId}", summary="Get public profile of a citizen")
async def getPublicProfile(
    citizenId: uuid.UUID,
    db: Annotated[AsyncSession, Depends(getDb)],
):
    result = await db.execute(select(Citizen).where(Citizen.id == citizenId))
    citizen = result.scalar_one_or_none()
    if not citizen:
        raise HTTPException(status_code=404, detail="Citizen not found")

    await db.refresh(citizen, ["homeDistrict"])
    return {
        "id": str(citizen.id),
        "displayName": citizen.displayName,
        "verificationStatus": citizen.verificationStatus,
        "homeDistrict": DistrictResponse.model_validate(citizen.homeDistrict).model_dump() if citizen.homeDistrict else None,
        "createdAt": citizen.createdAt.isoformat() if citizen.createdAt else None,
    }


@router.get("/me/issues", summary="Get authenticated citizen's submitted issues")
async def getMyIssues(
    citizen: Annotated[Citizen, Depends(getCurrentCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
):
    result = await db.execute(
        select(Issue)
        .where(Issue.creatorId == citizen.id)
        .order_by(Issue.createdAt.desc())
        .offset(offset)
        .limit(limit)
    )
    issues = result.scalars().all()

    items = []
    for issue in issues:
        await db.refresh(issue, ["district"])
        items.append({
            "id": str(issue.id),
            "title": issue.title,
            "category": issue.category,
            "status": issue.status,
            "supportCount": issue.supportCount,
            "opposeCount": issue.opposeCount,
            "city": issue.city,
            "district": issue.district.name if issue.district else None,
            "createdAt": issue.createdAt.isoformat(),
        })

    return {"items": items, "count": len(items)}


@router.get("/me/participation", summary="Get authenticated citizen's participation history")
async def getMyParticipation(
    citizen: Annotated[Citizen, Depends(getCurrentCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
):
    result = await db.execute(
        select(Participation)
        .where(Participation.citizenId == citizen.id)
        .order_by(Participation.createdAt.desc())
        .offset(offset)
        .limit(limit)
    )
    participations = result.scalars().all()

    items = []
    for p in participations:
        await db.refresh(p, ["issue"])
        items.append({
            "issueId": str(p.issueId),
            "issueTitle": p.issue.title if p.issue else None,
            "type": p.type,
            "createdAt": p.createdAt.isoformat(),
        })

    return {"items": items, "count": len(items)}
