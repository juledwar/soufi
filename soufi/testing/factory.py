# Copyright (c) 2021 Cisco Systems, Inc. and its affiliates
# All rights reserved.

"""Factory functions and classes for tests."""

import hashlib
import random
import string
from datetime import datetime, timezone
from itertools import count, islice, repeat
from unittest.mock import sentinel


class Factory:
    """Class that defines helpers that make things for you."""

    randint = random.randint
    random_choice = random.choice
    random_sample = random.sample
    random_ascii = map(random_choice, repeat(string.ascii_letters))
    random_letters = map(
        random_choice, repeat(string.ascii_letters + string.digits)
    )
    random_sentences = map(random_choice, repeat(string.printable))
    random_whitespace = map(random_choice, repeat(string.whitespace))

    # Marker to instruct factory methods to create a random object from
    # parameters.
    RANDOM = sentinel.RANDOM

    def __init__(self):
        """Initialize a monotonic ID generator.

        For use when making database items.  This will allow for every
        factory-created item in the test DB to have a globally-unique ID
        value, so that comparisons between objects won't have any
        unintentional overlap, but sorting and what-have-you will still
        behave as expected.

        To use, simply pass it in as the `id` kwarg when creating a model
        object, e.g,:
            role_id = next(self.next_id)
            models.Role(id=role_id, name=name, description=desc, project=proj)
        """
        self.next_id = count(1)

    def randomize_case(self, inp):
        return "".join(map(self.random_choice, zip(inp.lower(), inp.upper())))

    def make_string(self, prefix="", size=10, charset=None):
        if charset is None:
            charset = self.random_letters
        return prefix + "".join(islice(charset, size))

    def make_bytes(self, prefix="", size=10, charset=None):
        return self.make_string(prefix, size, charset).encode('utf-8')

    def make_digest(self):
        string = self.make_string().encode("ascii")
        return "sha256:" + hashlib.sha256(string).hexdigest()

    def make_semver(self, octets=3, prerelease=None, build=None, extra=None):
        """Generate a valid (or invalid, if you prefer) semantic version."""
        # TODO(nic): a way to generate a semver that is greater than / less
        #  than another semver, without a needlessly fidgety interface
        semver = ".".join(str(self.randint(0, 9)) for _ in range(octets))
        if prerelease is not None:
            semver += f"-{prerelease}"
        if build is not None:
            semver += f"+{build}"
        if extra is not None:
            semver += str(extra)
        return semver

    def make_domainname(self, prefix=None):
        # https://en.wikipedia.org/wiki/List_of_Internet_top-level_domains#Original_top-level_domains
        tlds = ("com", "org", "net", "int", "edu", "gov", "mil", "arpa")
        if prefix is None:
            prefix = self.make_string("site")
        return "{}.{}".format(prefix, self.random_choice(tlds))

    def make_url(self, scheme="http"):
        return "{}://{}/{}".format(
            scheme, self.make_domainname(), self.make_string("path")
        )

    def pick_enum(self, enum, but_not=frozenset()):
        return self.random_choice(
            [value for value in enum if value not in but_not]
        )

    def pick_bool(self):
        return self.random_choice([True, False])

    def make_datetime(self, from_utime=None):
        datetimes = (
            # Apollo 11 landing date
            datetime(1969, 7, 20, 20, 17, 40, tzinfo=timezone.utc),
            # Mars Pathfinder landing date
            datetime(1997, 7, 4, 16, 56, 55, tzinfo=timezone.utc),
            # New Horizons Pluto flyby date
            datetime(2015, 7, 14, 11, 49, 57, tzinfo=timezone.utc),
            # Venera 5 landing date
            datetime(1969, 5, 16, 6, 54, tzinfo=timezone.utc),
            # Huygens probe landing date
            datetime(2005, 1, 14, 12, 43, tzinfo=timezone.utc),
            # time_t == 0x7FFFFFFF
            datetime(2038, 1, 18, 19, 14, 7, tzinfo=timezone.utc),
        )
        if from_utime is not None:
            return datetime.fromtimestamp(from_utime, tz=timezone.utc)
        return self.random_choice(datetimes)


# Factory is a singleton.
factory = Factory()
