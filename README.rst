SOFI
====

SoFi (Source Finder) is a library that finds downloadable URLs for
source packages, given the binary package name and version.

Currently supported finders are:
 - Debian OS packages
 - Ubuntu OS packages
 - NPM packages
 - Python sdists

Future:
 - java
 - gem
 - Go


Quickstart
----------

Install Sofi with pip::

   pip install sofi

Using the command line:

.. code:: bash

    sofi python flask 2.0.0
    https://files.pythonhosted.org/packages/37/6d/61637b8981e76a9256fade8ce7677e86a6edcd6d4525f459a6b9edbd96a4/Flask-2.0.0.tar.gz

    sofi debian debian zlib1g 1:1.2.11.dfsg-1 -o zlib.tar.xz
    zlib_1.2.11.dfsg.orig.tar.gz: https://snapshot.debian.org/file/1b7f6963ccfb7262a6c9d88894d3a30ff2bf2e23
    zlib_1.2.11.dfsg-1.dsc: https://snapshot.debian.org/file/f2bea8c346668d301c0c7745f75cf560f2755649
    zlib_1.2.11.dfsg-1.debian.tar.xz: https://snapshot.debian.org/file/c3b2bac9b1927fde66b72d4f98e4063ce0b51f34

    ls -l zlib.tar.xz
    -rw-rw-r-- 1 juledwar juledwar 391740 May 20 15:20 zlib.tar.xz


Using the API:

.. code:: python

    import shutil
    import sofi

    finder = sofi.finder.factory(
        'python', 'flask', '2.0.0', sofi.finder.SourceType.python
    )
    source = finder.find()
    print(source)

    finder = sofi.finder.factory(
        'debian', 'zlib1g', '1:1.2.11.dfsg-1', sofi.finder.SourceType.os
    )
    source = finder.find()
    print(source)
    with source.make_archive() as archive, open('zlib.tar.xz') as local:
        shutil.filecopyobj(archive, local)