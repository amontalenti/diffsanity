import datetime as dt
import os
from hashlib import md5

import click
import fs
import rawpy
from fs.errors import ResourceNotFound
from fs.walk import Walker
from PIL import Image


def get_file_hash(file_path, fs_obj):
    """Generate an MD5 hash for the file's bytes, handling image files specially."""
    SKIP_RAW = False
    if SKIP_RAW:
        if file_path.lower().endswith((".cr2", ".cr3")):
            # Debug option to skip skip d5sum of RAW files since we know they are always
            # paired with JPG files, and this speeds things up
            return "0" * 8
    file_bytes = get_file_bytes(file_path, fs_obj)
    if file_bytes is None:
        # if not a known file type, we'll just chunk and md5 the file
        # examples: .mov, .mp4, .mlv
        with fs_obj.open(file_path, "rb") as f:
            hash_md5 = md5()
            while chunk := f.read(4096):
                hash_md5.update(chunk)
            return hash_md5.hexdigest()
    hash_md5 = md5(file_bytes)
    return hash_md5.hexdigest()


def get_file_bytes(file_path, fs_obj):
    """For known file types, convert the file into a byte array sans metadata."""
    if file_path.lower().endswith((".jpg", ".jpeg", ".png")):
        try:
            with fs_obj.open(file_path, "rb") as f:
                # using this technique strips Exif metadata on JPG/PNG image
                image = Image.open(f)
                image_bytes = image.tobytes()
                return image_bytes
        except Exception:
            return None
    elif file_path.lower().endswith((".cr2", ".cr3")):
        try:
            with fs_obj.open(file_path, "rb") as f, rawpy.imread(f) as raw:
                # using this technique strips any RAW metadata
                image_data = raw.postprocess()
                image = Image.fromarray(image_data)
                image_bytes = image.tobytes()
                return image_bytes
        except Exception:
            return None


def generate_primary_key(file_path, fs_obj):
    """
    Generates a primary key for the given file path using PyFilesystem2.

    The primary key is a tuple containing:
    - filename: the name of the file (not the full path)
    - mtime: last modification time of the file, as an integer timestamp
    - size: size of the file in bytes

    Parameters:
        file_path (str): The path to the file.
        fs_obj (FS): A PyFilesystem2 filesystem object.


    Returns:
        tuple: A tuple (filename, mtime, size) serving as the primary key.
    """
    # Split the file path into directory path and filename
    dir_path, filename = os.path.split(file_path)
    # Open the filesystem based on the directory path
    if not fs_obj.exists(file_path):
        raise ResourceNotFound(f"No file found at the specified path: {file_path}")
    info = fs_obj.getinfo(file_path, namespaces=["details"])
    # Get modification time as UTC ISO8601 date string
    utc_mtime = dt.datetime.utcfromtimestamp(int(info.modified.timestamp())).isoformat()
    # Get size in num bytes
    size = info.size
    return (utc_mtime, filename, size)


def generate_hashes(directory):
    """Generate hashes for all files in the directory."""
    print(f"Generating hashes for {directory}:")
    hashes = {}
    with fs.open_fs(directory) as fs_obj:
        for path in Walker().files(fs_obj):
            print(f"{path} | ", end="", flush=True)
            file_hash = get_file_hash(path, fs_obj)
            print(f"{file_hash}", end="", flush=True)
            primary_key = generate_primary_key(path, fs_obj)
            print(f" | {primary_key}", flush=True)
            hashes[file_hash] = path
    print(" Done.")
    return hashes


@click.group()
def cli():
    pass


@cli.command()
def version():
    """Display the version of the tool."""
    click.echo("diffsanity version 0.1")


@cli.command()
@click.argument("source_folder")
@click.argument("backup_folder")
@click.option(
    "-r",
    "--report",
    type=click.Path(),
    help="Generate a report file listing missing files.",
)
def check(source_folder, backup_folder, report):
    """Check that all files in source_folder are backed up in backup_folder."""
    source_hashes = generate_hashes(source_folder)
    backup_hashes = generate_hashes(backup_folder)

    # could cache the results here with a SQLite database or similar
    # would need to figure out how to hash the source and backup media drives (lsblk perhaps?)

    missing_hashes = {
        h: source_hashes[h] for h in source_hashes if h not in backup_hashes
    }

    def iterate_hashes():
        for hash, path in missing_hashes.items():
            click.echo(f"Missing {path} with hash {hash}")
            full_path = os.path.join(source_folder, path.lstrip("/"))
            yield full_path, path, hash

    if not missing_hashes:
        click.echo("All hashes from source folder are present in the backup folder.")
        return

    click.echo("Some hashes are missing in the backup folder:")
    if report:
        with open(report, "w") as file:
            for full_path, _, _ in iterate_hashes():
                file.write(f"{full_path}\n")
            click.echo(f"Missing file report generated in: {report}")
    else:
        for _, path, hash in iterate_hashes():
            full_path = os.path.join(source_folder, path.lstrip("/"))


if __name__ == "__main__":
    cli()
