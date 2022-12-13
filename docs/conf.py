# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
sys.path.insert(0, os.path.abspath('../vantage6'))
sys.path.insert(0, os.path.abspath('../vantage6-node'))
sys.path.insert(0, os.path.abspath('../vantage6-server'))
sys.path.insert(0, os.path.abspath('../vantage6-client'))
sys.path.insert(0, os.path.abspath('../vantage6-common'))


# -- Project information -----------------------------------------------------

project = 'vantage6'

copyright = ('2022 vantage6')
author = (
    'A. van Gestel, '
    'B. van Beusekom, '
    'D. Smits, '
    'F. Martin, '
    'J. van Soest, '
    'H. Alradhi, '
    'M. Sieswerda'
)

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.napoleon',
              'sphinx_autodoc_typehints', 'sphinx.ext.autosectionlabel',
              'sphinx.ext.intersphinx']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'alabaster'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

html_theme_options = {
    'logo': "logo-240x80.png",
    'logo_name': False,
    'github_user': 'vantage6',
    'github_repo': 'vantage6',
    'fixed_sidebar': True,
}


# The master toctree document.
master_doc = 'index'

add_module_names = False

pygments_style = None

numfig = True
