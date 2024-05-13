from diffsanity import get_file_bytes

from data import Data


def test_unknown():
    for file_path, fs_obj, _ in Data("simple"):
        assert file_path.endswith(".txt")
        assert get_file_bytes(file_path, fs_obj) is None
