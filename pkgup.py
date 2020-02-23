#!/usr/bin/python
"""
pkgup is an easy way to maintain AUR packages.

pkgup makes maintaining easy when only the package version or only the release
number needs to be updated. It's a CLI script to be run in the same directory
as the PKGBUILD and so, is not intended to be imported as a module. Also note
that changing the release number makes no real changes.
"""

import argparse
import re
import hashlib
from tqdm import tqdm
import requests
import subprocess
import os

parser = argparse.ArgumentParser(description="Update PKGBUILDs easily.")
parser.add_argument("pkgver", help="Version to update to")
parser.add_argument("-r", "--pkgrel", type=int,
                    help="Release number to update to")
ARGS = parser.parse_args()

if ARGS.pkgrel:
    PKG_REL = ARGS.pkgrel
else:
    PKG_REL = 1


class pkgup():

    gitname = None
    pkgbuild_content = None

    def file_hasher(self, src_file_path):
        """Find SHA256 hash of the source file."""
        sha256 = hashlib.sha256()
        with open(src_file_path, "rb") as src_file:
            # The file may be large, read it as blocks of 65536 bytes (64 KBs).
            for block in iter(lambda: src_file.read(65536), b""):
                sha256.update(block)
        return sha256.hexdigest()

    def source_process(self):
        """Process the source link."""
        pkgname = re.search("pkgname=.*",
                            self.pkgbuild_content,
                            flags=re.IGNORECASE
                            ).group(0).replace("pkgname=", "")
        self.gitname = re.search("_gitname=.*", self.pkgbuild_content,
                                 flags=re.IGNORECASE).group(0)
        if self.gitname is None:
            print("_gitname not set, using pkgname instead.")
            self.gitname = pkgname
        else:
            self.gitname = self.gitname.replace("_gitname=", "")
        author = re.search("_author=.*", self.pkgbuild_content,
                           flags=re.IGNORECASE).group(0)
        if author is None:
            print("_author not set. Does not effect anything unless" +
                  " $_author is used in source.")
        else:
            author = author.replace("_author=", "")
        source = re.search("source=.*", self.pkgbuild_content,
                           flags=re.IGNORECASE).group(0).replace("source=", "")
        tar_file_name = "{}-{}.tar.gz".format(self.gitname, ARGS.pkgver)
        link_clean_list = {"$_author": author,
                           "$_gitname": self.gitname,
                           "$pkgver": ARGS.pkgver,
                           "$pkgname": pkgname,
                           '("': '',
                           '")': '',
                           tar_file_name + "::": ''}
        for old_val, new_val in link_clean_list.items():
            source = source.replace(old_val, new_val)
        return source

    def integrity_check(self, file_name):
        """Check the integrity of the source file and re-download if needed."""
        check = subprocess.Popen(["gzip", "-t", file_name],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        check.wait()
        if check.returncode == 0:
            print("File seems okay. Proceed.")
        else:
            print('File is broken. Re-downloading.')
            os.remove(file_name)
            self.download_src(repeat=True)

    def pkgbuild_update(self, pkgver, new_hash):
        """Update the PKGBUILD according to the changes."""
        sha256sums = re.search('sha256sums=.*', self.pkgbuild_content,
                               flags=re.IGNORECASE).group(0)
        old_ver = re.search('pkgver=.*', self.pkgbuild_content,
                            flags=re.IGNORECASE).group(0)
        old_rel = re.search('pkgrel=.*', self.pkgbuild_content,
                            flags=re.IGNORECASE).group(0)
        update_list = {sha256sums: f"sha256sums=('{new_hash}')",
                       old_ver: f"pkgver={pkgver}",
                       old_rel: f"pkgrel={str(PKG_REL)}"}
        pkgbuild_new = self.pkgbuild_content
        for old_val, new_val in update_list.items():
            pkgbuild_new = pkgbuild_new.replace(old_val, new_val)
        with open('PKGBUILD', 'w') as pkgbuild:
            pkgbuild.write(pkgbuild_new)
        print(pkgbuild_new)
        print("PKGBUILD Updated.")

    def srcinfo_update(self):
        """Update the .SRCINFO file."""
        srcinfo_gen = subprocess.Popen(["makepkg", "--printsrcinfo"],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
        srcinfo_gen.wait()
        srcinfo = srcinfo_gen.stdout.read().decode()
        with open('.SRCINFO', 'w') as srcinfo_file:
            srcinfo_file.write(srcinfo)
        print(".SRCINFO Updated.")

    def download_src(self, repeat=False):
        """Download the source file and run integrity_check."""
        source = self.source_process()
        src_file_name = "{}-v{}.tar.gz".format(self.gitname, ARGS.pkgver)
        if not repeat:
            print("Download source processed as: " + source)
            print("File name will be: " + src_file_name)
        if not os.path.exists(src_file_name):
            request = requests.get(source, stream=True)
            file_size = int(request.headers.get('content-length', 0))
            prog = tqdm(total=file_size, unit='iB', unit_scale=True)
            with open(src_file_name, 'wb') as src_file:
                for data in request.iter_content(chunk_size=1024):
                    prog.update(len(data))
                    src_file.write(data)
                    src_file.flush()
            prog.close()
        self.integrity_check(src_file_name)
        return src_file_name

    def main(self):
        """Read PKGBUILD and run other functions in order."""
        with open('PKGBUILD', 'r') as pkgbuild:
            self.pkgbuild_content = pkgbuild.read()
        src_file_name = self.download_src()
        src_hash = self.file_hasher(src_file_name)
        print("SHA256 Sum found to be: " + src_hash)
        self.pkgbuild_update(ARGS.pkgver, src_hash)
        self.srcinfo_update()


if __name__ == '__main__':
    pkgup().main()
