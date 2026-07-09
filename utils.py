import hashlib
from datetime import datetime


def file_hash(uploaded_file):
    """Create a hash for an uploaded file so duplicate uploads can be detected."""
    uploaded_file.seek(0)
    file_bytes = uploaded_file.getvalue()
    uploaded_file.seek(0)
    return hashlib.md5(file_bytes).hexdigest()


def current_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
