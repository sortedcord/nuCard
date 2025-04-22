import mimetypes
import os

def is_audio_file(file_path) -> bool:
    """
    Check if the given file is an audio file based on its MIME type.

    Args:
        file_path (str): Path to the file.

    Returns:
        bool: True if the file is an audio file, False otherwise.
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type is not None and mime_type.startswith('audio/')

def iterdir(path) -> list:
    """
    Give a list containing paths of all files (recursively).

    Args:
        path (str): Path to the directory.

    Returns:
        list: List of file paths.
    """
    file_paths = []
    for entry in os.listdir(path):
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path):
            file_paths.extend(iterdir(full_path))
        elif os.path.isfile(full_path):
            file_paths.append(full_path)
    return file_paths

def match_property(key, properties):
    _ = []
    for prop in properties:
        if key == prop:
            return prop
        elif key in prop:
            _.append(prop)
    if _:
        return _[0]

