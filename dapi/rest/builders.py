from __future__ import annotations

import copy
import json as jsonlib
from typing import Any, Mapping, MutableMapping, MutableSequence, Optional
from urllib import parse

import aiohttp
import attr

__all__ = ("JSONBuilder", "ParamsBuilder", "FormBuilder")


@attr.define(init=False)
class JSONBuilder:
    """Represents a JSON object"""

    inner: MutableMapping[str, Any] = attr.field(init=False)
    """ The inner representation of the JSON """

    def __init__(self, **kwargs: Any):
        self.inner = kwargs

    def add(self, key: str, value: Any) -> JSONBuilder:
        """Add a key to the JSON mapping

        Parameters
        ----------
        key : builtins.str
            The key.
        value : typing.Any
            The value that the key represents. (Will implicitly
            call `to_json` if the type supports it).

        Returns
        -------
        dapi.rest.builders.JSONBuilder
            The builder object, can be used for chaining.
        """

        if hasattr(value, "to_json"):
            value = value.to_json()

        self.inner[key] = value
        return self

    def build(self) -> Mapping[str, Any]:
        """Builds the JSON object into a mapping. (This makes
        a deepcopy of the underlying object).

        Returns
        -------
        typing.Mapping[builtins.str, typing.Any]
        """

        return copy.deepcopy(self.inner)


@attr.define(init=False)
class ParamsBuilder:
    """Represents the parameters of the query string"""

    inner: MutableMapping[str, str] = attr.field(init=False)
    """ The inner representation of the parameters """

    def __init__(self, **kwargs: str):
        self.inner = {}

        for key, value in kwargs.items():
            self.inner[key] = parse.quote_plus(value)

    def add(self, key: str, value: str) -> ParamsBuilder:
        """Add a parameter to the parameters

        Parameters
        ----------
        key : builtins.str
            The key.
        value : typing.Any
            The value that the key represents.

        Returns
        -------
        dapi.rest.builders.ParamsBuilder
            The builder object, can be used for chaining.
        """

        self.inner[key] = parse.quote_plus(value)

        return self

    def build(self) -> Mapping[str, str]:
        """Build the parameters into a mapping.

        Returns
        -------
        typing.Mapping[builtins.str, builtins.str]
            The mapping referring to the parameters.
        """

        new = {}
        for key, value in self.inner.items():
            new[key] = value

        return new


@attr.define(init=False)
class FormBuilder:
    """Represents a multipart form"""

    fields: MutableSequence[Mapping[str, Any]] = attr.field(init=False)
    """ The raw fields that the form contains """

    def __init__(self):
        self.fields = []

    def add_field(
        self,
        name: str,
        value: Any,
        content_type: Optional[str] = None,
        filename: Optional[str] = None,
        content_transfer_encoding: Optional[str] = None,
    ) -> FormBuilder:
        """Adds an field to the form.

        Parameters
        ----------
        name : builtins.str
            The name of the field.
        value : typing.Any
            The value of the field (can be bytes!)
        content_type : typing.Optional[builtins.str]
            The content-type of the value, defaults to
            `application/octet-stream`.
        filename : typing.Optional[builtins.str]
            The filename of the field.
        content_transfer_encoding : typing.Optional[builtins.str]
            The content transfer encoding.

        Returns
        -------
        dapi.rest.builders.FormBuilder
            The builder object, can be used for chaining.
        """

        if content_type is None:
            content_type = "application/octet-stream"

        self.fields.append(
            dict(
                name=name,
                value=value,
                content_type=content_type,
                filename=filename,
                content_transfer_encoding=content_transfer_encoding,
            )
        )
        return self

    def add_json(self, json: Mapping[str, Any]) -> FormBuilder:
        """Shortcut for adding the `payload_json` field to a
        form.

        Parameters
        ----------
        json : typing.Dict[builtins.str, typing.Any]
            The JSON data that you want to attach.

        Returns
        -------
        dapi.rest.builders.FormBuilder
            The builder object, can be used for chaining.
        """

        self.add_field(
            name="payload_json",
            value=jsonlib.dumps(json),
            content_type="application/json",
        )

        return self

    def build(self) -> aiohttp.FormData:
        """Builds the form into an aiohttp.FormData object

        Returns
        -------
        aiohttp.FormData
            The form object.
        """

        form = aiohttp.FormData()
        for field in self.fields:
            form.add_field(**field)

        return form
