import os
import pkgutil
import subprocess

import pkg_resources
from setuptools import setup, find_packages

curr_path = os.path.dirname(__file__)
CLI_PATH = os.path.join(curr_path, "libinsitu", "cli")

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(curr_path, fname))\
        .read().strip()

def run(args) :
    return subprocess.run(args, stdout=subprocess.PIPE).\
        stdout.decode('utf-8').splitlines()

# Get current git branch
branches = run(["git", "branch"])
curr_branch = next(line for line in branches if "*" in line)
curr_branch = curr_branch.replace(" ", "").replace("*", "")


name = "libinsitu"

if curr_branch not in  ["master", "main"] :

    if curr_branch != "dev" :
        raise Exception("Only main, master and dev branch supported")

    name += "_dev"


extra_urls= []

with open("requirements.txt", "r") as f :

    def extract_extra_index(strs) :
        for line in strs :
            if line.startswith("--extra-index-url") :
                _, url, rest = line.split(" ")
                extra_urls.append(url)
                yield rest
            else:
                yield line

    requirements = [
            #str(requirement).replace("==", ">=")
            str(requirement)
            for requirement
            in pkg_resources.parse_requirements(extract_extra_index(f))]



# List all cli modules
entry_points = []
for importer, modname, ispkg in pkgutil.iter_modules([CLI_PATH]):
    entry_points.append('ins-%s = libinsitu.cli.%s:main' % (modname, modname))
print(f" Cli path {CLI_PATH} entry points : {entry_points}")

packages = find_packages()

print("Packages : %s"%  str(packages))
print("Extra URLs : %s" % extra_urls)

setup(
    name = name,
    python_requires='>3.7',
    author = "OIE - Mines ParisTech",
    author_email = "raphael.jolivet@mines-paristech.fr",
    description = ("This library provides tools to transform solar irradiation data from various networks to uniform NetCDF files. "
                   "It also provides tools to request and manipulate those NetCDF files"),
    license = "BSD",
    keywords = "in-situ, solar, pv, irradiation, NetCDF, FAIR, meta-data",
    url = "http://libinsitu.org/",
    packages=packages,
    long_description=read('README.md'),
    long_description_content_type='text/markdown',
    dependency_links=extra_urls,
    include_package_data=True,
    classifiers=[],
    setup_requires=['setuptools_scm'],
    install_requires=requirements,
    use_scm_version={
        'write_to': 'build/lib/libinsitu/_version.py',
        'write_to_template': '__version__ = "{version}"',
    },
    entry_points={'console_scripts': entry_points}
)


