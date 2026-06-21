import re
import io
import easyocr
import logging
from typing import Tuple, Optional, List

logger = logging.getLogger(__name__)

# Global EasyOCR Reader instance cached for performance
_reader = None

# Minimum confidence score to accept an OCR result
_OCR_MIN_CONFIDENCE = 0.30


def getOcrReader() -> easyocr.Reader:
    """Get or initialize the EasyOCR reader singleton."""
    global _reader
    if _reader is None:
        logger.info("Initializing EasyOCR Reader for English...")
        _reader = easyocr.Reader(['en'])
    return _reader


def preprocessImage(imageBytes: bytes) -> bytes:
    """
    Preprocess a raw image to improve OCR accuracy:
      1. Upscale if smaller than 1000px wide
      2. Convert to grayscale
      3. Enhance contrast
      4. Apply sharpening filter
    Returns enhanced image as JPEG bytes.
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter

        img = Image.open(io.BytesIO(imageBytes))

        # Upscale small images (minimum 1000px wide)
        if img.width < 1000:
            scale = 1000 / img.width
            newSize = (int(img.width * scale), int(img.height * scale))
            img = img.resize(newSize, Image.LANCZOS)

        # Convert to grayscale
        img = img.convert("L")

        # Boost contrast
        img = ImageEnhance.Contrast(img).enhance(1.8)

        # Sharpen
        img = img.filter(ImageFilter.SHARPEN)
        img = img.filter(ImageFilter.SHARPEN)  # Double-sharpen for noisy images

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        return buf.getvalue()

    except Exception as e:
        logger.warning(f"Image preprocessing failed, using raw bytes: {e}")
        return imageBytes


def isNonLatinNoise(text: str) -> bool:
    """
    Returns True if a line consists predominantly of non-ASCII characters
    (e.g. Telugu/Hindi script) that would pollute name/address parsing.
    """
    if not text:
        return False
    nonAsciiCount = sum(1 for c in text if ord(c) > 127)
    return nonAsciiCount / max(len(text), 1) > 0.4


def extractAadhaarDetails(
    frontBytes: bytes, backBytes: bytes
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Extracts name, DOB, address, and Aadhaar number from front and back card image bytes.
    Applies preprocessing, confidence filtering, and robust parsing heuristics.

    Returns:
        (name, dob, address, aadhaarNumber)
    """
    name = None
    dob = None
    address = None
    aadhaarNumber = None

    # Debug mode: controlled by DEBUG_OCR env var (graceful fallback if settings unavailable)
    try:
        from app.core.config import settings
        debugOcr = settings.debugOcr
    except Exception:
        debugOcr = False

    # Debug: dump raw images to disk if DEBUG_OCR is enabled
    if debugOcr:
        try:
            with open("front_debug.jpg", "wb") as f:
                f.write(frontBytes)
            with open("back_debug.jpg", "wb") as f:
                f.write(backBytes)
        except Exception as dbgErr:
            logger.error(f"Failed to save debug images: {dbgErr}")

    try:
        reader = getOcrReader()

        # Preprocess both images before OCR
        frontProcessed = preprocessImage(frontBytes)
        backProcessed = preprocessImage(backBytes)

        # ── Front Image: Name, DOB, Aadhaar Number ──────────────────────────
        frontResults = reader.readtext(frontProcessed)

        # Filter by confidence and non-Latin noise
        frontLines = [
            text.strip()
            for (_, text, conf) in frontResults
            if text and text.strip() and conf >= _OCR_MIN_CONFIDENCE and not isNonLatinNoise(text)
        ]
        logger.info(f"Front OCR Lines (filtered): {frontLines}")

        name, dob = parseFrontDetails(frontLines)
        aadhaarNumber = parseAadhaarNumber(frontLines)

        # ── Back Image: Address, Aadhaar Number fallback ─────────────────────
        backResults = reader.readtext(backProcessed)

        backLines = [
            text.strip()
            for (_, text, conf) in backResults
            if text and text.strip() and conf >= _OCR_MIN_CONFIDENCE and not isNonLatinNoise(text)
        ]
        logger.info(f"Back OCR Lines (filtered): {backLines}")

        address = parseBackDetails(backLines)
        if not aadhaarNumber:
            aadhaarNumber = parseAadhaarNumber(backLines)

        # Debug: write parsed results if DEBUG_OCR enabled
        if debugOcr:
            with open("ocr_debug.txt", "w", encoding="utf-8") as dbgFile:
                dbgFile.write(f"Front Lines:\n{frontLines}\n\n")
                dbgFile.write(f"Back Lines:\n{backLines}\n\n")
                dbgFile.write(f"Parsed Name: {name}\n")
                dbgFile.write(f"Parsed DOB: {dob}\n")
                dbgFile.write(f"Parsed Address: {address}\n")
                dbgFile.write(f"Parsed Aadhaar Number: {aadhaarNumber}\n")

    except Exception as e:
        logger.error(f"Error during Aadhaar Card OCR processing: {e}", exc_info=True)

    return name, dob, address, aadhaarNumber


def normalizeOcrChars(text: str) -> str:
    """
    Normalize common OCR character substitutions:
      O/o → 0 (for digit contexts)
      I/l/L → 1 (for digit contexts)
    Only applied to the uppercase copy for digit extraction — does NOT mutate original text.
    """
    result = text.upper()
    for ch, digit in [('O', '0'), ('I', '1'), ('L', '1')]:
        result = result.replace(ch, digit)
    return result


def parseAadhaarNumber(lines: List[str]) -> Optional[str]:
    """
    Locate a 12-digit Aadhaar number across one or more OCR lines.
    Strategy:
      1. Look for 4-4-4 pattern with optional separators in any single line.
      2. Look for 4-4-4 pattern across adjacent line pairs (number split across lines).
      3. Extract all digits from full text and find a 12-digit run.
    """
    def findIn(text: str) -> Optional[str]:
        normalized = normalizeOcrChars(text)
        # Match 4-4-4 groups with optional spaces/hyphens
        match = re.search(r'\b(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})\b', normalized)
        if match:
            return f"{match.group(1)} {match.group(2)} {match.group(3)}"
        return None

    # Pass 1: single lines
    for line in lines:
        result = findIn(line)
        if result:
            return result

    # Pass 2: sliding window of 2 adjacent lines joined
    for i in range(len(lines) - 1):
        combined = lines[i] + " " + lines[i + 1]
        result = findIn(combined)
        if result:
            return result

    # Pass 3: scan all digits from full normalized text
    fullText = normalizeOcrChars(" ".join(lines))
    digitsOnly = re.sub(r'\D', '', fullText)

    # Look for a 12-digit run (not part of a longer digit sequence)
    match12 = re.search(r'(?<!\d)(\d{12})(?!\d)', digitsOnly)
    if match12:
        val = match12.group(1)
        return f"{val[:4]} {val[4:8]} {val[8:]}"

    # Last resort: if total digit count == 12 treat entire sequence as Aadhaar
    if len(digitsOnly) == 12:
        return f"{digitsOnly[:4]} {digitsOnly[4:8]} {digitsOnly[8:]}"

    return None


def parseDobFromLine(line: str) -> Optional[str]:
    """
    Extract a Date of Birth from a single OCR line.
    Handles:
      - Keyword anchors: DOB, D.O.B, BIRTH, YOB
      - OCR separator noise: slashes misread as digits (10006/2001 → 10/06/2001)
      - YYYY-MM-DD and DD/MM/YYYY orderings
      - Year-only fallback
    """
    normalized = normalizeOcrChars(line)

    # ── Try clean structured patterns first ─────────────────────────────────

    # Pattern: keyword + DD sep MM sep YYYY
    m = re.search(
        r'(?:DOB|D0B|D\.O\.B|BIRTH)[:\s]*(\d{1,2})[-/. ](\d{1,2})[-/. ](\d{4})',
        normalized
    )
    if m:
        d, mo, y = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
        if 1 <= int(d) <= 31 and 1 <= int(mo) <= 12:
            return f"{d}/{mo}/{y}"

    # Pattern: keyword + YYYY sep MM sep DD
    m = re.search(
        r'(?:DOB|D0B|D\.O\.B|BIRTH)[:\s]*(\d{4})[-/. ](\d{1,2})[-/. ](\d{1,2})',
        normalized
    )
    if m:
        y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
        if 1 <= int(d) <= 31 and 1 <= int(mo) <= 12:
            return f"{d}/{mo}/{y}"

    # Pattern: bare DD sep MM sep YYYY (no keyword)
    m = re.search(r'\b(\d{1,2})[-/. ](\d{1,2})[-/. ](\d{4})\b', normalized)
    if m:
        d, mo, y = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
        if 1 <= int(d) <= 31 and 1 <= int(mo) <= 12:
            return f"{d}/{mo}/{y}"

    # Pattern: bare YYYY sep MM sep DD
    m = re.search(r'\b(\d{4})[-/. ](\d{1,2})[-/. ](\d{1,2})\b', normalized)
    if m:
        y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
        if 1 <= int(d) <= 31 and 1 <= int(mo) <= 12:
            return f"{d}/{mo}/{y}"

    # ── Noisy separator recovery ─────────────────────────────────────────────
    # Slashes/separators sometimes absorbed as digits: "10006/2001" or "10062001"
    # Strategy: find a year (19xx or 20xx), then decode digits before it as DDMM.

    # Locate keyword anchor to restrict search scope
    keywords = ["DOB", "D0B", "D.O.B", "BIRTH", "YOB", "YEAR OF BIRTH"]
    anchorIdx = -1
    for kw in keywords:
        idx = normalized.find(kw)
        if idx != -1:
            anchorIdx = idx + len(kw)
            break

    searchText = normalized[anchorIdx:] if anchorIdx != -1 else normalized

    # Find a plausible year
    yearMatch = re.search(r'\b(19\d{2}|20[0-2]\d)\b', searchText)
    if not yearMatch:
        yearMatch = re.search(r'(19\d{2}|20[0-2]\d)', searchText)

    if yearMatch:
        year = yearMatch.group(1)
        beforeDigits = re.sub(r'\D', '', searchText[:yearMatch.start()])

        day, month = None, None
        length = len(beforeDigits)

        if length == 4:
            # DDMM
            day, month = beforeDigits[:2], beforeDigits[2:]
        elif length == 3:
            # DDM or DMM
            d1, m1 = beforeDigits[:2], beforeDigits[2:]
            d2, m2 = beforeDigits[:1], beforeDigits[1:]
            if 1 <= int(d1) <= 31 and 1 <= int(m1) <= 12:
                day, month = d1, m1
            elif 1 <= int(d2) <= 31 and 1 <= int(m2) <= 12:
                day, month = d2, m2
        elif length >= 5:
            # OCR absorb separator e.g. "10006" → day=10, month=06
            d, m = beforeDigits[:2], beforeDigits[-2:]
            if 1 <= int(d) <= 31 and 1 <= int(m) <= 12:
                day, month = d, m

        if day and month:
            return f"{day.zfill(2)}/{month.zfill(2)}/{year}"

        # Fallback: Year-only (YOB)
        return f"01/01/{year}"

    return None


def parseFrontDetails(lines: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse front card OCR lines to extract Name and DOB.
    """
    name = None
    dob = None
    dobIndex = -1

    # 1. Find DOB
    for idx, line in enumerate(lines):
        parsed = parseDobFromLine(line)
        if parsed:
            dob = parsed
            dobIndex = idx
            break

    # Common header/label words to exclude from name candidates
    ignoreKeywords = {
        "government", "india", "govt", "unique", "identification",
        "authority", "uidai", "male", "female", "transgender",
        "yob", "dob", "birth", "enrollment", "help", "download",
        "card", "aadhaar", "aadhar", "satyameva", "jayate",
        "republic", "of",
    }

    # 2. Extract Name — look above the DOB line
    potentialNames = []
    searchLimit = dobIndex if dobIndex != -1 else len(lines)

    for idx in range(searchLimit):
        line = lines[idx]

        # Strip non-alpha characters, keep spaces and dots (for initials like "K. Aravind")
        cleaned = re.sub(r'[^a-zA-Z.\s]', '', line).strip()
        # Normalize multiple spaces
        cleaned = re.sub(r'\s+', ' ', cleaned)
        words = cleaned.split()

        # Require at least 1 substantial word (>= 3 chars) and at most 5 words
        substantialWords = [w for w in words if len(re.sub(r'\.', '', w)) >= 2]
        if not substantialWords or len(words) > 5:
            continue

        # Skip if any word is a known header/label keyword
        if any(w.lower().rstrip('.') in ignoreKeywords for w in words):
            continue

        # Skip if line is mostly single-char tokens (likely noise)
        singleCharCount = sum(1 for w in words if len(w) == 1 and w != '.')
        if singleCharCount > len(words) // 2:
            continue

        potentialNames.append(cleaned)

    # Name is typically the line closest to the DOB (last in the candidate list)
    if potentialNames:
        name = potentialNames[-1]

    return name, dob


def parseBackDetails(lines: List[str]) -> Optional[str]:
    """
    Parse back card OCR lines to extract the full address.
    Handles:
      - Explicit "Address:" label
      - S/O, C/O, W/O relationship prefix
      - PIN-code anchored backtracking heuristic
      - Semicolons normalized to commas
      - SIO/CIO/WIO typos normalized to S/O, C/O, W/O
    """
    addressParts = []
    addressStarted = False
    pincodePattern = re.compile(r'\b\d{6}\b')

    # Normalize lines: fix OCR char substitutions, but preserve original for output
    def normalizeLine(line: str) -> str:
        result = line.upper()
        for ch, digit in [('O', '0'), ('I', '1'), ('L', '1')]:
            result = result.replace(ch, digit)
        return result

    normalizedLines = [normalizeLine(line) for line in lines]

    def cleanAddressPart(text: str) -> str:
        """Normalize address text separators."""
        # Semicolons → commas
        text = text.replace(';', ',')
        # Fix OCR relationship prefix noise: SIO → S/O, CIO → C/O, WIO → W/O
        text = re.sub(r'\bS[/I]0\b', 'S/O', text, flags=re.IGNORECASE)
        text = re.sub(r'\bC[/I]0\b', 'C/O', text, flags=re.IGNORECASE)
        text = re.sub(r'\bW[/I]0\b', 'W/O', text, flags=re.IGNORECASE)
        text = re.sub(r'\bD[/I]0\b', 'D/O', text, flags=re.IGNORECASE)
        return text.strip()

    # Relationship prefix patterns (C/O, S/O etc.) indicating address start
    relPrefixPattern = re.compile(
        r'^(?:C/0|S/0|W/0|D/0|C/O|S/O|W/O|D/O|TO|CIO|SIO|WIO|DIO)\b'
    )

    for idx, normLine in enumerate(normalizedLines):
        originalLine = lines[idx]

        if not addressStarted:
            # Check for "Address:" label
            addrMatch = re.search(r'ADDRESS[:\s]*(.*)', normLine)
            if addrMatch:
                addressStarted = True
                # Extract content after label from original line
                origMatch = re.search(r'Address[:\s]*(.*)', originalLine, re.IGNORECASE)
                content = origMatch.group(1).strip() if origMatch else originalLine
                if content:
                    addressParts.append(cleanAddressPart(content))
                continue

            # Check for relationship prefix
            if relPrefixPattern.match(normLine):
                addressStarted = True
                addressParts.append(cleanAddressPart(originalLine))
                continue
        else:
            # Continue collecting address lines until PIN code is found
            cleaned = cleanAddressPart(originalLine)
            addressParts.append(cleaned)
            if pincodePattern.search(normLine):
                break

    # Fallback: PIN-code anchored backtracking
    if not addressStarted:
        pinIndex = -1
        for idx, normLine in enumerate(normalizedLines):
            if pincodePattern.search(normLine):
                pinIndex = idx
                break

        if pinIndex != -1:
            startIdx = max(0, pinIndex - 4)
            for i in range(startIdx, pinIndex + 1):
                # Skip UIDAI website lines
                if re.search(r'(?:uidai\.gov\.in|www\.)', lines[i], re.IGNORECASE):
                    continue
                addressParts.append(cleanAddressPart(lines[i]))

    if not addressParts:
        return None

    # Combine, collapse duplicate commas, and normalize whitespace
    fullAddress = ", ".join(p for p in addressParts if p)
    fullAddress = re.sub(r',\s*,', ',', fullAddress)
    fullAddress = re.sub(r'\s+', ' ', fullAddress)
    return fullAddress.strip(", ")
