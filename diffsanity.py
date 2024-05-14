import functools
import datetime as dt
import os
from hashlib import md5

import click
import fs
import rawpy
from fs.errors import ResourceNotFound
from fs.walk import Walker
from PIL import Image
from pi_heif import register_heif_opener
from xxhash import xxh32, xxh64, xxh128

register_heif_opener()


def pillow_bytes_no_exif_metadata(file_path, fs_obj):
    pass


def rawpy_bytes_no_exif_metadata(file_path, fs_obj):
    pass


def file_bytes(file_path, fs_obj):
    pass


def filename_mtime_numbytes(file_path, fs_obj):
    pass


class DiffSanityPlan:
    """This class is the start of a refactoring plan to use the above
    functions to clean up the code below.

    This will remove all the if/else branches and flags from the below code and
    make it more delcarative."""

    hash_fn_options = (md5, xxh32, xxh64, xxh128)

    # xxh128 may be 20% faster but md5 is more standard
    hash_fn = md5

    custom_filetype_handlers = {
        # compressed photos (JPGs)
        ("jpg", "jpeg", "heif", "png"): pillow_bytes_no_exif_metadata,
        # raw photos (C-RAW)
        ("cr2", "cr3"): rawpy_bytes_no_exif_metadata,
        # encoded videos
        ("mov", "mp4"): file_bytes,
        # raw videos
        ("mlv", "yuv"): file_bytes,
    }

    # hash full file bytes if no custom handler registered
    default_filetype_handler = file_bytes

    # filename (not path) as str, mtime (as ISO8601 str), num bytes (as str)
    file_primary_key = filename_mtime_numbytes

    # where hashing results in backup folder are stroed as caching speedup
    manifest_file = "filehash.sum"

    # rewrite manifest in backup folder upon every successful run?
    rewrite_manifest = False

    # skip .cr2/.cr3 files for debugging to speed up repeated test runs?
    debug_skip_raw = False

    # skip % of files in source for debugging to speed up repeated test runs
    # 0 means 100% of files are processed (0 are skipped)
    debug_skip_percent = 0


#
# End of refactoring plan, start of the working implementation of diffsanity
# --------------------------------------------------------------------------
#


def get_file_hash(file_path, fs_obj):
    """Generate an MD5 hash for the file's bytes, handling image files specially."""
    SKIP_RAW = False
    if SKIP_RAW:
        if file_path.lower().endswith((".cr2", ".cr3")):
            # Debug option to skip skip md5sum of RAW files since we know they are always
            # paired with JPG files, and this speeds things up a whole lot
            return "0" * 8

    file_bytes = get_file_bytes(file_path, fs_obj)
    hash_fn = md5

    USE_XXHASH_ALGO = False
    if USE_XXHASH_ALGO:
        # Debug option to try using the xxhash library, as described here:
        # https://xxhash.com/
        hash_fn = xxh128

    if file_bytes is None:
        # if not a known file type, we'll just chunk and md5 the file
        # examples: .mov, .mp4, .mlv
        with fs_obj.open(file_path, "rb") as f:
            hasher = hash_fn()
            while chunk := f.read(4096):
                hasher.update(chunk)
            return hasher.hexdigest()
    hasher = hash_fn(file_bytes)
    return hasher.hexdigest()


def get_file_bytes(file_path, fs_obj):
    """For known file types, convert the file into a byte array sans metadata."""
    if file_path.lower().endswith((".jpg", ".jpeg", ".png", ".heif")):
        try:
            with fs_obj.open(file_path, "rb") as f:
                # using this technique strips Exif metadata on JPG image
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
    - mtime: last modification time of the file, as an ISO8601 timestamp str
    - filename: the name of the file (not the full path)
    - size: size of the file in bytes, as a str

    Parameters:
        file_path (str): The path to the file.
        fs_obj (FS): A PyFilesystem2 filesystem object.

    Returns:
        tuple: A 3-tuple (mtime, filename, size) as the primary key.
    """
    # Split the file path into directory path and filename
    dir_path, filename = os.path.split(file_path)
    # Open the filesystem based on the directory path
    if not fs_obj.exists(file_path):
        raise ResourceNotFound(f"No file found at the specified path: {file_path}")
    info = fs_obj.getinfo(file_path, namespaces=["details"])
    # Get modification time as UTC ISO8601 date string
    mtime = dt.datetime.utcfromtimestamp(int(info.modified.timestamp())).isoformat()
    # Get size in num bytes
    size = str(info.size)
    return (mtime, filename, size)


def get_manifest(directory):
    """Looks for `filehash.sum` in directory, parses it, returns cachedict.

    Returns empty dictionary (`{}`) if file isn't found."""
    with fs.open_fs(directory) as fs_obj:
        if fs_obj.exists("filehash.sum"):
            with fs_obj.open("filehash.sum") as manifest:
                cachedict = {
                    (datestr, filestr, bytestr): md5sum
                    for datestr, filestr, bytestr, md5sum in (
                        line.strip().split(" | ") for line in manifest
                    )
                }
                return cachedict
    return {}


def generate_hashes(directory):
    """Generate hashes for all files in the directory."""
    click.info(f"Generating hashes for {directory} ('*' means cache hit):")
    hashes = {}
    cachedict = get_manifest(directory)
    with fs.open_fs(directory) as fs_obj:
        for path in Walker().files(fs_obj):
            primary_key = generate_primary_key(path, fs_obj)
            # either cached value or new file hash
            if primary_key in cachedict:
                cache_hit = "*"
                file_hash = cachedict[primary_key]
            else:
                cache_hit = ""
                file_hash = get_file_hash(path, fs_obj)
            click.echo(f"{path} | ", nl=False)
            # {cache_hit} is just "*" when there is a hit
            click.echo(f"{cache_hit}{file_hash}", nl=False)
            click.echo(f" | {primary_key}", nl=False)
            click.echo("")
            hashes[file_hash] = path
    click.info(" Done.")
    return hashes


# Patch click with variations of `echo`.
click.info = functools.partial(click.echo, err=True)
click.err = functools.partial(click.echo, err=True)


@click.group()
def cli():
    pass


@cli.command()
def version():
    """Display the version of the tool."""
    click.echo("diffsanity version 0.1")


@cli.command()
@click.argument("folder")
def manifest(folder):
    """Check for manifest file (filehash.sum) and print manifest first 5 lines."""
    cachedict = get_manifest(folder)
    num_entries = len(cachedict)
    filehash_sum = f"{folder}/filehash.sum"
    if num_entries == 0:
        click.err(f"No {filehash_sum} file found, or no manifest entries in file.")
        return
    click.info(f"{filehash_sum} file found ({num_entries} entries). Printing first 5:")
    for i, (primary_key, hash) in enumerate(cachedict.items(), 1):
        click.echo(primary_key, hash)
        if i == 5:
            return


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
    """Check that all files in source_folder are backed up in backup_folder.

    Note: currently, though `filehash.sum` manifest files are supported, they
    are not automatically generated upon running this tool. That will come in
    the next version."""
    source_hashes = generate_hashes(source_folder)
    backup_hashes = generate_hashes(backup_folder)

    missing_hashes = {
        h: source_hashes[h] for h in source_hashes if h not in backup_hashes
    }

    def iterate_hashes():
        for hash, path in missing_hashes.items():
            click.err(f"Missing {path} with hash {hash}")
            full_path = os.path.join(source_folder, path.lstrip("/"))
            yield full_path, path, hash

    if not missing_hashes:
        click.info("All hashes from source folder are present in the backup folder.")
        return

    click.err("Some hashes are missing in the backup folder:")
    if report:
        with open(report, "w") as file:
            for full_path, _, _ in iterate_hashes():
                file.write(f"{full_path}\n")
            click.err(f"Missing file report generated in: {report}")
    else:
        for _, _, _ in iterate_hashes():
            # iterate_hashes() will generate some basic console output
            pass

    click.get_current_context().exit(1)


if __name__ == "__main__":
    cli()
