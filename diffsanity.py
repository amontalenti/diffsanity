import click
from hashlib import md5
from PIL import Image
import rawpy
import fs
from fs.walk import Walker
import os

def get_file_hash(file_path, fs_obj):
    """Generate an MD5 hash for the file's bytes, handling image files specially."""
    if file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
        with fs_obj.open(file_path, 'rb') as f:
            image = Image.open(f)
            image_bytes = image.tobytes()
    elif file_path.lower().endswith('.cr2'):
        with fs_obj.open(file_path, 'rb') as f, rawpy.imread(f) as raw:
            image_data = raw.postprocess()
            image = Image.fromarray(image_data)
            image_bytes = image.tobytes()
    else:
        with fs_obj.open(file_path, 'rb') as f:
            hash_md5 = md5()
            while chunk := f.read(4096):
                hash_md5.update(chunk)
            return hash_md5.hexdigest()

    hash_md5 = md5(image_bytes)
    return hash_md5.hexdigest()

def generate_hashes(directory):
    """Generate hashes for all files in the directory."""
    hashes = {}
    with fs.open_fs(directory) as fs_obj:
        for path in Walker().files(fs_obj):
            file_hash = get_file_hash(path, fs_obj)
            hashes[file_hash] = path
    return hashes

@click.group()
def cli():
    pass

@cli.command()
def version():
    """Display the version of the tool."""
    click.echo("diffsanity version 0.1")

@cli.command()
@click.argument('source_folder')
@click.argument('backup_folder')
@click.option('-r', '--report', type=click.Path(), help='Generate a report file listing missing files.')
def check(source_folder, backup_folder, report):
    """Check that all files in source_folder are backed up in backup_folder."""
    source_hashes = generate_hashes(source_folder)
    backup_hashes = generate_hashes(backup_folder)

    missing_hashes = {h: source_hashes[h] for h in source_hashes if h not in backup_hashes}

    if missing_hashes:
        click.echo("Some hashes are missing in the backup folder:")
        if report:
            with open(report, 'w') as file:
                for hash, path in missing_hashes.items():
                    click.echo(f"Missing {path} with hash {hash}")
                    full_path = os.path.join(source_folder, path.lstrip("/"))
                    file.write(f"{full_path}\n")
                    click.echo(f"Missing file report generated in: {report}")
        else:
            # FIXME: duplication
            for hash, path in missing_hashes.items():
                full_path = os.path.join(source_folder, path.lstrip("/"))
                click.echo(f"Missing {path} with hash {hash}")
    else:
        click.echo("All hashes from source folder are present in the backup folder.")

if __name__ == '__main__':
    cli()
