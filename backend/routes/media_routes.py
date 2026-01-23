# backend/routes/media_routes.py

import os
from flask import Blueprint, request, Response, abort, current_app, send_file

media_bp = Blueprint("media", __name__, url_prefix="/media")


@media_bp.route("/<path:filename>")
def stream_media(filename):
    """
    Proper Range-enabled streaming for video files (WebM).
    Fixes partial playback / start-stop issues.
    """

    media_dir = os.path.join(current_app.root_path, "static", "media")
    file_path = os.path.join(media_dir, filename)

    if not os.path.isfile(file_path):
        abort(404)

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("Range", None)

    # If browser does not request a range, send whole file
    if not range_header:
        return send_file(
            file_path,
            mimetype="video/webm",
            conditional=True
        )

    # Parse "Range: bytes=start-end"
    try:
        _, byte_range = range_header.split("=")
        start_str, end_str = byte_range.split("-")
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
    except ValueError:
        abort(416)

    end = min(end, file_size - 1)
    length = end - start + 1

    with open(file_path, "rb") as f:
        f.seek(start)
        data = f.read(length)

    response = Response(
        data,
        status=206,
        mimetype="video/webm",
        direct_passthrough=True
    )

    response.headers.add("Content-Range", f"bytes {start}-{end}/{file_size}")
    response.headers.add("Accept-Ranges", "bytes")
    response.headers.add("Content-Length", str(length))

    return response
