from diffsanity import generate_primary_key

from data import Data


def test_consistency():
    generated = {}

    for file_path, fs_obj, _ in Data("simple"):
        generated[file_path] = generate_primary_key(file_path, fs_obj)

    prev = None
    for file_path, fs_obj, _ in Data("simple"):
        key = generate_primary_key(file_path, fs_obj)
        assert key == generated[file_path]
        assert key != prev
        prev = key
