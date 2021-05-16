#!/usr/bin/python
"""
pkgup is an easy way to maintain AUR packages.

pkgup makes maintaining easy when only the package version or only the release
number needs to be updated. It's a CLI script to be run in the same directory
as the PKGBUILD and so, is not intended to be imported as a module. Also note
that changing the release number makes no real changes.
"""

import argparse
import hashlib
import os
import re
import subprocess

from tqdm import tqdm
import requests

PARSER = argparse.ArgumentParser(description="Update PKGBUILDs easily.")
PARSER.add_argument("pkgver", help="Version to update to")
PARSER.add_argument("-r", "--pkgrel", type=int, help="Release number to update to")
PARSER.add_argument(
    "-s", "--skip-checks", action="store_true", help="Skip gzip integrity checks"
)
PARSER.add_argument("-f", "--format", type=str, help="Custom file format")
ARGS = PARSER.parse_args()


class PkgUp:
    """Perform updation operations on the PKGBUILD."""

    gitname = None
    pkgbuild_content = None

    @staticmethod
    def file_hasher(src_file_path):
        """Find SHA256 hash of the source file."""
        sha256 = hashlib.sha256()
        with open(src_file_path, "rb") as src_file:
            # The file may be large, read it as blocks of 65536 bytes (64 KBs).
            for block in iter(lambda: src_file.read(65536), b""):
                # Update the sha256 block-by-block.
                sha256.update(block)
        return sha256.hexdigest()

    def source_process(self):
        """Process the source link."""
        # Get the package name.
        pkgname = (
            re.search("pkgname=.*", self.pkgbuild_content, flags=re.IGNORECASE)
            .group(0)
            .replace("pkgname=", "")
        )
        # Get the git repository name.
        self.gitname = re.search(
            "_gitname=.*", self.pkgbuild_content, flags=re.IGNORECASE
        )
        if self.gitname is None:
            print("_gitname not set, using pkgname instead.")
            self.gitname = pkgname
        else:
            self.gitname = self.gitname.group(0).replace("_gitname=", "")
        # Get the author name.
        author = re.search("_author=.*", self.pkgbuild_content, flags=re.IGNORECASE)
        if author is None:
            print(
                "_author not set. Does not effect anything unless"
                + " $_author is used in source."
            )
            author = ""
        else:
            author = author.group(0).replace("_author=", "")
        # Get the source link.
        source = (
            re.search("source=.*", self.pkgbuild_content, flags=re.IGNORECASE)
            .group(0)
            .replace("source=", "")
        )
        # Clean the source link.
        if ARGS.format:
            src_file_name = f"{self.gitname}-v{ARGS.pkgver}.{ARGS.format}"
        else:
            src_file_name = f"{self.gitname}-v{ARGS.pkgver}.tar.gz"
        link_clean_list = {
            "$_author": author,
            "$_gitname": self.gitname,
            "$pkgver": ARGS.pkgver,
            "$pkgname": pkgname,
            '("': "",
            '")': "",
            src_file_name + "::": "",
        }
        for old_val, new_val in link_clean_list.items():
            source = source.replace(old_val, new_val)
        return source.strip("()").strip()

    def integrity_check(self, file_name):
        """Check the integrity of the source file and re-download if needed."""
        # Use gzip to check basic integrity of the downloaded file.
        check = subprocess.Popen(
            ["gzip", "-t", file_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        check.wait()  # Wait for process completion.
        # Check the return code of the program to know if the file is broken.
        if check.returncode == 0:
            print("File seems okay. Proceed.")
        else:
            print("File is broken. Re-downloading.")
            os.remove(file_name)
            self.download_src(repeat=True)

    def pkgbuild_update(self, pkgver, new_hash):
        """Update the PKGBUILD according to the changes."""
        # Get the old sha256sums.
        sha256sums = re.search(
            "sha256sums=.*", self.pkgbuild_content, flags=re.IGNORECASE
        ).group(0)
        # Get the old version number.
        old_ver = re.search(
            "pkgver=.*", self.pkgbuild_content, flags=re.IGNORECASE
        ).group(0)
        # Get the old release number.
        old_rel = re.search(
            "pkgrel=.*", self.pkgbuild_content, flags=re.IGNORECASE
        ).group(0)
        # Update the PKGBUILD with new values.
        update_list = {
            sha256sums: f"sha256sums=('{new_hash}')",
            old_ver: f"pkgver={pkgver}",
            old_rel: f"pkgrel={str(ARGS.pkgrel or 1)}",
        }
        pkgbuild_new = self.pkgbuild_content or ''
        for old_val, new_val in update_list.items():
            pkgbuild_new = pkgbuild_new.replace(old_val, new_val)
        with open("PKGBUILD", "w") as pkgbuild:
            pkgbuild.write(pkgbuild_new)
        print("PKGBUILD Updated.")

    @staticmethod
    def srcinfo_update():
        """Update the .SRCINFO file."""
        # Use makepkg to generate the .SRCINFO output.
        srcinfo_gen = subprocess.Popen(
            ["makepkg", "--printsrcinfo"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        srcinfo_gen.wait()  # Wait for process completion.
        # Save output to .SRCINFO file.
        srcinfo = srcinfo_gen.stdout.read().decode()
        with open(".SRCINFO", "w") as srcinfo_file:
            srcinfo_file.write(srcinfo)
        print(".SRCINFO Updated.")

    def download_src(self, repeat=False):
        """Download the source file and run integrity_check."""
        source = self.source_process()  # Get source link.

        # Get downloaded source file name.
        if ARGS.format:
            src_file_name = f"{self.gitname}-v{ARGS.pkgver}.{ARGS.format}"
        else:
            src_file_name = f"{self.gitname}-v{ARGS.pkgver}.tar.gz"

        # Check if the file is being re-downloaded.
        if not repeat:
            # Print this only once.
            print("Download source processed as: " + source)
            print("File name will be: " + src_file_name)

        # Check if file already exists.
        if not os.path.exists(src_file_name):
            # Use requests to get the file and tqdm to update progress.
            request = requests.get(source, stream=True)
            file_size = int(request.headers.get("content-length", 0))
            prog = tqdm(total=file_size, unit="iB", unit_scale=True)
            with open(src_file_name, "wb") as src_file:
                for data in request.iter_content(chunk_size=1024):
                    prog.update(len(data))
                    src_file.write(data)
                    src_file.flush()
            prog.close()
        if src_file_name.endswith("gz") and not ARGS.skip_checks:
            self.integrity_check(src_file_name)  # Check file integrity.
        return src_file_name  # Return the file name.

    def main(self):
        """Read PKGBUILD and run other functions in order."""
        with open("PKGBUILD", "r") as pkgbuild:
            self.pkgbuild_content = pkgbuild.read()

        # Donwload the source file and get its file name.
        src_file_name = self.download_src()

        # Get the SHA256 sum of the source file.
        src_hash = self.file_hasher(src_file_name)
        print("SHA256 Sum found to be: " + src_hash)

        # Update the PKGBUILD with the new values.
        self.pkgbuild_update(ARGS.pkgver, src_hash)
        self.srcinfo_update()


if __name__ == "__main__":
    PkgUp().main()
