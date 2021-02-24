#!/usr/bin/env python3

"Setuptools params"

from setuptools import setup, find_packages

VERSION = '0.2'

modname = distname = 'p4utils'

def readme():

    with open('README.md','r') as f:
        return f.read()

setup(
    name=distname,
    version=VERSION,
    description='P4 language and bmv2 model utilities',
    author='Edgar Costa Molero',
    author_email='cedgar@ethz.ch',
    packages=find_packages(),
    long_description=readme(),
    entry_points={'console_scripts': ['p4run = p4utils.p4run:main']},
    include_package_data = True,
    classifiers=[
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python 3",
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Topic :: System :: Networking",
        ],
    keywords='networking p4 mininet',
    license='GPLv2',
    install_requires=[
        'setuptools',
        'networkx',
        'ipaddress',
        'scapy',
        'psutil'
    ],
    extras_require={}
    #tests_require=['pytest'],
    #setup_requires=['pytest-runner']
)
