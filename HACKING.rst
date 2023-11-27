Hacking on Soufi
================

Running tests
-------------

The test suite can be run via the `hatch` utility:


::

    hatch run ci

will run the Python 3 tests, the PEP8 tests, and code formatting checks. Test
coverage is also displayed and without 100% test coverage the tests will fail.

::

    hatch run py3 -- <test pattern>

will run a subset of tests matching <test pattern>.

::

    hatch run debug

runs all tests serially in debug mode allowing the use of debuggers like pdb.

::

   hatch run test soufi.tests.test_file.TestClass.test_name

runs a single test in debug mode.

::

    hatch run failing

runs only the tests that failed in the previous run.

Other handy hatch targets:

::

    hatch run ipython

gives you an ipython prompt in the virtualenv used by hatch.

::

    hatch run format

reformats the code using Black and sorts imports using isort.
Tests will not pass if there are errors, which you can check using

::

    hatch run check


Code structure
--------------

`soufi/finders` is a directory that holds all the various finder
plugins. These are constructed by the `FinderFactory` in
`soufi/finder.py`. Each finder must implement the two abstract base
classes `SourceFinder` and `DiscoveredSource`. The former will return
an instance of the latter when source is found, and the latter has
helpers to generate an archive of the found source.

There is also the command line client at `soufi/__init__.py` which
mainly serves as a real-world testing tool.


Future work
-----------
There is much that can be improved in most parts of this code::
 - auto-generate API documentation and publish at readthedocs
 - The finders are not 100% effective and can miss some sources.
   Particularly Alpine and CentOS.
 - Better documentation of the API to the finders and what exceptions
   get raised and when.


.. footer::
  Soufi is copyright (c) 2021 Cisco Systems, Inc. and its affiliates
  All rights reserved.
