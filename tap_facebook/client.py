"""REST client handling, including facebookStream base class."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable

import requests
from singer_sdk.authenticators import BearerTokenAuthenticator
from singer_sdk.helpers.jsonpath import extract_jsonpath
from singer_sdk.streams import RESTStream

_Auth = Callable[[requests.PreparedRequest], requests.PreparedRequest]
SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")


class facebookStream(RESTStream):
    """facebook stream class."""

    # open config.json to read account id
    # TODO switch config to meltano.yml and env variables, config.json for testing
    with open(".secrets/config.json") as config_json:
        config = json.load(config_json)

    # get account id from config.json
    account_id = config["account_id"]

    # add account id in the url
    url_base = "https://graph.facebook.com/v16.0/act_{}".format(account_id)

    records_jsonpath = "$.data[*]"  # Or override `parse_response`.
    next_page_token_jsonpath = (
        "$.paging.cursors.after"  # Or override `get_next_page_token`.
    )

    @property
    def authenticator(self) -> BearerTokenAuthenticator:
        """Return a new authenticator object.

        Returns,
            An authenticator instance.
        """
        return BearerTokenAuthenticator.create_for_stream(
            self,
            token=self.config.get("access_token", ""),
        )

    def get_next_page_token(
        self,
        response: requests.Response,
        previous_token: Any | None,
    ) -> Any | None:
        """Return a token for identifying next page or None if no more pages.

        Args,
            response: The HTTP ``requests.Response`` object.
            previous_token: The previous page token value.

        Returns,
            The next pagination token.
        """
        if self.next_page_token_jsonpath:
            all_matches = extract_jsonpath(
                self.next_page_token_jsonpath, response.json()
            )
            first_match = next(iter(all_matches), None)
            next_page_token = first_match
        else:
            next_page_token = response.headers.get("X-Next-Page", None)

        return next_page_token

    def get_url_params(
        self,
        context: dict | None,
        next_page_token: Any | None,
    ) -> dict[str, Any]:
        """Return a dictionary of values to be used in URL parameterization.

        Args,
            context: The stream context.
            next_page_token: The next page index or value.

        Returns,
            A dictionary of URL query parameters.
        """
        params: dict = {}
        params["limit"] = 25
        if next_page_token is not None:
            params["after"] = next_page_token
        if self.replication_key:
            params["sort"] = "asc"
            params["order_by"] = self.replication_key

        return params

    def prepare_request_payload(
        self,
        context: dict | None,
        next_page_token: Any | None,
    ) -> dict | None:
        """Prepare the data payload for the REST API request.

        By default, no payload will be sent (return None).

        Args,
            context: The stream context.
            next_page_token: The next page index or value.

        Returns,
            A dictionary with the JSON body for a POST requests.
        """
        return None

    def parse_response(self, response: requests.Response) -> Iterable[dict]:
        """Parse the response and return an iterator of result records.

        Args,
            response: The HTTP ``requests.Response`` object.

        Yields,
            Each record from the source.
        """
        yield from extract_jsonpath(self.records_jsonpath, input=response.json())
