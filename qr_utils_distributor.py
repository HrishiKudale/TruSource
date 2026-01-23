import cv2
import json

def decode_qr_code_image(image_path):
    """
    Decode the QR code from the uploaded image and return the data in JSON format.
    """
    img = cv2.imread(image_path)
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(img)
    if not data:
        return None
    return json.loads(data)


def normalize_field(value):
    if value is None:
        return None
    return str(value).strip()


def normalize_quantity(qty_str):
    if not qty_str:
        return None
    return int("".join(filter(str.isdigit, str(qty_str))))


def match_distributor_data(qr_data, crop_id, crop_type, processed_quantity, packaging_type):
    def get_case_insensitive(qr_dict, *keys):
        for k in keys:
            for actual_key in qr_dict:
                if actual_key.lower() == k.lower():
                    return normalize_field(qr_dict[actual_key])
        return None

    qr_crop_id = get_case_insensitive(qr_data, "cropId")
    qr_crop_type = get_case_insensitive(qr_data, "cropType", "croptype")
    qr_quantity = normalize_quantity(qr_data.get("processedQuantity") or qr_data.get("harvestQuantity"))
    qr_packaging = get_case_insensitive(qr_data, "packagingType")

    if qr_crop_id != crop_id:
        return {"status": "mismatch", "message": f"Crop ID mismatch: Expected {crop_id}, but found {qr_crop_id}"}

    if qr_crop_type != crop_type:
        return {"status": "mismatch", "message": f"Crop Type mismatch: Expected {crop_type}, but found {qr_crop_type}"}

    if qr_quantity != normalize_quantity(processed_quantity):
        return {"status": "mismatch", "message": f"Processed Quantity mismatch: Expected {processed_quantity}, but found {qr_quantity}"}

    if qr_packaging != packaging_type:
        return {"status": "mismatch", "message": f"Packaging Type mismatch: Expected {packaging_type}, but found {qr_packaging}"}

    return {"status": "match", "message": "✅ All data verified successfully by distributor."}
