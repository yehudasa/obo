#!/usr/bin/python
from setuptools import setup, find_packages

setup(
    name='obo',
    version='0.0.1',
    packages=find_packages(),

    author='Yehuda Sadeh',
    author_email='yehuda@redhat.com',
    description='S3 control tool',
    license='MIT',
    keywords='s3 client',

    install_requires=[
        'boto >= 2.6.0',
        'PyYAML',
        'bunch >=1.0.0',
        'gevent ==0.13.6',
        'isodate >=0.4.4',
        ],

    entry_points={
        'console_scripts': [
            'obo = obo.obo:main',
            ],
        },

    )
