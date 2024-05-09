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

- `Pillow`, for handling JPG and other common image types
- `rawpy`, for handling Canon RAW (cr2/cr3) images
- `xxhash` (optional), for using a faster hashing algorithm than MD5
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

## Implementation details

### Consider the binary hash, not full file path

The paths aren't matched on source media and backup folder sides. Thus, we are
hunting for identical or nearly-identical files in different filepaths in the
backup folder tree. Since the full file path on either side is ignored for the
calculation of whether a given binary file is "missing" within `diffsanity` it
means you can know for sure a given source file has been backed up "somewhere"
in the backup folder.

### Strip the EXIF metadata by looking at image pixel bytes only

The most important filetype-specific rule `diffsanity` implements does hashes
of big photo files like JPGs and C-RAW while stripping EXIF metadata away. This
means that photo files that contain the same image pixels, but different
metadata, will hash to the same value. This helps especially because on Canon
hardware you have multiple SD/CF card writers set up in a dumb RAID and the
metadata across those RAID'ed media tends to get out of sync.

### Key files on `(filename, mtime, numbytes)` to enable hash caching

Rather than rehashing a backup folder, this tool will look for a file called
`filehash.sum`. This file contains pipe-separated values (` | `) to store
pre-computed hashes for "primary key" representations of the files, namely the
filename (as a str), mtime in ISO8601 format (as a str), and num bytes (as a
str). This is because computing an MD5 or other hash of large binary files is
CPU- and I/O-intensive, so the caching does speedups of up to 150,000% for
large file trees.

## Future ideas

### Support multiple source folders

In a common use case, let's say I have an SDCard and a CompactFlash card, both
plugged into the same USB-C reader. I want to check if all the data from both
of those is in the backup folder.

### Generate a patch script

Let's say I find out that 100 files from my SDCard are missing from the backup
folder. I'd like to have a patch script made available as a "repair plan" --
that is, a script that could rectify the situation. It could be as simple as
copying the files that are missing to a new folder with a name like
"patch-YYYY-MM-DD/", and then I can manually rename it afterwards.

### Extend into near-duplicate hashing algorithms

Right now, we're implementing hashing algorithms that are meant to find exact
duplicates -- at least as far as the image pixel data is concerned. You could
imagine extended`diffsanity` to support algorithms for "near duplicate"
detection. Although this wouldn't be as helpful in a backup context, it could
lead to techniques for clustering near-duplicate images with a shell-friendly
and UNIXy workflow, which could be quite cool.

## Concerns

### Advanced `rsync` and `rclone` usage

Though I know there isn't any tool out there that peers into JPG and C-RAW
files to look only at the "sensor bytes" rather than the full bytestream
including metadata, and that `rclone` and `rsync` definitely don't help with
that. I do wonder how much of `diffsanity` reinvents clever scripting of
`rsync` and `rclone`. For example, in my first cut at this problem I was going
to do the following:

- create a "stripped of metadata" temporary folder with the JPG and C-RAW files
- likewise create a parallel folder of same in destination
- use `rsync --dry-run` and/or `rclone check` to compare them

Another idea was to use an optimized tool like `md5deep -r`, and then only
do a further "peer-into-the-file" comparison if I find identically named
files with different hashes.

### CPU performance

This tool can suffer not just from GIL performance issues (single core) but
also I/O and CPU interleaving issues. When you look at how `md5deep` is
performant in its task, it says:

"By default, `md5deep` will create one producer thread to scan the file system
and one hashing thread per CPU core. Multi-threading causes output filenames to
be in non-deterministic order, as files that take longer to hash will be
delayed while they are hashed."

This is significantly more sophisticated than the single-thread, single-core
approach here.
