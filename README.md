# diffsanity - sanity checks via hashing and diffing

## Description

`diffsanity` is a tool designed to ensure file integrity between two or more
filesystems, typically used for verifying backups.

It generates MD5 hashes for all files in a source directory and checks that
these hashes are present in a backup directory. Special handling is included
for image files (JPG, PNG, HEIF, CR2, CR3), where the tool processes images to
strip out EXIF metadata before hashing, ensuring that comparisons focus solely
on the image content.

For all other file types, `diffsanity` treats the files as binary blobs and
hashes their entire byte content.

## Why?

This tool scratches my own itch as an amateur photographer with terabytes of
photography data and way too many photo media cards with layers of backup
redundancy that don't quite fit with one another.

This includes a ["dual-slot dumb RAID"][raid] on both of my camera bodies, a
USB3 SSD drive as a "lazy dumping ground" of all my photos across shooting
sessions, a `restic` repo I use as my snapshot-based chunk-deduped backup
repository, and `rclone` which does a WAN copy of my restic repo to Backblaze
B2 for off-site backup, completing my 3-2-1 backup scheme.

`diffsanity` fills a gap in my backup workflow that I couldn't fill with
existing tools. That is: making absolutely sure, as a sanity check, that all
the image data from my SD cards and CompactFlash cards made it onto my backup
SSD drive.

It stems from the fact that many of my photos/videos are not exact binary
duplicates, but instead near-duplicates, due to edge cases around metadata
handling.

So I always wonder, "did I manage to back everything up from my two SD
cards for my Canon R7, as well as the 1 SD Card and 1 CF Card for my Canon 5D
Mark III?" And I couldn't get `rsync` or `rclone check` to answer this question
for me. So I rolled my own in Python.

See [amontalenti.com/photos][photos] for more on my approach to photography.

I worked on `diffsanity` during Recurse Center's **Never Graduate Week**, aka
NGW 2024, in their lovely space in Brooklyn, NY. Thank you, RC! :octopus:

More info on RC [here][RC] and more info on what NGW is like [here][NGW].
Never Graduate!

[photos]: https://amontalenti.com/photos
[RC]: https://recurse.com
[NGW]: https://www.recurse.com/blog/114-never-graduate-week-2017-how-we-planned-and-ran-our-annual-alumni-week

## Dependencies

Install `diffsanity` by cloning the repository and installing the required
dependencies via `pip`. These requirements include:

- `Pillow`, for handling JPG and other common image types
- `pi-heif`, for handling HEIF image files common on Apple devices
- `rawpy`, for handling Canon RAW (CR2/CR3) images
- `xxhash` (experimental), for using a faster hashing algorithm than MD5
- `PyFilesystem`, for traversing the filesystem
- `click`, for the building the CLI sub-commands and help/usage

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

You can use the `-r, --report` option to produce a missing file report in a
plain text file.

### `diffsanity.py manifest` sub-command

To speed up repeated runs of `diffsanity` against large folders of binary
images, it generates a manifest file (named `filehash.sum`) in the root of the
folder. This file contains pre-computed hashes for each of the files, keyed by
`(filename, mtime, and numbytes)`.

This results in speedups of over 100,000% in cases where you are doing repeated
runs and only a few new files have been added to the source or backup folder.
In my real-world testing, a `check` run that took **2 hours** dropped to **5
seconds.** (That one felt good.)

That is, when run against a source media card with 3,000 image files (250GB of
data) and a backup SSD drive 12,000 image files (1TB data), calculating all the
hashes would normally take **2 hours** but when consulting the manifest files
would run in **5 seconds instead**. (Feels even better the second time.)

See below for more implementation details.

```
python diffsanity.py manifest <folder>
```

This subcommand checks whether a `filehash.sum` manifest file is present in the
folder, and, if it is, it prints a few of its entries. It does not generate
the manifest; a manifest is meant to be generated after you use the `check` sub-command.

## High-Level Design

This Python class does a nice job of documenting the high level design of
`diffsanity`:

```python
class DiffSanityPlan:
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
```

The design is covered with prose below.

## Example run

Against a source and backup folder like this:

```
❯ tree example
example
├── backup
│   └── sdcard1
│       ├── 1I1A3890.mp4
│       ├── IU0C5091.CR2
│       ├── IU0C5091.JPG
│       └── README.txt
└── src
    ├── 1I1A3890-Copy.mp4
    ├── IU0C5091.CR2
    ├── IU0C5091.JPG
    ├── IU0C5094.CR2
    ├── IU0C5094.JPG
    └── README.txt
```

Running diffsanity returns this output:

```
❯ python diffsanity.py check example/src/ example/backup/

Generating hashes for example/src/ ('*' prefix on hash means cache hit):
/IU0C5091.JPG | d865a5863daf8c0acb65de4ef814d5bd
/IU0C5091.CR2 | 20b388dd349bf471d5d4fab6d1e69dff
/README.txt | d8e8fca2dc0f896fd7cb4cb0031ba249
/IU0C5094.CR2 | 2ea442fd190a0de1331456a06d2c4c79
/IU0C5094.JPG | 9918a3cf405b18b583c7a10a03cf5304
/1I1A3890-Copy.mp4 | 9db7e5a8b126e2a93dc26dec7ae5a40e
Done.

Generating hashes for example/backup/ ('*' prefix on hash means cache hit):
/sdcard1/IU0C5091.JPG | d865a5863daf8c0acb65de4ef814d5bd
/sdcard1/IU0C5091.CR2 | 20b388dd349bf471d5d4fab6d1e69dff
/sdcard1/README.txt | d8e8fca2dc0f896fd7cb4cb0031ba249
/sdcard1/1I1A3890.mp4 | 9db7e5a8b126e2a93dc26dec7ae5a40e
 Done.

Some hashes are missing in the backup folder:
Missing /IU0C5094.CR2 with hash 2ea442fd190a0de1331456a06d2c4c79
Missing /IU0C5094.JPG with hash 9918a3cf405b18b583c7a10a03cf5304
```

There are 3 interesting things to notice about this:

- it found 2 photo files missing from the backup (named `IUOC5094.JPG/CR2`)
- it did not consider `1I1A3890.mp4` to be missing, because a hash-identical file
  named `1I1A3890-Copy.mp4` is in the backup folder
- it worked regardless of the fact that the backup folder has the files in a
  parent directory called `/sdcard1/` even though no such parent directory
  exists in the source folder

Of course, you can also tell that it used MD5 hashes throughout the process.

## Implementation details

### Consider the binary hash, not full file path

The full paths needn't match on source media and backup folder sides. This is
an intentional design decision, since we can use the binary hash to know a given
file made it "somewhere" in the backup folder tree.

Thus, this tool hunts for identical or nearly-identical files in different
filepaths in the backup folder tree. When it doesn't find a given md5 hash
from the source in the backup folder, that's what it reports as a missing file.

Since the full file path on either side is ignored for the calculation of
whether a given binary file is "missing" within `diffsanity`, it means when it
reports there are no missing files from source to backup, you can know **for
sure** a given source file has been backed up "somewhere" in the backup folder.
Thus the sanity moniker.

The whole idea is that I run this before wiping source media as a final "sanity
check". Usually, my source folders are mounted SD Cards or CF Cards, which I want
to wipe clean. But I also want to know, for sure, that their contents have been
backed up. And that's even if I haven't actually backed up **that specific
card**, because maybe it is itself meant to be a ["dual-slot dumb RAID"][raid]
backup of a different card that I've already backed up.

### Strip the EXIF metadata by looking at image pixel bytes only

The most important filetype-specific rule `diffsanity` implements is to hash
big photo files like JPGs and C-RAW while stripping EXIF metadata away. This
means that photo files that contain the same image pixels, but different
metadata, will hash to the same value.

This helps especially because on Canon hardware you have multiple SD/CF card
writers set up in a ["dual-slot dumb RAID"][raid] and the metadata across those
RAID'ed media tends to get out of sync. A simple example here is that I might
mark a photograph as a "favorite" or "keeper" on my camera body, which modifies
the JPG/RAW's "Rating" property in the EXIF metadata. But the way the "dumb
RAID" in these Camera bodies works, it only modifies the EXIF metadata for the
"primary" card, not the backup/RAID'ed card.

[raid]: https://www.eos-magazine.com/articles/eos_feature/dual-card-slot.html

That means I can end up in situations where I have identically named files,
with identical image sensor content, but different EXIF metadata, and thus
different md5 hashes. Thus a tool like `rclone` and `rsync` will think these
are different files. But `diffsanity` can peer inside the files thanks to its
filetype-specific rules.

### Key files on `(filename, mtime, numbytes)` to enable hash caching

Rather than rehashing an entire backup folder every time `check` runs, this
tool will look for a file called `filehash.sum`. This file contains
pipe-separated values (` | `) to store pre-computed hashes for "primary key"
representations of the files, namely the filename (as a str), mtime in ISO8601
format (as a str), and num bytes (as a str).

This is because computing an MD5 or other hash of large binary files is CPU-
and I/O-intensive, so the caching does speedups of up to 100,000% for large
file trees.

## Future ideas

### Support multiple source folders

In a common use case, let's say I have an SD Card and a CompactFlash card, both
plugged into the same USB-C reader. I want to check if all the data from both
of those is in the backup folder. I could support this by implementing
something like `--and, -a`, as in:

```
python diffsanity src1/ --and src2/ --and src3/ backup/
```

... which would scan `src1/`, `src2/`, and `src3/` before comparing against the
backup folder `backup/`.

### Support videos the same way the tool supports images

The same EXIF metadata problem exists for video, and `exiftool` is able to
see EXIF metadata on Canon MP4 video files. But stripping EXIF metadata away
from videos is a bit more involved. I wasn't sure whether to pull in something
like `ffmpeg-python` (which might be slow and have complex dependencies), or to
just shell out to...

```
exiftool -all= FILES
```

... since that strips the metadata rather quickly through some binary hacking.
The issue with running `exiftool` is that it'd create temporary files so I might
have to use some I/O buffer tricks.

There's also `PyExifTool` which is a command-line wrapper. Anyway, for now, we
do full binary md5 hashes on videos since it's very uncommon for me to edit
video metadata anyway, and I wanted to save some time.

### Generate a patch script

Let's say I find out that 100 files from my SD Card are missing from the backup
folder. I'd like to have a patch script made available as a "repair plan" --
that is, a script that could rectify the situation. It could be as simple as
copying the files that are missing to a new folder with a name like
"patch-YYYY-MM-DD/", and then I can manually rename it afterwards.

The idea is that after you run the patch script, you could re-run `diffsanity
check`, and find out there are no longer any missing files since the patch
script got all the files into the backup (in the patch folder).

### Extend into near-duplicate hashing algorithms

Right now, we're implementing hashing algorithms that are meant to find exact
duplicates -- at least as far as the image pixel data is concerned. You could
imagine extending `diffsanity` to support algorithms for "near duplicate"
detection. Although this wouldn't be as helpful in a backup context, it could
lead to techniques for clustering near-duplicate images with a shell-friendly
and UNIXy workflow, which could be quite cool.

An example Python library to use for this would be [imagehash][imagehash],
which supports average, perceptual, difference, wavelet, and crop-resistant
hashing algorithms.

A use case would be to organize rapid-fire "burst" photos into folders, much
the same way that Google Photos supports ["Photo Stacks"][stacks]. That'd be
especially helpful for wildlife, sports, and action photographers because the
high-framerate burst shooting of modern mirrorless and DSLR cameras leads to an
explosion of files, each of which is almost like a frame of a movie. By using
an image hashing algorithm, we could perhaps cluster these "burst sessions"
together into a stack and move the files after the first one in a series into a
neat folder. But this seems pretty far outside the current remit of `diffsanity`
as a backup tool, so I'll leave it here as an idea for now.

[stack]: https://support.google.com/photos/answer/14169846?hl=en

[imagehash]: https://pypi.org/project/ImageHash/

## Concerns

### Advanced `rsync` and `rclone` usage

I am pretty sure there isn't a tool out there that peers into JPG and C-RAW
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

The clincher for me to build my own tool was that I couldn't figure out how to
work around these two intrinsic problems two my use case:

- no custom filetype hashing rules (e.g. hash jpg _without_ exif metadata,
  _just_ hash the jpg pixel data only)
- requirement that source and destination files are in same relative path of
  file tree, e.g. `src/a/b` needs to be in `dest/a/b`, no match if `b` is
  actually in `dest/c/d/e/b`, even if `b` is md5 identical on both sides

Once I realized that both of these problems could be handled pretty easily in
Python code, and that `PyFilesystem2`, `Pillow`, and `hashlib.md5` could do the
work I needed, I had now entered a pleasurable rabbit hole of coding.

### CPU performance when hashing

This tool can suffer not just from GIL performance issues (single core) but
also I/O and CPU interleaving issues. When you look at how `md5deep` is
performant in its task, it says:

"By default, `md5deep` will create one producer thread to scan the file system
and one hashing thread per CPU core. Multi-threading causes output filenames to
be in non-deterministic order, as files that take longer to hash will be
delayed while they are hashed."

This is significantly more sophisticated than the single-thread, single-core
approach here.
