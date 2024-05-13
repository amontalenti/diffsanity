import functools
import os

import fs

TEST_ROOT = os.path.abspath(os.path.dirname(__file__))
DATA_ROOT = os.path.join(TEST_ROOT, "data")


class Data:
    """Load precomputed metadata of files at .../test/data/{name}.

    Example invocation to generate MD5SUMS on Linux:

        find . -type f                    |
          grep -v SUMS$                   |
          xargs -L 1 -P $(nproc) md5sum   |
          sort -k 2,2                     |
          tee BYTE_MD5SUMS
    """

    def __init__(self, name):
        self.path = os.path.join(DATA_ROOT, name)
        self.md5_dict = self.load(os.path.join(self.path, "BYTE_MD5SUMS"))
        self.verify_filepaths_match(self.path, self.md5_dict)

    def __iter__(self):
        return self.iter(algo=None)  # Use default algo.

    def file_and_checksum(self, folder, algo=None):
        "File, checksum pairs relative to top-level folder of test data."
        algo = algo or "md5"
        assert algo in ("md5",)
        checksum_dict = getattr(self, f"{algo}_dict")

        file_and_checksum = []
        for path, checksum in checksum_dict.items():
            if path.startswith(f"./{folder}/"):
                _, _, subpath = path.split("/", maxsplit=2)
                file_and_checksum.append((subpath, checksum))

        assert file_and_checksum
        return file_and_checksum

    def iter(self, folder=None, algo=None):
        """Iterate all top-level, include FS object between path, checksum."""
        if folder is not None:
            folder_list = [folder]
        else:
            folder_list = self.toplevel()

        pairs = functools.partial(self.file_and_checksum, algo=algo)
        some = None

        with fs.open_fs(self.path) as data_fs:
            for folder in folder_list:
                for file_path, checksum in pairs(folder):
                    some = True
                    path = f"{folder}/{file_path}"
                    yield path, data_fs, checksum

        assert some, "No data."

    def load(self, path):
        "Load file to checksum mapping from SUMS file at given path."
        file_to_checksum = {}
        with open(path) as f:
            for line in f:
                checksum, file_path = line.strip().split(maxsplit=1)
                assert file_path.startswith("."), "Use relative paths."
                file_to_checksum[file_path] = checksum
        return file_to_checksum

    def toplevel(self):
        "Get list of top-level folders within test data."
        for _, toplevel, _ in os.walk(self.path):
            return toplevel

    def verify_filepaths_match(self, root, file_to_checksum):
        "Assert checksum file list matches filesystem content."
        metadata = set(file_to_checksum.keys())

        filesystem = set()
        folder_fs = fs.open_fs(root)
        for path in sorted(folder_fs.walk.files()):
            path = path.lstrip("/")
            if "/" not in path and path.endswith("SUMS"):
                continue
            filesystem.add(f"./{path}")

        metadata_only = filesystem - metadata
        filesystem_only = metadata - filesystem

        assert not metadata_only, metadata_only
        assert not filesystem_only, filesystem_only
