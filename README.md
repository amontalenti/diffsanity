# diffsanity - sanity checks for file backups

## Description

`diffsanity` is a tool designed to ensure file integrity between two or more
filesystems, typically used for verifying backups.

It generates MD5 hashes for all files in a source directory and checks that
these hashes are present in a backup directory. Special handling is included
for image files (JPG, PNG, CR2), where the tool processes images to strip out
EXIF metadata before hashing, ensuring that comparisons focus solely on the
image content.

For all other file types, `diffsanity` treats the files as binary blobs and
hashes their entire byte content.

## Dependencies

Install `diffsanity` by cloning the repository and installing the required dependencies via `pip`. These requirements include:

- Pillow, for handling JPG images
- rawpy, for handling CR2 (aka RAW) images
- PyFilesystem, for traversing the filesystem
- click, for the CLI interface

## Usage

### `diffsanity.py check` sub-command

To verify that all files in the source directory are backed up correctly in the
backup directory, use the `check` sub-command:

```
python diffsanity.py check <source_folder> <backup_folder>
```

This command will recursively traverse the `source_folder`, generate hashes for
its files, and then ensure these hashes are present (somewhere) in the `backup_folder`.

If any hashes are missing, diffsanity will report the missing files.
