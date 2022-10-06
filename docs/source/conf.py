# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import sys, os


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'libinsitu'
copyright = '2022, Centre O.I.E - Raphaël Jolivet, Yves Marie Saint-Drenan'
author = 'Centre O.I.E - Raphaël Jolivet, Yves Marie Saint-Drenan'
release = '1.2'

sys.path.append(os.path.join(os.path.dirname(__file__), '_deps'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'myst_parser',
    'sphinxarg.ext',
    'gitrep2']

# These folders are copied to the documentation's HTML output
html_static_path = ['_static']

# These paths are either relative to html_static_path
# or fully qualified paths (eg. https://...)
html_css_files = [
    'css/custom.css',
]

templates_path = ['_templates']
exclude_patterns = []
source_suffix = ['.rst', '.md']

gitref_remote_url = "https://git.sophia.mines-paristech.fr/oie/libinsitu.git"
gitref_branch = "main"


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ['_static']



