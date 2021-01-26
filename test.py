#!/usr/bin/env python3

#
# Playground that mimics cargo fetch to prepare Bitbake crate fetcher
#
# SPDX-License-Identifier: GPL-2.0-only
#

import os
import glob
import copy
import json

# As long as python-core does not contain toml or pytoml (under discussion)
# use our stolen copy from https://github.com/uiri/toml
import toml
#import pytoml as toml

from bb.utils import is_semver, vercmp_string_op

class CrateDependencies:
    def __init__(self, reg_index_basepath, rust_lib_root, rust_arch):
        self.reg_index_basepath = reg_index_basepath
        self.rustlib_path = os.path.join(rust_lib_root, "/usr/lib/rustlib", rust_arch, 'lib')

    def find_dependencies(self, crate_name, crate_version, crate_lockfile):
        self.crate_name = crate_name
        self.crate_version = crate_version
        self.crate_lockfile = crate_lockfile
        self.depend_crates_required = {}
        self.depend_crates_ignored = {} # either shipped in source or by rust
        self.file_parsed_currently = ""
        # Prefer Cargo.lock if shipped
        if os.path.exists(self.crate_lockfile):
            self.file_parsed_currently = self.crate_lockfile
            print("Parsing %s for dependencies." % self.crate_lockfile)
            toml_dict = self.toml_to_dict(self.crate_lockfile)
            if "package" in toml_dict:
                for package_dict in toml_dict["package"]:
                    self.add_crate(package_dict, True)
            else:
                # TODO error handling
                print("%s is invalid - no 'package' header found" % self.crate_lockfile)
            return
        # Try registry index
        else:
            if self.find_crate_dependencies_in_index(self.crate_name, 
                                                     self.crate_version, 
                                                     self.reg_index_basepath):
                print("Dependencies of %s-%s used from index." % (self.crate_name, self.crate_version))
            else:
                print("TODO call cargo-native")

    def print_crates(self):
        print("\nDepend crates:")
        for key in sorted(self.depend_crates_required):
            print("Name:", key, "Versions:", sorted(self.depend_crates_required[key]))
        print("Crates:", len(self.depend_crates_required))
        print("\nUnhandled depends:")
        for key in sorted(self.depend_crates_ignored):
            print("Name:", key, "Versions:", sorted(self.depend_crates_ignored[key]))
        print("Crates:", len(self.depend_crates_ignored))

    def add_crate(self, crate_dict, source_info_required):
        # Note on source_info_required:
        # * In Cargo.lock dependency entries without 'source' are in-tree must
        #   be ignored
        # * In files from registry-index there is no source entry
        if "name" in crate_dict and "version" in crate_dict:
            name = crate_dict["name"]
            version = crate_dict["version"]
            if not source_info_required or "source" in crate_dict:
                dict_to_add = self.depend_crates_required
            else:
                dict_to_add = self.depend_crates_ignored
            if not name in dict_to_add:
                dict_to_add[name] = []
            if not version in dict_to_add[name]:
                dict_to_add[name].append(version)
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
    def version_acceptable(version, version_rules):
        # quick out (e.g Cargo.lock versions are expicit / no requirements)
        rule_list_in = version_rules.split(',')
        comparison_chars = ['>', '<', '=', '!']
        requirement_chars = ['^', '~', '*'] + comparison_chars
        rules_have_requirements = any(req_char in version_rules for req_char in requirement_chars)
        if len(rule_list_in) == 1 and not rules_have_requirements:
            return version == version_rules

        def calcversion_ranges(version_split, increment_pos):
            version_split_end = version_split.copy()
            version_split_end[increment_pos] = str(int(version_split_end[increment_pos] or '0')+1)
            for subver in range(increment_pos+1, len(version_split_end)):
                version_split_end[subver] = '0'
            # stuff with trailing '0' / make string rule
            version_split += ['0'] * (3 - len(version_split))
            version_split_end += ['0'] * (3 - len(version_split_end))
            version_start = '>=' + separator.join(version_split)
            version_end = '<' + separator.join(version_split_end)
            return version_start,version_end

        # Check if version has requirements. We process
        # * caret
        # * tilde
        # * wildcard
        # * multiple rules
        # see https://doc.rust-lang.org/cargo/reference/specifying-dependencies.html
        rule_list_out = []
        for rule in rule_list_in:
            separator = '.'
            version_split = rule.split(separator)
            version_start = ""
            version_end = ""
            # We do support carot OR tilde on first postion only
            # caret
            if version_split[0].startswith('^'):
                version_split[0] = version_split[0].replace('^', '')
                increment_pos = 0
                for subver in range(0, len(version_split)):
                    # caret is handled dfferently on major version 0
                    if version_split[subver] != '0':
                        increment_pos = subver
                        break
                    elif subver+1 < len(version_split):
                        increment_pos = subver+1
                version_start, version_end = calcversion_ranges(version_split, increment_pos)
            # tilde
            elif version_split[0].startswith('~'):
                version_split[0] = version_split[0].replace('~', '')
                increment_pos = 1
                if len(version_split) == 1:
                    increment_pos = 0
                version_start, version_end = calcversion_ranges(version_split, increment_pos)
            # wildcard
            elif rule.endswith('*'):
                if version_split[0] == '*':
                    version_start = '>=0.0.0' # This should not be found in index
                else:
                    increment_pos = 0
                    if len(version_split) > 2 and version_split[2] == '*':
                        increment_pos = 1
                    # replace * will go calcversion_ranges does not replace all
                    for subver in range(0, len(version_split)):
                        if version_split[subver] == '*':
                            version_split[subver] = '0'
                    version_start, version_end = calcversion_ranges(version_split, increment_pos)
            # comparison
            else:
                version_start = rule
            if version_start != "":
                rule_list_out.append(version_start)
            if version_end != "":
                rule_list_out.append(version_end)
            #print(rule, '->', version_start, version_end)

        # here rule_list_out is set with comparison requirement only
        all_rules_pass = True
        for rule in rule_list_out:
            rule = ''.join(rule.split())
            # extract operator
            for pos in range(0, len(rule)):
                if not rule[pos] in comparison_chars:
                    break
            cmp_operator = rule[0:pos]
            cmp_version = rule[pos:]
            if not vercmp_string_op(version, cmp_version, cmp_operator):
                all_rules_pass = False

        return all_rules_pass

    @staticmethod
    def find_crate_in_index(crate_name, 
                            search_str, # version rules or checksum
                            reg_index_basepath, 
                            search_for_checksum = False):
        crate_info_found = {}
        index_filename = CrateDependencies.build_pathname_index(crate_name, reg_index_basepath)
        if os.path.exists(index_filename):
            with open(index_filename) as file:
                crate_string = file.read()
            version_list = crate_string.splitlines()
            # file in index contains lines with json in version order
            # we start with latest and to find hit early and tests showed that
            # cargo does same for version ranges
            version_list.reverse()
            for line in version_list:
                crate_version_dict = json.loads(line)
                # ignore yanked entries
                if 'yanked' in crate_version_dict and crate_version_dict['yanked']:
                    continue
                if search_for_checksum:
                    if crate_version_dict["cksum"].startswith(search_str):
                        crate_info_found = crate_version_dict
                else:
                    version_index = crate_version_dict["vers"]
                    if CrateDependencies.version_acceptable(version_index, search_str):
                        crate_info_found = crate_version_dict
                if crate_info_found != {}:
                    break
        return crate_info_found

    def depend_processed_before(self, name, version):
        return \
            (name in self.depend_crates_required and \
            version in self.depend_crates_required[name]) or \
            (name in self.depend_crates_ignored and \
            version in self.depend_crates_ignored[name])

    def find_crate_dependencies_in_index(self, crate_name, crate_version, reg_index_basepath):
        index_info = CrateDependencies.find_crate_in_index( crate_name,
                                                            crate_version, 
                                                            reg_index_basepath,
                                                            False)
        if index_info != {}:
            for depend in index_info["deps"]:
                name = depend["name"]
                # Check if it is a library installed by rust
                if os.path.exists(self.rustlib_path):
                    # Try to find a matching version of rustlib
                    # 1. Is there a library matching crate's name?
                    libname = 'lib' + name.replace('-', '_')
                    globstr = os.path.join(self.rustlib_path, libname + '-*.rlib')
                    rust_lib_in_index = {}
                    for lib in glob.glob(globstr):
                        # TODO: Check by checksum if added before
                        # 2. Find crate in index
                        chksum = lib.replace(self.rustlib_path, '') \
                            .replace(libname, '') \
                            .replace('.rlib', '') \
                            .replace('-', '') \
                            .replace('/', '')
                        rust_lib_in_index = self.find_crate_in_index(
                            name, 
                            chksum,
                            self.reg_index_basepath, 
                            True)
                        if rust_lib_in_index != {}:
                            # 3. Does rustlib match requirements?
                            if not CrateDependencies.version_acceptable(rust_lib_in_index["vers"], depend["req"]):
                                rust_lib_in_index = {}
                            break
                    if rust_lib_in_index != {}:
                        crate_to_add = {}
                        crate_to_add["name"] = name
                        crate_to_add["version"] = rust_lib_in_index["vers"]
                        crate_to_add["cksum"] = rust_lib_in_index["cksum"]
                        # a bit of a hack: By not supplying source and
                        # supplying source_info_required we force rustlib
                        # added to ignored list
                        self.add_crate(crate_to_add, True)
                        continue

                # Dependency entries in index have version requirements -> find matching
                depend_in_index = CrateDependencies.find_crate_in_index(
                    name, depend["req"], reg_index_basepath, False)
                if depend_in_index != {}:
                    version = depend_in_index["vers"]
                    if self.depend_processed_before(name, version):
                        continue
                    crate_to_add = {}
                    crate_to_add["name"] = name
                    crate_to_add["version"] = version
                    crate_to_add["cksum"] = depend_in_index["cksum"]
                    self.add_crate(crate_to_add, False)
                    # start recursion
                    self.find_crate_dependencies_in_index(name, version, reg_index_basepath)
        return index_info != {}




# # Some temp tests
# CrateDependencies.version_acceptable('0.0.0', '^1.2.3')
# CrateDependencies.version_acceptable('0.0.0', '^1.2')
# CrateDependencies.version_acceptable('0.0.0', '^1')
# CrateDependencies.version_acceptable('0.0.0', '^0.2.3')
# CrateDependencies.version_acceptable('0.0.0', '^0.2')
# CrateDependencies.version_acceptable('0.0.0', '^0.0.3')
# CrateDependencies.version_acceptable('0.0.0', '^0.0')
# CrateDependencies.version_acceptable('0.0.0', '^0')

# CrateDependencies.version_acceptable('0.0.0', '~1.2.3')
# CrateDependencies.version_acceptable('0.0.0', '~1.2')
# CrateDependencies.version_acceptable('0.0.0', '~1')

# CrateDependencies.version_acceptable('0.0.0', '*')
# CrateDependencies.version_acceptable('0.0.0', '1.*')
# CrateDependencies.version_acceptable('0.0.0', '1.2.*')
# exit()

cratedep = CrateDependencies( "/home/superandy/data/git-projects/rust/crates.io-index", "", "x86_64-unknown-linux-gnu" )

cratedep.find_dependencies( "rand", 
                            "0.8.2", 
                            "/home/superandy/data/git-projects/rust/rand/Cargo.lock")
cratedep.print_crates()

exit()

cratedep.find_dependencies( "spotifyd", 
                            "0.3.0", 
                            "/home/superandy/data/git-projects/rust/spotifyd/Cargo.lock")
cratedep.print_crates()

cratedep.find_dependencies( "firefox", 
                            "68.9.0esr", 
                            "/home/superandy/tmp/oe-core-glibc/work/cortexa72-mortsgna-linux/firefox/68.9.0esr-r0/firefox-68.9.0/Cargo.lock")
cratedep.print_crates()
