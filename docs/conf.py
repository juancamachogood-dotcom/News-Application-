import os
import sys
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["DJANGO_SETTINGS_MODULE"] = "news_project.settings"
os.environ["DB_ENGINE"] = "sqlite"

django.setup()

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project metadata -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'News Application'
copyright = '2026, Juan Camacho'
author = 'Juan Camacho'

version = '1.0'
release = '1.0'

# -- Sphinx extensions and build setting --------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
]

templates_path = []
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- HTML appearance -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = []
