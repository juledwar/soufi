# Copyright (c) 2021-2023 Cisco Systems, Inc. and its affiliates
# All rights reserved.

import itertools
from importlib import import_module
from unittest import mock
from unittest.mock import MagicMock

import requests
import testtools

from soufi.testing import factory


# TODO(nic): this needs to handle "unbalanced" parameter sets; if all
#  parameters are not provided with all scenarios, then the parameter lists
#  go out of sync with the inputs.  If you call this without properly
#  defining your input scenarios, you get to keep all the pieces.
# TODO(nic): give this to testscenarios, if we think it might be useful to them
def combine_scenarios(*scenarios):
    """Create a combinatorial matrix of all provided scenarios.

    Like `testscenarios.scenarios.multiply_scenarios`, but it stacks up all
    possible combinations of scenarios rather than creating a cross-product.

    :returns: A list of compound scenarios: the combination of all
        scenarios, with the names concatenated and the parameters of all
        scenarios stacked into lists.
    """
    result = []
    scenario_lists = list(map(list, scenarios))
    for i in range(1, len(*scenarios) + 1):
        for combination in itertools.combinations(*scenario_lists, i):
            names, parameters = zip(*combination)
            scenario_name = ",".join(names)
            scenario_parameters = {}
            for parameter in parameters:
                for k, v in parameter.items():
                    if k not in scenario_parameters:
                        scenario_parameters[k] = []
                    scenario_parameters[k].append(v)
            result.append((scenario_name, scenario_parameters))
    return result


class TestCase(testtools.TestCase):
    """Base class for all tests."""

    factory = factory.factory

    def patch(
        self, obj, attribute=None, value=mock.sentinel.unset
    ) -> MagicMock:
        """Patch `obj.attribute` with `value`.

        If `value` is unspecified, a new `MagicMock` will be created and
        patched-in instead. Its ``__name__`` attribute will be set to
        `attribute` or the ``__name__`` of the replaced object if `attribute`
        is not given.

        This is a thin customisation of `testtools.TestCase.patch`, so refer
        to that in case of doubt.

        :return: The patched-in object.
        """
        # If 'attribute' is None, assume 'obj' is a 'fully-qualified' object,
        # and assume that its __module__ is what we want to patch. For more
        # complex use cases, the two-parameter 'patch' will still need to
        # be used.
        if attribute is None:
            attribute = obj.__name__
            obj = import_module(obj.__module__)
        else:
            if not hasattr(obj, attribute):
                # Prevent footgunning.
                raise AttributeError(f"{attribute} does not exist on {obj}")
        if value is mock.sentinel.unset:
            value = MagicMock(__name__=attribute)
        super().patch(obj, attribute, value)
        return value

    def extend_side_effects(self, mock_obj, extra_value):
        """Cumulatively add side effects to an existing Mock.

        :param mock_obj: The Mock object
        :param extra_value: Any object which to add to the
            Mock.side_effect

        This exists because Mock implements side_effect as a list iterator,
        which means there's extra work than simply appending to an existing
        list of side_effects.
        """
        effects = list(mock_obj.side_effect)
        effects.append(extra_value)
        mock_obj.side_effect = effects

    def patch_get_with_response(self, response_code, data=None, json=None):
        """Patch `requests.get` with the provided values.

        :param response_code: A requests.codes value, to mimic an HTTP status
        :param data: A string-like object to mimic Response.content
        :param json: A dict or list, to mimic what Response.json() would return
        :return: The created MagicMock, to add side-effects, etc.
        """
        fake_response = mock.MagicMock()
        fake_response.return_value.status_code = response_code
        fake_response.return_value.content = data
        fake_response.return_value.json.return_value = json
        return self.patch(requests, 'get', fake_response)

    def patch_head_with_response(self, response_code):
        """Patch `requests.head` with the provided values.

        HEAD requests have an empty message body, so no data is accepted.

        :param response_code: A requests.codes value, to mimic an HTTP status
        :return: The created MagicMock, to add side-effects, etc.
        """
        fake_response = mock.MagicMock()
        fake_response.return_value.status_code = response_code
        return self.patch(requests, 'head', fake_response)
