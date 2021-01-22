#!/usr/bin/env python3

#
# Playground that mimics cargo fetch to prepare Bitbake crate fetcher
#
# SPDX-License-Identifier: GPL-2.0-only
#

import os

# As long as python-core does not contain toml or pytoml (under discussion)
# use our stolen copy from https://github.com/uiri/toml
import toml_copy as toml
#import toml
#import pytoml as toml

crates_withsource = {}
crates_nosource = {}

def print_crates():
    print("\nCrates with sources:")
    for key in sorted(crates_withsource):
        print("Name:", key, "Versions:", sorted(crates_withsource[key]))
    print("\nCrates no sources:")
    for key in sorted(crates_nosource):
        print("Name:", key, "Versions:", sorted(crates_nosource[key]))

def add_crate(crate_dict, filename):
    #print(crate_dict)
    if "name" in crate_dict and "version" in crate_dict:
        name = crate_dict["name"]
        version = crate_dict["version"]
        if "source" in crate_dict:
            source = crate_dict["source"]
            global crates_withsource
            if not name in crates_withsource:
                crates_withsource[name] = []
            if not version in crates_withsource[name]:
                crates_withsource[name].append(version)
        else:
            global crates_nosource
            if not name in crates_nosource:
                crates_nosource[name] = []
            if not version in crates_nosource[name]:
                crates_nosource[name].append(version)
    else:
        print("\n\nOoops in", filename)
        print(crate_dict)
        exit()


def toml_to_dict(filename):
    with open(filename, 'r') as file:
        toml_string = file.read()
    return toml.loads(toml_string)

def parse_crates(path):
    if not os.path.exists(path):
        return
    path = os.path.abspath(path)
    #print("Entering %s..." % path)

    # TODO: PREFER Cargo.lock
    # Cargo.toml
    filename = os.path.join(path, "Cargo.toml")
    is_lib = False
    if os.path.exists(filename):
        toml_dict = toml_to_dict(filename);

        if "workspace" in toml_dict:
            workspace = toml_dict["workspace"]
            for member in workspace["members"]:
                parse_crates(os.path.join(path, member))

        if "lib" in toml_dict:
            is_lib = True
        # move to Cargo.lock in case of binary (=not lib) below
        if is_lib:
            if "dependencies" in toml_dict:
                #print("Dependencies added by", filename)
                pat_deps = []
                for key, value in toml_dict["dependencies"].items():
                    # path dependency?
                    if isinstance(value, dict) and "path" in value:
                        newpath = os.path.join(path, value["path"])
                        pat_deps.append(newpath)
                    # git dependency?
                    elif isinstance(value, dict) and "git" in value:
                        value["version"] = "git"
                        if "name" not in value:
                            value["name"] = value["git"]
                        add_crate(value, filename)
                    else:
                        # Cargo.toml can set optional dependencies as [dependencies.<option>]
                        # They contain a 'package' entry which we must use (otherwised we'd select
                        # option as package name.) Note: we cannot interpret options here so fetch
                        # optional crates with source always
                        if "package" in value:
                            package_name = value.pop("package")
                        else:
                            package_name = key
                        if isinstance(value, dict):
                            value["name"] = package_name
                        else:
                            tmpval = {"name": package_name, "version": value}
                            value = tmpval
                        add_crate(value, filename)
                # paths
                for subpath in pat_deps:
                    parse_crates(subpath)

            # TODO target
    else:
        print("%s does not exist" % filename)

    # use Cargo.lock for binaries
    if not is_lib:
        filename = os.path.join(path, "Cargo.lock")
        if os.path.exists(filename):
            toml_dict = toml_to_dict(filename);
            if "package" in toml_dict:
                #print("Files added by", filename)
                for package_dict in toml_dict["package"]:
                    add_crate(package_dict, filename)


#parse_crates("/home/superandy/data/git-projects/rust/spotifyd")
parse_crates("/home/superandy/data/git-projects/rust/rand")
#parse_crates("/home/superandy/tmp/oe-core-glibc/work/cortexa72-mortsgna-linux/firefox/68.9.0esr-r0/firefox-68.9.0")

print()
print_crates()
