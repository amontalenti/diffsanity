# diffsanity - sanity checks for file backups

## Description

`diffsanity` is a tool designed to ensure file integrity between two or more
filesystems, typically used for verifying backups.

It generates MD5 hashes for all files in a source directory and checks that
these hashes are present in a backup directory. Special handling is included
for image files (JPG, PNG, CR2, CR3), where the tool processes images to strip
out EXIF metadata before hashing, ensuring that comparisons focus solely on the
image content.

For all other file types, `diffsanity` treats the files as binary blobs and
hashes their entire byte content.

## Dependencies

Install `diffsanity` by cloning the repository and installing the required
dependencies via `pip`. These requirements include:

- `Pillow`, for handling JPG images
- `rawpy`, for handling CR2 (aka RAW) images
- `PyFilesystem`, for traversing the filesystem
- `click`, for the CLI interface

## Usage

### `diffsanity.py check` sub-command

To verify that all files in the source directory are backed up correctly in the
backup directory, use the `check` sub-command:

```
python diffsanity.py check <source_folder> <backup_folder>
```

This command will recursively traverse the `source_folder`, generate hashes for
its files, and then ensure these hashes are present (somewhere) in the
`backup_folder`.

If any hashes are missing, diffsanity will report the missing files.

## Future Improvements

### Plain file, byte, and mtime hashing

Though using content-aware MD5 hashes was where this tool started, the truth
is, for many filesystem comparisons, doing filename, byte size, and mtime
comparisons is good enough. If you look at `rsync`, it doesn't bother with
checksums unless you ask it to do so. And if you look at `rclone`, it only uses
them if they are "essentially free" in the remote filesystem (e.g. Amazon S3).

### MD5 hash caching

MD5 hashes are expensive to calculate, especially for the backup disk, which,
pretty much by definition, contains a lot of data and files. It'd be nice to
cache ones that have already been calculated in some sort of SQLite database or
similar. This way, you only have to do it once, or update the MD5 hash if the
file, byte, and mtime changed for a given file (under assumption that if that
metadata changed, then so did the MD5).

Along with this, we might need a technique to identify the source folders and
backup folders. That is, what block device they are in. Perhaps using `lsblk`
or similar APIs.

### Multiple source folders

In a common use case, let's say I have an SDCard and a CompactFlash card, both
plugged into the same USB-C reader. I want to check if all the data from both
of those is in the backup folder.

### Patch script

Let's say I find out that 100 files from my SDCard are missing from the backup
folder. I'd like to have a patch script made available as a "repair plan" --
that is, a script that could rectify the situation. It could be as simple as
copying the files that are missing to a new folder with a name like
"patch-YYYY-MM-DD/", and then I can manually rename it afterwards.

## Concerns

### Advanced `rsync` and `rclone` usage

Though I know there isn't any tool out there that peers into JPG and CR2 files
to look only at the "sensor bytes" rather than the full bytestream including
metadata, and that `rclone` and `rsync` definitely don't help with that. I do
wonder how much of `diffsanity` reinvents clever scripting of `rsync` and
`rclone`. For example, in my first cut at this problem I was going to do the
following:

- create a "stripped of metadata" temporary folder with the JPG and CR2 files
- likewise create a parallel folder of same in destination
- use `rsync` or `rclone` to compare them

Another idea was to use an optimized tool like `md5deep -r`, and then only
do a further "peer-into-the-file" comparison if I find identically named
files with different hashes.

### Performance

This tool can suffer not just from GIL performance issues (single core) but
also I/O and CPU interleaving issues. When you look at how `md5deep` is
performant in its task, it says:

"By default, `md5deep` will create one producer thread to scan the file system
and one hashing thread per CPU core. Multi-threading causes output filenames to
be in non-deterministic order, as files that take longer to hash will be
delayed while they are hashed."

This is significantly more sophisticated than the single-thread, single-core
approach here.
