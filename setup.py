import os
from setuptools import setup, find_packages

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()
    
setup(
    name = "fogpy",
    version = "0.1.0",
    packages = find_packages(),
    description = "Python API lib for FogBugz",
    author = "Ecometrica",
    author_email = "info@ecometrica.ca",
    maintainer = "Éric St-Jean",
    maintainer_email = "eric@ecometrica.ca",
    url = "http://github.com/ecometrica/fogpy/",
    keywords = ["fogbugz", "api"],
    classifiers = [
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.6",
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: BSD License",
        "Operating System :: POSIX",
        "Topic :: Software Development",
        ],
    long_description = read('README.rst'),
)
