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
    return str(value).strip().lower()

def normalize_quantity(qty_str):
    if not qty_str:
        return None
    return int("".join(filter(str.isdigit, str(qty_str))))

def match_retailer_data(qr_data, crop_id, crop_type, quantity, packaging_type, receiver_name):
    def get_case_insensitive(qr_dict, *keys):
        for k in keys:
            for actual_key in qr_dict:
                if actual_key.lower() == k.lower():
                    return normalize_field(qr_dict[actual_key])
        return None

    qr_crop_id = get_case_insensitive(qr_data, "cropId")
    qr_crop_type = get_case_insensitive(qr_data, "cropType", "croptype")
    qr_quantity = normalize_quantity(qr_data.get("quantity") or qr_data.get("quantitySold"))
    qr_packaging = get_case_insensitive(qr_data, "packagingType")
    qr_receiver_name = get_case_insensitive(qr_data, "receiverName", "receiver")

    if qr_crop_id != normalize_field(crop_id):
        return {"status": "mismatch", "message": f"Crop ID mismatch: Expected {crop_id}, but found {qr_crop_id}"}

    if qr_crop_type != normalize_field(crop_type):
        return {"status": "mismatch", "message": f"Crop Type mismatch: Expected {crop_type}, but found {qr_crop_type}"}

    if qr_quantity != normalize_quantity(quantity):
        return {"status": "mismatch", "message": f"Quantity Sold mismatch: Expected {quantity}, but found {qr_quantity}"}

    if qr_packaging != normalize_field(packaging_type):
        return {"status": "mismatch", "message": f"Packaging Type mismatch: Expected {packaging_type}, but found {qr_packaging}"}

    if qr_receiver_name != normalize_field(receiver_name):
        return {"status": "mismatch", "message": f"Receiver Name mismatch: Expected {receiver_name}, but found {qr_receiver_name}"}

    return {"status": "match", "message": "✅ All data verified successfully by retailer."}
