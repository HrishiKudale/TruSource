import qrcode
import json

def generate_qr_code( harvest_data, output_path):
    """
    Generate a QR code that combines both crop and harvest data.

    :param crop_data: Dictionary containing crop data
    :param harvest_data: Dictionary containing harvest data
    :param output_path: Path to save the QR code image
    :return: None (QR code is saved to the provided output path)
    """
    qr_data = { **harvest_data}  # Combine crop and harvest data
    qr_img = qrcode.make(json.dumps(qr_data))  # Generate the QR code image
    qr_img.save(output_path)  # Save the image at the specified path
    return output_path
