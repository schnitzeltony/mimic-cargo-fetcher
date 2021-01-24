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


class VersionStringException(Exception):
    """Exception raised when an invalid version specification is found"""

def explode_version(s):
    r = []
    alpha_regexp = re.compile(r'^([a-zA-Z]+)(.*)$')
    numeric_regexp = re.compile(r'^(\d+)(.*)$')
    while (s != ''):
        if s[0] in string.digits:
            m = numeric_regexp.match(s)
            r.append((0, int(m.group(1))))
            s = m.group(2)
            continue
        if s[0] in string.ascii_letters:
            m = alpha_regexp.match(s)
            r.append((1, m.group(1)))
            s = m.group(2)
            continue
        if s[0] == '~':
            r.append((-1, s[0]))
        else:
            r.append((2, s[0]))
        s = s[1:]
    return r

def split_version(s):
    """Split a version string into its constituent parts (PE, PV, PR)"""
    s = s.strip(" <>=")
    e = 0
    if s.count(':'):
        e = int(s.split(":")[0])
        s = s.split(":")[1]
    r = ""
    if s.count('-'):
        r = s.rsplit("-", 1)[1]
        s = s.rsplit("-", 1)[0]
    v = s
    return (e, v, r)

def vercmp_part(a, b):
    va = explode_version(a)
    vb = explode_version(b)
    while True:
        if va == []:
            (oa, ca) = (0, None)
        else:
            (oa, ca) = va.pop(0)
        if vb == []:
            (ob, cb) = (0, None)
        else:
            (ob, cb) = vb.pop(0)
        if (oa, ca) == (0, None) and (ob, cb) == (0, None):
            return 0
        if oa < ob:
            return -1
        elif oa > ob:
            return 1
        elif ca is None:
            return -1
        elif cb is None:
            return 1
        elif ca < cb:
            return -1
        elif ca > cb:
            return 1

def vercmp(ta, tb):
    (ea, va, ra) = ta
    (eb, vb, rb) = tb

    r = int(ea or 0) - int(eb or 0)
    if (r == 0):
        r = vercmp_part(va, vb)
    if (r == 0):
        r = vercmp_part(ra, rb)
    return r

def vercmp_string(a, b):
    ta = split_version(a)
    tb = split_version(b)
    return vercmp(ta, tb)

def vercmp_string_op(a, b, op):
    """
    Compare two versions and check if the specified comparison operator matches the result of the comparison.
    This function is fairly liberal about what operators it will accept since there are a variety of styles
    depending on the context.
    """
    res = vercmp_string(a, b)
    if op in ('=', '=='):
        return res == 0
    elif op == '<=':
        return res <= 0
    elif op == '>=':
        return res >= 0
    elif op in ('>', '>>'):
        return res > 0
    elif op in ('<', '<<'):
        return res < 0
    elif op == '!=':
        return res != 0
    else:
        raise VersionStringException('Unsupported comparison operator "%s"' % op)


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
