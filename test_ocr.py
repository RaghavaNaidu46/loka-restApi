import sys
import os

# Set python path to current directory so it can import app
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services.ocr_service import extractAadhaarDetails

def main():
    print("Reading front_debug.jpg and back_debug.jpg...")
    with open("front_debug.jpg", "rb") as f:
        front_bytes = f.read()
    with open("back_debug.jpg", "rb") as f:
        back_bytes = f.read()

    print("Running extractAadhaarDetails...")
    name, dob, address, aadhaar_number = extractAadhaarDetails(front_bytes, back_bytes)
    print("--- OCR RESULTS ---")
    print(f"Name: {name}")
    print(f"DOB: {dob}")
    print(f"Address: {address}")
    print(f"Aadhaar Number: {aadhaar_number}")

if __name__ == "__main__":
    main()
