"""
BitBake Utility Functions (extract)
"""

# Copyright (C) 2004 Michael Lauer
#
# SPDX-License-Identifier: GPL-2.0-only
#

import re, fcntl, os, string, stat, shutil, time
import sys
import errno


def is_semver(version):
    """
        Is the version string following the semver semantic?

        https://semver.org/spec/v2.0.0.html
    """
    regex = re.compile(
    r"""
    ^
    (0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)
    (?:-(
        (?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)
        (?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*
    ))?
    (?:\+(
        [0-9a-zA-Z-]+
        (?:\.[0-9a-zA-Z-]+)*
    ))?
    $
    """, re.VERBOSE)

    if regex.match(version) is None:
        return False

    return True
