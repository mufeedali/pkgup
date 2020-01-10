# pkgup
A python script for easily updating PKGBUILDs. Made specifically for my packages. Can work for others if PKGBUILD is written accordingly. But it's only suitable for smaller packages with good build systems.

### What does it do?
 - Increases the pkgver and pkgrel to desired values.
 - Downloads the source as '.tar.gz'
 - Verifies basic integrity (`gzip -t`) and re-downloads if necessary.
 - Generates SHA256 checksum of source file.
 - Updates PKGBUILD accordingly.
 - Updates .SRCINFO accordingly. (`makepkg --printsrcinfo`)

### Dependencies
 - `python-tqdm`
 - `python-requests`
 - `gzip`
 - `makepkg` (part of `pacman`, used only for generating `.SRCINFO`)

### What is needed in the PKGBUILD for upgradablity?
 - It only works with '.tar.gz' source files.
 - Your `source` link should use `$pkgver` for downloading the correct version. For example, it can be like:  
 https://gitlab.com/valos/Komikku/-/archive/v$pkgver/Komikku-v$pkgver.tar.gz

#### Preferred format
The preferred format for `source` is as follows. For projects hosted on GitLab:
```
source=('https://www.gitlab.com/$_author/$_gitname/-/archive/v$pkgver/$_gitname-v$pkgver.tar.gz')
```
For projects hosted on GitHub:
```
source=('https://www.github.com/$_author/$_gitname/releases/archive/v$pkgver.tar.gz')
```
`_author` and `$_gitname` are not absolutely necessary, but recommended.