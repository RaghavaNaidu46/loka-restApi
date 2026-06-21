import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.database import getDb
from app.core.deps import getCurrentCitizen
from app.models.citizen import Citizen, VerificationStatus
from app.models.moderation import VerificationRecord, VerificationRecordStatus
from app.schemas.auth import MessageResponse

router = APIRouter(prefix="/verification", tags=["Verification"])


class VerificationStatusResponse:
    pass


@router.post("/upload-xml", summary="Upload Aadhaar Offline XML for verification")
async def uploadAadhaarXml(
    shareCode: Annotated[str, Form()],
    xmlFile: Annotated[UploadFile, File()],
    citizen: Annotated[Citizen, Depends(getCurrentCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    if citizen.verificationStatus == VerificationStatus.verified:
        return {"message": "Citizen is already verified. Status: verified."}

    xmlBytes = await xmlFile.read()
    if len(xmlBytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded XML file is empty")

    from app.core.config import settings

    if settings.mockVerification:
        # Mock: Accept any upload in development
        record = VerificationRecord(
            citizenId=citizen.id,
            status=VerificationRecordStatus.valid,
            uidaiRef=f"MOCK-{uuid.uuid4()}",
            verifiedAt=datetime.now(timezone.utc),
        )
        db.add(record)

        # Attempt to parse XML if possible, fallback to test defaults if invalid
        original_name = "Aravind Terli"
        dob = "15/08/1995"
        addr = "H.No 12-3, Madhapur, Hyderabad, Telangana - 500081"
        aadhaar_no = f"MOCK-{uuid.uuid4()}"[:20]
        try:
            from app.services.aadhaar_service import processAadhaarXml
            result = await processAadhaarXml(xmlBytes, shareCode)
            if result.isValid:
                if result.name:
                    original_name = result.name
                if result.dob:
                    dob = result.dob
                if result.address:
                    addr = result.address
                if result.referenceId:
                    aadhaar_no = result.referenceId
        except Exception as e:
            import traceback
            traceback.print_exc()
            pass

        await db.execute(
            update(Citizen)
            .where(Citizen.id == citizen.id)
            .values(
                verificationStatus=VerificationStatus.verified,
                originalName=original_name,
                dateOfBirth=dob,
                address=addr,
                aadhaarNumber=aadhaar_no,
            )
        )
        await db.commit()
        return {"message": "Verification successful. Status: verified.", "mockMode": True}

    # Production: Parse and validate Aadhaar Offline XML
    from app.services.aadhaar_service import processAadhaarXml
    result = await processAadhaarXml(xmlBytes, shareCode)

    if not result.isValid:
        record = VerificationRecord(
            citizenId=citizen.id,
            status=VerificationRecordStatus.invalid,
        )
        db.add(record)
        await db.commit()
        raise HTTPException(status_code=422, detail=result.errorMessage or "Verification failed")

    # Aadhaar deduplication: reject if this Aadhaar is linked to another account
    if result.referenceId:
        existing = await db.execute(
            select(Citizen)
            .where(Citizen.aadhaarNumber == result.referenceId)
            .where(Citizen.id != citizen.id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Aadhaar card is already linked to another account."
            )

    # Validate extracted fields — don't save partial/missing data
    missingFields = []
    if not result.name:
        missingFields.append("Name")
    if not result.dob:
        missingFields.append("Date of Birth")
    if not result.address:
        missingFields.append("Address")
    if missingFields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not extract: {', '.join(missingFields)}. Please upload a clearer document."
        )

    record = VerificationRecord(
        citizenId=citizen.id,
        status=VerificationRecordStatus.valid,
        uidaiRef=result.referenceId,
        verifiedAt=datetime.now(timezone.utc),
    )
    db.add(record)

    await db.execute(
        update(Citizen)
        .where(Citizen.id == citizen.id)
        .values(
            verificationStatus=VerificationStatus.verified,
            originalName=result.name,
            dateOfBirth=result.dob,
            address=result.address,
            aadhaarNumber=result.referenceId,
        )
    )
    await db.commit()
    return {"message": "Verification submitted successfully. Status: verified."}


@router.post("/upload-card", summary="Upload Aadhaar Card images (front & back) for verification")
async def uploadAadhaarCard(
    citizen: Annotated[Citizen, Depends(getCurrentCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
    frontImage: UploadFile = File(...),
    backImage: UploadFile = File(...),
):
    try:
        with open("app_requests.log", "a") as f:
            f.write(f"[{datetime.now()}] upload-card: Received request from citizen {citizen.id}\n")
    except Exception:
        pass

    if citizen.verificationStatus == VerificationStatus.verified:
        return {"message": "Citizen is already verified. Status: verified."}

    try:
        frontBytes = await frontImage.read()
        backBytes = await backImage.read()
        if len(frontBytes) == 0 or len(backBytes) == 0:
            raise HTTPException(status_code=400, detail="Uploaded images cannot be empty")

        from app.core.config import settings
        from app.services.ocr_service import extractAadhaarDetails

        # Extract name, dob, address, and Aadhaar number via EasyOCR
        name, dob, address, aadhaarNumber = extractAadhaarDetails(frontBytes, backBytes)

        # Field-level clarity check — report exactly which fields could not be read
        missingFields = []
        if not name:
            missingFields.append("Name")
        if not dob:
            missingFields.append("Date of Birth")
        if not address:
            missingFields.append("Address")
        if not aadhaarNumber:
            missingFields.append("Aadhaar Number")

        if missingFields:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not read: {', '.join(missingFields)}. Please upload a clearer photo of your Aadhaar card."
            )

        # Aadhaar deduplication: reject if already linked to another account
        existingResult = await db.execute(
            select(Citizen)
            .where(Citizen.aadhaarNumber == aadhaarNumber)
            .where(Citizen.id != citizen.id)
        )
        if existingResult.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Aadhaar card is already linked to another account."
            )

        if settings.mockVerification:
            record = VerificationRecord(
                citizenId=citizen.id,
                status=VerificationRecordStatus.valid,
                uidaiRef=f"CARD-{uuid.uuid4()}",
                verifiedAt=datetime.now(timezone.utc),
            )
            db.add(record)
            await db.execute(
                update(Citizen)
                .where(Citizen.id == citizen.id)
                .values(
                    verificationStatus=VerificationStatus.verified,
                    originalName=name,
                    dateOfBirth=dob,
                    address=address,
                    aadhaarNumber=aadhaarNumber,
                )
            )
            await db.commit()
            res = {
                "message": "Verification card successful. Status: verified.",
                "mockMode": True,
                "extractedData": {
                    "originalName": name,
                    "dateOfBirth": dob,
                    "address": address,
                    "aadhaarNumber": aadhaarNumber
                }
            }
            with open("app_requests.log", "a") as f:
                f.write(f"[{datetime.now()}] upload-card: Success (mockMode=True)\n")
            return res

        # Production OCR flow
        record = VerificationRecord(
            citizenId=citizen.id,
            status=VerificationRecordStatus.valid,
            uidaiRef=f"CARD-{uuid.uuid4()}",
            verifiedAt=datetime.now(timezone.utc),
        )
        db.add(record)
        await db.execute(
            update(Citizen)
            .where(Citizen.id == citizen.id)
            .values(
                verificationStatus=VerificationStatus.verified,
                originalName=name,
                dateOfBirth=dob,
                address=address,
                aadhaarNumber=aadhaarNumber,
            )
        )
        await db.commit()
        res = {
            "message": "Aadhaar Card processed successfully. Status: verified.",
            "extractedData": {
                "originalName": name,
                "dateOfBirth": dob,
                "address": address,
                "aadhaarNumber": aadhaarNumber
            }
        }
        with open("app_requests.log", "a") as f:
            f.write(f"[{datetime.now()}] upload-card: Success (Production)\n")
        return res
    except HTTPException as he:
        with open("app_requests.log", "a") as f:
            f.write(f"[{datetime.now()}] upload-card: HTTPException {he.status_code} - {he.detail}\n")
        raise he
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        with open("app_requests.log", "a") as f:
            f.write(f"[{datetime.now()}] upload-card: Internal Error - {str(e)}\n{tb}\n")
        raise e


@router.get("/status", summary="Get citizen's current verification status")
async def getVerificationStatus(
    citizen: Annotated[Citizen, Depends(getCurrentCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    result = await db.execute(
        select(VerificationRecord)
        .where(VerificationRecord.citizenId == citizen.id)
        .order_by(VerificationRecord.createdAt.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()

    return {
        "citizenId": str(citizen.id),
        "verificationStatus": citizen.verificationStatus,
        "lastAttempt": record.createdAt.isoformat() if record else None,
        "uidaiRef": record.uidaiRef if record else None,
    }


@router.patch("/districts", summary="Update citizen districts")
async def updateDistricts(
    citizen: Annotated[Citizen, Depends(getCurrentCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
    homeDistrictId: uuid.UUID | None = None,
    livingInDistrictId: uuid.UUID | None = None,
):
    values = {}
    if homeDistrictId is not None:
        values["homeDistrictId"] = homeDistrictId
    if livingInDistrictId is not None:
        values["livingInDistrictId"] = livingInDistrictId

    if values:
        await db.execute(
            update(Citizen)
            .where(Citizen.id == citizen.id)
            .values(**values)
        )
        await db.commit()
    return MessageResponse(message="Districts updated successfully")
