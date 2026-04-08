import os
import zipfile
import tempfile
import asyncio
import aiofiles
from typing import Tuple, List
from fastapi import UploadFile
import shutil
import fnmatch
import tempfile

async def validate_file_patterns(directory: str, patterns: list) -> bool:
    """
    Validate that files matching the specified patterns exist in the directory.
    Returns True if all patterns have at least one matching file, False otherwise.
    """
    for pattern in patterns:
        if not any(fnmatch.fnmatch(os.path.relpath(os.path.join(root, file), directory), pattern)
                   for root, _, files in os.walk(directory) for file in files):
            return False
    return True

async def save_upload_to_temp(file: UploadFile):
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)
    
    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            await f.write(chunk)
    
    return file_path, temp_dir


async def extract_zip(file_path: str, extract_to: str) -> None:
    """
    Extract a zip file asynchronously to the specified directory.
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _extract_zip_sync, file_path, extract_to)


def _extract_zip_sync(file_path: str, extract_to: str) -> None:
    """
    Synchronous helper function to extract a zip file.
    """
    with zipfile.ZipFile(file_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)


async def zip_directory(directory: str, zip_name: str) -> str:
    """
    Zip a directory asynchronously and return the path to the zip file.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _zip_directory_sync, directory, zip_name)


def _zip_directory_sync(directory: str, zip_name: str) -> str:
    """
    Synchronous helper function to zip a directory.
    """
    zip_path = os.path.join(tempfile.mkdtemp(), zip_name)
    with zipfile.ZipFile(zip_path, "w") as zip_out:
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, directory)
                zip_out.write(file_path, arcname)
    return zip_path


def copy_files_preserving_hierarchy(source_dir: str, dest_dir: str, patterns: List[str]) -> None:
    """
    Copy files from the source directory to the destination directory based on patterns,
    preserving the original directory hierarchy.

    Args:
        source_dir (str): Path to the directory containing source files.
        dest_dir (str): Path to the destination directory.
        patterns (list): List of patterns to match files for copying.

    Returns:
        None
    """
    os.makedirs(dest_dir, exist_ok=True)

    for root, _, files in os.walk(source_dir):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, source_dir)  # Preserve the hierarchy
            # Check if the file matches any of the patterns
            if any(fnmatch.fnmatch(rel_path, pattern) for pattern in patterns):
                dest_path = os.path.join(dest_dir, rel_path)  # Preserve hierarchy in dest_dir
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)  # Create necessary directories
                shutil.copy2(file_path, dest_path)  # Copy file while preserving metadata

def find_file(file_dir: str, file_pattern: str) -> str:
    """
    Find the first file matching the given pattern in the specified directory.

    Args:
        file_dir (str): The directory to search in.
        file_pattern (str): The pattern to match files against.

    Returns:
        str: The path to the first matching file.

    Raises:
        FileNotFoundError: If no file matching the pattern is found.
    """
    for root, _, files in os.walk(file_dir):
        for file in files:
            rel_path = os.path.relpath(os.path.join(root, file), file_dir)
            if fnmatch.fnmatch(rel_path, file_pattern):
                return os.path.join(root, file)  # Return the first match
    raise FileNotFoundError(f"No file matching pattern '{file_pattern}' found in directory '{file_dir}'")