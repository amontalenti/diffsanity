import os

from click.testing import CliRunner
from diffsanity import check

from data import Data

BOTH = [
    "/hello.txt",
    "/one/hello.txt",
    "/sub/shorter.txt",
    "/two/a-much-longer-filename.txt",
]

MISSING = [
    "/two/more/src-only.txt",
]


def test_simple():
    simple = Data("simple")
    src = os.path.join(simple.path, "src")
    dest = os.path.join(simple.path, "dest")

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(check, [src, dest])

    for file_path in BOTH:
        assert file_path in result.stdout
        assert file_path not in result.stderr

    for file_path in MISSING:
        assert file_path in result.stderr

    assert result.exit_code != 0
