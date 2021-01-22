#!/usr/bin/env python3

#
# Playground that mimics cargo fetch to prepare Bitbake crate fetcher
#
# SPDX-License-Identifier: GPL-2.0-only
#

import os
import json

# As long as python-core does not contain toml or pytoml (under discussion)
# use our stolen copy from https://github.com/uiri/toml
import toml
#import pytoml as toml

import semver

class CrateDependencies:
    def __init__(self, crate_name, crate_version, crate_lockfile, reg_index_basepath):
        self.crate_name = crate_name
        self.crate_version = crate_version
        self.crate_lockfile = crate_lockfile
        self.reg_index_basepath = reg_index_basepath
        self.depend_crates = {}
        self.depend_unkown = {}
        self.file_parsed_currently = ""

    def find_dependencies(self):
        # Prefer Cargo.lock if shipped
        if os.path.exists(self.crate_lockfile):
            self.file_parsed_currently = self.crate_lockfile
            print("Parsing %s for dependencies." % self.crate_lockfile)
            toml_dict = self.toml_to_dict(self.crate_lockfile)
            if "package" in toml_dict:
                for package_dict in toml_dict["package"]:
                    self.add_crate(package_dict, "version", True)
            else:
                # TODO error handling
                print("%s is invalid - no 'package' header found" % self.crate_lockfile)
            return
        else:
            if self.find_crate_dependencies_in_index(self.crate_name, 
                                                     self.crate_version, 
                                                     self.reg_index_basepath):
                print("Use dependencies of %s-%s from index." % (self.crate_name, self.crate_version))
            else:
                print("TODO call cargo-native")

    def print_crates(self):
        print("\nDepend crates:")
        for key in sorted(self.depend_crates):
            print("Name:", key, "Versions:", sorted(self.depend_crates[key]))
        print("\nUnhandled depends:")
        for key in sorted(self.depend_unkown):
            print("Name:", key, "Versions:", sorted(self.depend_unkown[key]))

    def add_crate(self, crate_dict, version_tag, source_info_required):
        # Note on source_info_required:
        # * In Cargo.lock dependency entries without 'source' are in-tree must
        #   be ignored
        # * In files from registry-index there is no source entry
        if "name" in crate_dict and version_tag in crate_dict:
            name = crate_dict["name"]
            version = crate_dict[version_tag]
            if not source_info_required or "source" in crate_dict:
                if not name in self.depend_crates:
                    self.depend_crates[name] = []
                if not version in self.depend_crates[name]:
                    self.depend_crates[name].append(version)
            else:
                if not name in self.depend_unkown:
                    self.depend_unkown[name] = []
                if not version in self.depend_unkown[name]:
                    self.depend_unkown[name].append(version)
        else:
            print("\n\nOoops in", self.file_parsed_currently)
            print(crate_dict)
            exit()

    @staticmethod
    def toml_to_dict(filename):
        with open(filename, 'r') as file:
            toml_string = file.read()
        return toml.loads(toml_string)

    @staticmethod
    def build_pathname_index(crate_name, basepath):
        if len(crate_name) > 3:
            indexpath = crate_name[0:2] + '/' + crate_name[2:4]
        elif len(crate_name) == 3:
            indexpath = '3/' + crate_name[0:1]
        else:
            indexpath = str(len(crate_name))
        return os.path.join(basepath, indexpath, crate_name)

    @staticmethod
    def find_crate_in_index(crate_name, version_desired, reg_index_basepath):
        crate_info_found = {}
        index_filename = CrateDependencies.build_pathname_index(crate_name, reg_index_basepath)
        if os.path.exists(index_filename):
            with open(index_filename) as file:
                crate_string = file.read()
            version_list = crate_string.splitlines()
            # file in index contains lines with json in version order
            # we start with latest and to find hit early and tests showed that
            # cargo does same for semver version ranges
            version_list.reverse()
            for line in version_list:
                crate_version_dict = json.loads(line)
                version_index = crate_version_dict["vers"]
                # TODO: This does not work we have to take care of
                # * caret
                # * tilde
                # * wildcard
                # see https://doc.rust-lang.org/cargo/reference/specifying-dependencies.html
                # use bb.utils version comparisons
                compare_result = semver.compare(version_index, version_desired)
                if compare_result >= 0:
                    crate_info_found = crate_version_dict
                    break
        return crate_info_found


    def find_crate_dependencies_in_index(self, crate_name, crate_version, reg_index_basepath):
        dependency_found = False
        index_info = CrateDependencies.find_crate_in_index( crate_name,
                                                            crate_version, 
                                                            reg_index_basepath)
        if index_info != {}:
            dependency_found = True
            for depend in index_info["deps"]:
                print(depend)
                # Dependency entries in index do not pin version -> find matching
                depend_in_index = CrateDependencies.find_crate_in_index(depend["name"], depend["req"], reg_index_basepath)
                if depend_in_index != {}:
                    depend["version"] = depend_in_index["version"]


                 #   self.add_crate(dependency, "req", False)

        return dependency_found


# Some temp test tests
cratedep = CrateDependencies( "rand", 
                                "0.8.2", 
                                "/home/superandy/data/git-projects/rust/rand/Crates.lock",
                                "/home/superandy/data/git-projects/rust/crates.io-index")
cratedep.find_dependencies()
cratedep.print_crates()
exit()

cratedep = CrateDependencies( "spotifyd", 
                                "0.3.0", 
                                "/home/superandy/data/git-projects/rust/spotifyd/Cargo.lock",
                                "/home/superandy/data/git-projects/rust/crates.io-index")
cratedep.find_dependencies()
#cratedep.print_crates()

cratedep = CrateDependencies( "firefox", 
                                "68.9.0esr", 
                                "/home/superandy/tmp/oe-core-glibc/work/cortexa72-mortsgna-linux/firefox/68.9.0esr-r0/firefox-68.9.0/Cargo.lock",
                                "/home/superandy/data/git-projects/rust/crates.io-index")
cratedep.find_dependencies()
cratedep.print_crates()
