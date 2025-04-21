import mimetypes

def is_audio_file(file_path):
    """
    Check if the given file is an audio file based on its MIME type.

    Args:
        file_path (str): Path to the file.

    Returns:
        bool: True if the file is an audio file, False otherwise.
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type is not None and mime_type.startswith('audio/')