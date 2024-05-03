import os
from hashlib import md5

import click
import fs
import rawpy
from fs.walk import Walker
from PIL import Image

# FIXME: obviously, it'd be awesome to generate the hashes once, store them in a database,
# and then only regenerate them for files that had change in numbytes or mtime. This way
# I wouldn't have to regenerate the hashes of the backup_folder even as I do comparisons
# against several source_folders


def get_file_hash(file_path, fs_obj):
    """Generate an MD5 hash for the file's bytes, handling image files specially."""
    if file_path.lower().endswith((".cr2", ".cr3")):
        # FIXME: temporarily skipping md5sum of RAW files since we know they are always
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


def generate_hashes(directory):
    """Generate hashes for all files in the directory."""
    print(f"Generating hashes for {directory}:")
    hashes = {}
    with fs.open_fs(directory) as fs_obj:
        for path in Walker().files(fs_obj):
            print(f"{path} | ", end="", flush=True)
            file_hash = get_file_hash(path, fs_obj)
            print(f"{file_hash}", flush=True)
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

    if missing_hashes:
        click.echo("Some hashes are missing in the backup folder:")
        if report:
            with open(report, "w") as file:
                for hash, path in missing_hashes.items():
                    click.echo(f"Missing {path} with hash {hash}")
                    full_path = os.path.join(source_folder, path.lstrip("/"))
                    file.write(f"{full_path}\n")
                click.echo(f"Missing file report generated in: {report}")
        else:
            # FIXME: code duplication
            for hash, path in missing_hashes.items():
                full_path = os.path.join(source_folder, path.lstrip("/"))
                click.echo(f"Missing {path} with hash {hash}")
    else:
        click.echo("All hashes from source folder are present in the backup folder.")


if __name__ == "__main__":
    cli()
