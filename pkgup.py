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
args = parser.parse_args()

if args.pkgrel:
    pkgrel = args.pkgrel
else:
    pkgrel = 1


def file_hasher(src_file_path):
    """Find SHA256 hash of the source file."""
    sha256 = hashlib.sha256()
    with open(src_file_path, "rb") as src_file:
        # The file may be large, so read it as blocks of 65536 bytes (64 KBs)
        for block in iter(lambda: src_file.read(65536), b""):
            sha256.update(block)
    return sha256.hexdigest()


def source_process():
    """Process the source link."""
    global gitname
    pkgname = re.search("pkgname=.*", pkgbuild_content,
                        flags=re.IGNORECASE).group(0).replace("pkgname=", "")
    gitname = re.search("_gitname=.*", pkgbuild_content,
                        flags=re.IGNORECASE).group(0)
    if gitname is None:
        print("_gitname not set, using pkgname instead.")
        gitname = pkgname
    else:
        gitname = gitname.replace("_gitname=", "")
    author = re.search("_author=.*", pkgbuild_content,
                       flags=re.IGNORECASE).group(0)
    if author is None:
        print("_author not set. Does not effect anything unless" +
              " $_author is used in source.")
    else:
        author = author.replace("_author=", "")
    source = re.search("source=.*", pkgbuild_content,
                       flags=re.IGNORECASE).group(0).replace("source=", "")
    tar_file_name = "{}-{}.tar.gz".format(gitname, args.pkgver)
    link_clean_list = {"$_author": author,
                       "$_gitname": gitname,
                       "$pkgver": args.pkgver,
                       "$pkgname": pkgname,
                       '("': '',
                       '")': '',
                       tar_file_name + "::": ''}
    for x, y in link_clean_list.items():
        source = source.replace(x, y)
    return source


def integrity_check(file_name):
    """Check the integrity of the source file and re-download if necessary."""
    check = subprocess.Popen(["gzip", "-t", file_name],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    check.wait()
    if check.returncode == 0:
        print("File seems okay. Proceed.")
    else:
        print('File is broken. Re-downloading.')
        os.remove(file_name)
        download_src(repeat=True)


def pkgbuild_update(pkgver, new_hash):
    """Update the PKGBUILD according to the changes."""
    global pkgbuild_content
    sha256sums = re.search('sha256sums=.*', pkgbuild_content,
                           flags=re.IGNORECASE).group(0)
    old_ver = re.search('pkgver=.*', pkgbuild_content,
                        flags=re.IGNORECASE).group(0)
    old_rel = re.search('pkgrel=.*', pkgbuild_content,
                        flags=re.IGNORECASE).group(0)
    update_list = {sha256sums: "sha256sums=('{}')".format(new_hash),
                   old_ver: "pkgver=" + pkgver,
                   old_rel: "pkgrel=" + str(pkgrel)}
    pkgbuildnew = pkgbuild_content
    for x, y in update_list.items():
        pkgbuildnew = pkgbuildnew.replace(x, y)
    with open('PKGBUILD', 'w') as pkgbuild:
        pkgbuild.write(pkgbuildnew)
    print(pkgbuildnew)
    print("PKGBUILD Updated.")


def srcinfo_update():
    """Update the .SRCINFO file."""
    srcinfo_gen = subprocess.Popen(["makepkg", "--printsrcinfo"],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
    srcinfo_gen.wait()
    srcinfo = srcinfo_gen.stdout.read().decode()
    with open('.SRCINFO', 'w') as srcinfo_file:
        srcinfo_file.write(srcinfo)
    print(".SRCINFO Updated.")


def download_src(repeat=False):
    """Download the source file and run integrity_check."""
    global gitname
    source = source_process()
    src_file_name = "{}-v{}.tar.gz".format(gitname, args.pkgver)
    if not repeat:
        print("Download source processed as: " + source)
        print("File name will be: " + src_file_name)
    if not os.path.exists(src_file_name):
        r = requests.get(source, stream=True)
        file_size = int(r.headers.get('content-length', 0))
        prog = tqdm(total=file_size, unit='iB', unit_scale=True)
        with open(src_file_name, 'wb') as src_file:
            for data in r.iter_content(chunk_size=1024):
                prog.update(len(data))
                src_file.write(data)
                src_file.flush()
        prog.close()
    integrity_check(src_file_name)
    return src_file_name


def main():
    """Read PKGBUILD and run other functions in order."""
    global gitname, pkgbuild_content
    with open('PKGBUILD', 'r') as pkgbuild:
        pkgbuild_content = pkgbuild.read()
    src_file_name = download_src()
    src_hash = file_hasher(src_file_name)
    print("SHA256 Sum found to be: " + src_hash)
    pkgbuild_update(args.pkgver, src_hash)
    srcinfo_update()


if __name__ == '__main__':
    main()
