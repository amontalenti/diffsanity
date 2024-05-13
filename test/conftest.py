import os
import sys
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import fs
fs  # ignore

TEST_ROOT = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.dirname(TEST_ROOT)

sys.path.insert(0, PROJECT_ROOT)
