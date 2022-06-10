import setuptools

setuptools_version = tuple(map(int, setuptools.__version__.split(".", 2)[:2]))
if setuptools_version < (34, 4):
    raise RuntimeError("setuptools 34.4 or newer is required, detected ",
                       setuptools_version)

if __name__ == "__main__":
    setuptools.setup(
        # This duplicates the equivalent in pyproject.toml so that setup.py
        # --version won't report a version of 0.0.0 in editable installs.
        # setup.py invocations will NOT install build requirements from
        # pyproject.toml. Unfortunately this also causes
        # SetuptoolsDeprecationWarnings to be emitted, complaining about
        # PEP517.
        setup_requires=["setuptools>=60.5.0", "wheel", "setuptools-scm>=6.4.2"]
    )
