"""TcEx Framework Module"""

# standard library
import json
import logging
import urllib.parse
from abc import ABC
from collections.abc import Generator
from typing import Any

# third-party
from requests import Response, Session
from requests.exceptions import ProxyError, RetryError

# first-party
from tcex.api.tc.v3.tql.tql import Tql
from tcex.exit.error_code import handle_error
from tcex.logger.trace_logger import TraceLogger
from tcex.pleb.cached_property import cached_property
from tcex.util import Util

# get tcex logger
_logger: TraceLogger = logging.getLogger(__name__.split('.', maxsplit=1)[0])  # type: ignore


class ObjectCollectionABC(ABC):  # noqa: B024
    """Case Management Collection Abstract Base Class

    This class is a base class for Case Management collections that use
    multi-inheritance with a pydantic BaseModel class. To ensure
    properties are not added to the model both @property and @setter
    methods are used.
    """

    def __init__(
        self,
        session: Session,
        tql_filters: list | None = None,  # This will be removed!
        params: dict | None = None,
    ):
        """Initialize instance properties."""
        self._params = params or {}
        self._tql_filters = tql_filters or []

        # properties
        self._session = session
        self.log = _logger
        self.request: Response
        self.tql = Tql()
        self._model = None
        self.type_ = None  # defined in child class
        self.util = Util()

    def __len__(self) -> int:
        """Return the length of the collection."""
        parameters = self._params.copy()
        parameters['resultLimit'] = 1
        parameters['count'] = True
        tql_string = self.tql.raw_tql
        if self.type_ and self.type_.lower() in {'exclusion_lists'}:
            ex_msg = f'len op not supported for {self.type_} API endpoint.'
            raise NotImplementedError(ex_msg)
        if not self.tql.raw_tql:
            tql_string = self.tql.as_str
        if tql_string:
            parameters['tql'] = tql_string

        # convert all keys to camel case
        for k, v in list(parameters.items()):
            k_ = self.util.snake_to_camel(k)
            # if result_limit and resultLimit both show up use the proper cased version
            if k_ not in parameters:
                parameters[k_] = v

        self._request(
            'GET',
            self._api_endpoint,
            body=None,
            params=parameters,
            headers={'content-type': 'application/json'},
        )
        return self.request.json().get('count', len(self.request.json().get('data', [])))

    @property
    def _api_endpoint(self):  # pragma: no cover
        """Return filter method."""
        ex_msg = 'Child class must implement this method.'
        raise NotImplementedError(ex_msg)

    @property
    def _max_logging_segment(self) -> int:
        """Return the maximum logging length based on the log level."""
        match self.log.getEffectiveLevel():
            case logging.DEBUG:
                return 1_000

            case logging.TRACE:  # type: ignore
                return 1_500

            case _:
                return 200

    def _request(
        self,
        method: str,
        url: str,
        body: bytes | str | None = None,
        params: dict | None = None,
        headers: dict | None = None,
    ):
        """Handle standard request with error checking."""
        max_param_length = 2_000
        if method == 'GET' and body is None and params is not None and params:
            query_string = urllib.parse.urlencode(params)
            if len(query_string) > max_param_length:
                # set body to the format that TC support for params in body
                body = json.dumps({'data': params})
                # reset params to None
                params = None

        try:
            self.log_request(method, url, body, params)
            self.request = self._session.request(
                method, url, data=body, headers=headers, params=params
            )
        except (ConnectionError, ProxyError, RetryError):  # pragma: no cover
            handle_error(
                code=951,
                message_values=[
                    method.upper(),
                    None,
                    '{"message": "Connection/Proxy Error/Retry"}',
                    url,
                ],
            )

        if not self.success(self.request):
            err = self.request.text or self.request.reason
            handle_error(
                code=950,
                message_values=[
                    self.request.request.method,
                    self.request.status_code,
                    err,
                    self.request.url,
                ],
            )

        # log content for debugging
        self.log_response(self.request)

    @property
    def filter(self):  # pragma: no cover
        """Return filter method."""
        ex_msg = 'Child class must implement this method.'
        raise NotImplementedError(ex_msg)

    def log_request(
        self, method: str, url: str, body: bytes | str | None = None, params: dict | None = None
    ):
        """Log the response text."""
        max_log_segment = self._max_logging_segment

        if isinstance(body, bytes):
            body = '[binary data]'

        if body is not None and len(body) > (max_log_segment * 2):
            body = body[:max_log_segment] + '... [truncated] ...' + body[-max_log_segment:]

        self.log.info(
            f'feature=api-tc-v3, request-method={method}, request-url={url}, '
            f'request-body={body}, request-params={params}',
        )

    def log_response(self, response: Response):
        """Log the response text."""
        max_log_segment = self._max_logging_segment

        body = response.text
        if body is not None and len(body) > (max_log_segment * 2):
            body = body[:max_log_segment] + '... [truncated] ...' + body[-max_log_segment:]

        self.log.info(
            f'feature=api-tc-v3, response-status={response.status_code}, '
            f'response-body={body}, response-elapsed={response.elapsed.total_seconds()}, '
            f'response-url={response.request.url}'
        )

    @property
    def model(self):
        """Return the model."""
        return self._model

    @model.setter
    def model(self, data):
        self._model = type(self.model)(**data)

    def iterate(
        self,
        base_class: Any,
        api_endpoint: str | None = None,
        params: dict | None = None,
    ) -> Generator:
        """Iterate over CM/TI objects."""
        url = api_endpoint or self._api_endpoint
        params = params or self.params

        # special parameter for indicators to enable the return the the indicator fields
        # (value1, value2, value3) on std-custom/custom-custom indicator types.
        if self.type_ == 'Indicators' and api_endpoint is None:
            params.setdefault('fields', []).append('genericCustomIndicatorValues')

        # convert all keys to camel case
        for k, v in list(params.items()):
            k_ = self.util.snake_to_camel(k)
            params[k_] = v

        tql_string = self.tql.raw_tql or self.tql.as_str

        if tql_string:
            params['tql'] = tql_string

        while True:
            self._request(
                'GET',
                body=None,
                url=url,
                headers={'content-type': 'application/json'},
                params=params,
            )

            # reset some vars
            params = {}

            response = self.request.json()
            data = response.get('data', [])
            url = response.pop('next', None)

            for result in data:
                yield base_class(session=self._session, **result)  # type: ignore

            # break out of pagination if no next url present in results
            if not url:
                break

    @property
    def params(self) -> dict:
        """Return the parameters of the case management object collection."""
        return self._params

    @params.setter
    def params(self, params: dict):
        """Set the parameters of the case management object collection."""
        self._params = params

    @staticmethod
    def success(r: Response) -> bool:
        """Validate the response is valid.

        Args:
            r (requests.response): The response object.

        Returns:
            bool: True if status is "ok"
        """
        status = True
        if r.ok:
            try:
                if r.json().get('status') != 'Success':  # pragma: no cover
                    status = False
            except Exception:  # pragma: no cover
                status = False
        else:
            status = False
        return status

    @property
    def timeout(self) -> int:
        """Return the timeout of the case management object collection."""
        return self._timeout

    @timeout.setter
    def timeout(self, timeout: int):
        """Set the timeout of the case management object collection."""
        self._timeout = timeout

    @cached_property
    def tql_options(self):
        """Return TQL data keywords."""
        _data = []
        r = self._session.options(f'{self._api_endpoint}/tql', params={})
        if r.ok:
            _data = r.json()['data']
        return _data

    @property
    def tql_keywords(self):
        """Return supported TQL keywords."""
        return [to.get('keyword') for to in self.tql_options]
