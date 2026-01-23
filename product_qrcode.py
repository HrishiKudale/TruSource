# product_qrcode.py
import os
import qrcode
from PIL import Image, ImageDraw, ImageFont

# 👤 Individual Crop QR code generator
def product(crop_id):
    traceability_url = f"http://192.168.1.33:5000/consumer/scan?crop_id={crop_id}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(traceability_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    qr_dir = os.path.join("static", "qrcodes")
    os.makedirs(qr_dir, exist_ok=True)

    qr_filename = f"{crop_id}_qr.png"
    qr_file_path = os.path.join(qr_dir, qr_filename)
    img.save(qr_file_path)

    return f"static/qrcodes/{qr_filename}"


import os
import qrcode
from PIL import Image, ImageDraw, ImageFont

# 📦 Batch QR code generator for processed products
def generate_batch_qr_codes(base_code, qr_data_template, count):
    qr_dir = os.path.join("static", "qrcodes", "batch")
    os.makedirs(qr_dir, exist_ok=True)

    qr_paths = []
    qr_data_list = []

    for i in range(1, count + 1):
        batch_no = f"{base_code}-{i}"
        qr_data = qr_data_template.copy()
        qr_data["batchNo"] = batch_no

        crop_id = qr_data["cropId"]
        traceability_url = f"http://localhost:5000/track?crop_id={crop_id}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(traceability_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

        # Add batch number below QR
        qr_width, qr_height = qr_img.size
        final_img = Image.new("RGB", (qr_width, qr_height + 50), "white")
        final_img.paste(qr_img, (0, 0))

        draw = ImageDraw.Draw(final_img)
        try:
            font = ImageFont.truetype("arial.ttf", 18)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), batch_no, font=font)
        text_width = bbox[2] - bbox[0]
        x = (qr_width - text_width) // 2
        draw.text((x, qr_height + 10), batch_no, fill="black", font=font)

        filename = f"{batch_no}.png"
        full_path = os.path.join(qr_dir, filename)
        final_img.save(full_path)

        qr_paths.append(f"static/qrcodes/batch/{filename}")
        qr_data_list.append(qr_data)

    return qr_paths, qr_data_list
