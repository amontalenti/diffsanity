import os

from diffsanity import generate_hashes, get_file_hash

from data import Data


HELLO_MD5 = "746308829575e17c3331bbcb00c0898b"


def test_data():
    simple = Data("simple")

    dest = dict(simple.file_and_checksum("dest"))
    assert len(dest) > 1
    assert dest["hello.txt"] == HELLO_MD5

    src = dict(simple.file_and_checksum("src"))
    assert len(src) > 1
    assert src["one/hello.txt"] == HELLO_MD5

    assert len(list(simple)) == len(src) + len(dest)
    assert len(list(simple.iter())) == len(src) + len(dest)
    assert len(list(simple.iter("src"))) == len(src)
    assert len(list(simple.iter("dest"))) == len(dest)


def test_simple_hash():
    for file_path, fs_obj, checksum in Data("simple"):
        assert get_file_hash(file_path, fs_obj) == checksum


def test_simple_hashes():
    simple = Data("simple")
    for directory in simple.toplevel():
        hashes = generate_hashes(os.path.join(simple.path, directory))
        assert HELLO_MD5 in hashes
        assert len(hashes) > 1
