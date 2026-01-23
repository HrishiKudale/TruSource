import cv2
import json
from datetime import datetime

def decode_qr_code_image(image_path):
    """
    Decode the QR code from the uploaded image and return the data in JSON format.
    """
    img = cv2.imread(image_path)
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(img)
    if not data:
        return None
    return json.loads(data)  # Return the decoded JSON data

def normalize_date(date_str):
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None

def normalize_quantity(qty_str):
    if not qty_str:
        return None
    return int("".join(filter(str.isdigit, qty_str)))

def normalize_field(value):
    if value is None:
        return None
    return str(value).strip()

def match_data(qr_data, crop_id, crop_type, harvest_quantity, packaging_type, manufacturer_id):
    """
    Compare the QR code data with the manually entered data.
    Returns a dictionary with the comparison result.
    """
    # Extract values from the QR code data
    qr_crop_id = qr_data.get("cropId")
    qr_crop_type = qr_data.get("croptype")
    qr_harvest_quantity = qr_data.get("harvestQuantity")
    qr_packaging_type = qr_data.get("packagingType")
    qr_manufacturer_id = qr_data.get("manufacturerId")


    
    if qr_manufacturer_id != manufacturer_id:
        return {"status": "mismatch", "message": f"Crop ID mismatch: Expected {manufacturer_id}, but found {qr_manufacturer_id}"}
    # Compare cropId
    if qr_crop_id != crop_id:
        return {"status": "mismatch", "message": f"Crop ID mismatch: Expected {crop_id}, but found {qr_crop_id}"}

    # Compare cropType
    if qr_crop_type != crop_type:
        return {"status": "mismatch", "message": f"Crop Type mismatch: Expected {crop_type}, but found {qr_crop_type}"}

    # Compare harvestQuantity
    if int(qr_harvest_quantity) != int(harvest_quantity):
        return {"status": "mismatch", "message": f"Harvest Quantity mismatch: Expected {harvest_quantity}, but found {qr_harvest_quantity}"}

    # Compare packagingType
    if qr_packaging_type != packaging_type:
        return {"status": "mismatch", "message": f"Packaging Type mismatch: Expected {packaging_type}, but found {qr_packaging_type}"}

    return {"status": "match", "message": "All data matches!"}
