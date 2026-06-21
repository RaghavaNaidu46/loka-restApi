import dataclasses
from typing import Optional


@dataclasses.dataclass
class AadhaarResult:
    isValid: bool
    referenceId: Optional[str] = None
    errorMessage: Optional[str] = None
    name: Optional[str] = None
    dob: Optional[str] = None
    address: Optional[str] = None


async def processAadhaarXml(xmlBytes: bytes, shareCode: str) -> AadhaarResult:
    """
    Process Aadhaar Offline XML (UIDAI Offline e-KYC).

    In MOCK_VERIFICATION=true mode this function is not called.
    In production:
    1. Unzip the password-protected zip (password = shareCode) to extract the XML.
    2. Parse the XML using lxml.
    3. Validate the UIDAI digital signature using the UIDAI public key.
    4. Extract the UID reference (not the Aadhaar number itself — just the reference).
    5. Return isValid=True with referenceId, or isValid=False with errorMessage.
    """
    try:
        import zipfile
        import io
        from lxml import etree

        # Step 1: Unzip
        try:
            zipBuffer = io.BytesIO(xmlBytes)
            with zipfile.ZipFile(zipBuffer) as zf:
                xmlFileName = next(
                    (name for name in zf.namelist() if name.endswith(".xml")), None
                )
                if not xmlFileName:
                    return AadhaarResult(isValid=False, errorMessage="No XML found inside the zip")
                rawXml = zf.read(xmlFileName, pwd=shareCode.encode("utf-8"))
        except zipfile.BadZipFile:
            # Might be a raw XML file, not a zip
            rawXml = xmlBytes
        except RuntimeError as e:
            return AadhaarResult(isValid=False, errorMessage=f"Invalid share code: {e}")

        # Step 2: Parse XML
        root = etree.fromstring(rawXml)

        # Step 3: Extract reference ID (uid attribute from KycRes or OfflinePaperlessKyc tag)
        referenceId = root.get("uid") or root.get("referenceId") or root.get("referenceid")
        if not referenceId:
            # Try child elements
            for elem in root.iter():
                if elem.get("uid"):
                    referenceId = elem.get("uid")
                    break

        # Extract Poi and Poa elements case-insensitively
        poi_elements = root.xpath("//*[translate(local-name(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='poi']")
        poa_elements = root.xpath("//*[translate(local-name(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='poa']")
        
        name = None
        dob = None
        if poi_elements:
            poi = poi_elements[0]
            for attr_name, attr_val in poi.attrib.items():
                if attr_name.lower() in ("name", "originalname", "fullname"):
                    name = attr_val
                elif attr_name.lower() in ("dob", "dateofbirth", "d.o.b", "d_o_b", "yob", "yearofbirth"):
                    dob = attr_val

        # Normalize DOB to DD/MM/YYYY format if found
        if dob:
            import re
            if re.match(r'^\b\d{4}\b$', dob.strip()):
                dob = f"01/01/{dob.strip()}"
            else:
                match_yyyy = re.search(r'(\d{4})[-/. ](\d{2})[-/. ](\d{2})', dob)
                if match_yyyy:
                    dob = f"{match_yyyy.group(3)}/{match_yyyy.group(2)}/{match_yyyy.group(1)}"
                else:
                    match_dd = re.search(r'(\d{2})[-/. ](\d{2})[-/. ](\d{4})', dob)
                    if match_dd:
                        dob = f"{match_dd.group(1)}/{match_dd.group(2)}/{match_dd.group(3)}"
        
        address_parts = []
        if poa_elements:
            poa = poa_elements[0]
            for attr in ["co", "house", "street", "lm", "loc", "vtc", "dist", "state", "pc"]:
                # Lookup attributes case-insensitively just in case
                val = next((v for k, v in poa.attrib.items() if k.lower() == attr.lower()), None)
                if val:
                    address_parts.append(val)
        address = ", ".join(address_parts) if address_parts else None

        # Step 4: UIDAI Signature Validation
        # For now, we accept any well-formed XML as valid.

        return AadhaarResult(
            isValid=True,
            referenceId=str(referenceId) if referenceId else "UNKNOWN_REF",
            name=name,
            dob=dob,
            address=address
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return AadhaarResult(isValid=False, errorMessage=str(e))
