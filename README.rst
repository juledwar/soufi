SOUFI
=====

Soufi (Source Finder) is a library that finds downloadable URLs for
source packages, given the binary package name and version. It will also
create a compressed archive of multiple downloadable files, or save
any existing downloadable archive.

Currently supported finders are:
 - Debian OS packages
 - Ubuntu OS packages
 - CentOS packages
 - Alpine packages
 - NPM packages
 - Python sdists
 - Golang modules
 - Java JARs

If you want to download Alpine packages, you must have `git` installed.


Requirements
------------
Soufi is currently tested on Python versions 3.7, 3.8 and 3.9. It is
known not to work on 3.6.


Quickstart
----------

Install Soufi with pip::

   pip install soufi

Using the command line:

.. code:: bash

    soufi python flask 2.0.0
    https://files.pythonhosted.org/packages/37/6d/61637b8981e76a9256fade8ce7677e86a6edcd6d4525f459a6b9edbd96a4/Flask-2.0.0.tar.gz

    soufi debian zlib1g 1:1.2.11.dfsg-1 -o zlib.tar.xz
    zlib_1.2.11.dfsg.orig.tar.gz: https://snapshot.debian.org/file/1b7f6963ccfb7262a6c9d88894d3a30ff2bf2e23
    zlib_1.2.11.dfsg-1.dsc: https://snapshot.debian.org/file/f2bea8c346668d301c0c7745f75cf560f2755649
    zlib_1.2.11.dfsg-1.debian.tar.xz: https://snapshot.debian.org/file/c3b2bac9b1927fde66b72d4f98e4063ce0b51f34

    ls -l zlib.tar.xz
    -rw-rw-r-- 1 juledwar juledwar 391740 May 20 15:20 zlib.tar.xz


Using the API:

.. code:: python

    import shutil
    import soufi

    finder = soufi.finder.factory(
        'python', 'flask', '2.0.0', soufi.finder.SourceType.python
    )
    source = finder.find()
    print(source)

    finder = soufi.finder.factory(
        'debian', 'zlib1g', '1:1.2.11.dfsg-1', soufi.finder.SourceType.os
    )
    source = finder.find()
    print(source)
    with source.make_archive() as archive, open('zlib.tar.xz', 'wb') as local:
        shutil.filecopyobj(archive, local)


Copyright
---------

Soufi is copyright (c) 2021 Cisco Systems, Inc. and its affiliates
All rights reserved.
