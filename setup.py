#!/usr/bin/env python
import os
from setuptools import find_packages
from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name='deuspy',
    version='0.0',
    author='Amirouche Boubekki',
    author_email='amirouche@hypermove.net',
    url='https://github.com/amirouche/deuspy',
    description='Database For Fun Prototyping',
    long_description=read('README.rst'),
    packages=find_packages(),
    zip_safe=False,
    license='Apache',
    classifiers=[
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Topic :: Software Development'
    ],
)
