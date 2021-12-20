"""Playbook Create"""
# standard library
import base64
import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Union

# third-party
from pydantic import BaseModel

# first-party
from tcex.key_value_store import KeyValueApi, KeyValueRedis
from tcex.utils.utils import Utils

# get tcex logger
logger = logging.getLogger('tcex')


class PlaybookCreate:
    """Playbook Write ABC"""

    def __init__(
        self,
        context: str,
        key_value_store: Union[KeyValueApi, KeyValueRedis],
        output_variables: list,
    ):
        """Initialize the class properties."""
        self.context = context
        self.key_value_store = key_value_store
        self.output_variables = output_variables

        # properties
        # self._output_variables_by_key = None
        # self._output_variables_by_type = None
        self.log = logger
        self.utils = Utils()

    def _check_null(self, key: str, value: Any) -> bool:
        """Return True if key or value is null."""
        invalid = False
        if key is None:
            self.log.warning('The provided key was None.')
            invalid = True

        if value is None:
            self.log.warning(f'The provided value for key {key} was None.')
            invalid = True

        return invalid

    def _check_requested(self, variable: str, when_requested: bool) -> None:
        """Return True if output variable was requested by downstream app."""
        if when_requested is True and not self.is_requested(variable):
            self.log.debug(f'Variable {variable} was NOT requested by downstream app.')
            return False
        return True

    def _check_variable_type(self, variable: str, type_: str) -> bool:
        """Validate the correct type was passed to the method."""
        if self.utils.get_playbook_variable_model(variable).type.lower() != type_.lower():
            raise RuntimeError(
                f'Invalid variable provided ({variable}), variable must be of type {type_}.'
            )

    def _coerce_string_value(self, value: Union[bool, float, int, str]) -> str:
        """Return a string value from an bool or int."""
        # coerce bool before int as python says a bool is an int
        if isinstance(value, bool):
            # coerce bool to str type
            self.log.warning(f'Coercing bool value ({value}) to a string ("{str(value).lower()}").')
            value = str(value).lower()

        # coerce int to str type
        if isinstance(value, (float, int)):
            self.log.warning(f'Coercing float/int value ({value}) to a string ("{str(value)}").')
            value = str(value)

        return value

    def _create_data(self, key: str, value: Any) -> None:
        """Write data to key value store."""
        self.log.debug(f'writing variable {key.strip()}')
        try:
            return self.key_value_store.create(self.context, key.strip(), value)
        except RuntimeError as e:  # pragma: no cover
            self.log.error(e)

        return None

    def _get_variable(self, key: str, variable_type: Optional[str] = None) -> str:
        """Return properly formatted variable.

        A key can be provided as the variable key (e.g., app.output) or the
        entire (e.g., #App:1234:app.output!String). The full variable is required
        to create the record in the KV Store.

        If a variable_type is provided an exact match will be found, however if no
        variable type is known the first key match will be returned. Uniqueness of
        keys is not guaranteed, but in more recent Apps it is the standard.

        If no variable is found it means that the variable was not requested by the
        any downstream Apps or could possible be formatted incorrectly.
        """
        if not self.utils.is_playbook_variable(key):
            # try to lookup the variable in the requested output variables.
            for output_variable in self.output_variables:
                variable_model = self.utils.get_playbook_variable_model(output_variable)
                if variable_model.key == key and (
                    variable_type is None or variable_model.type == variable_type
                ):
                    # either an exact match, or first match
                    return output_variable
            # not requested by downstream App or misconfigured
            return None
        # key was already a properly formatted variable
        return key

    # def _parse_output_variables(self) -> None:
    #     """Parse the output variables provided to Playbook Class.

    #     Example Variable Format:

    #     ['#App:1234:status!String', '#App:1234:status_code!String']
    #     """
    #     self._output_variables_by_key = {}
    #     self._output_variables_by_type = {}
    #     for ov in self.output_variables:
    #         # parse the variable to get individual parts
    #         variable_model = self.utils.get_playbook_variable_model(ov)

    #         # store the variables in dict by key (e.g. "status_code")
    #         self._output_variables_by_key[variable_model.key] = {'variable': ov}

    #         # store the variables in dict by key-type (e.g. "status_code-String")
    #         self._output_variables_by_type[f'{variable_model.key}-{variable_model.type}'] = {
    #             'variable': ov
    #         }

    def _pre_create_checks(self, type_: str):
        """Run standard pre create checks."""

    @staticmethod
    def _serialize_data(value: str) -> str:
        """Get the value from Redis if applicable."""
        try:
            return json.dumps(value)
        except ValueError as e:  # pragma: no cover
            raise RuntimeError(f'Invalid data provided, failed to serialize value ({e}).')

    @staticmethod
    def _process_object_types(
        value: Union[BaseModel, dict],
        validate: Optional[bool] = True,
        allow_none: Optional[bool] = False,
    ) -> Dict[str, Any]:
        """Process object types (e.g., KeyValue, TCEntity)."""
        types = (BaseModel, dict)
        if allow_none is True:
            types = (BaseModel, dict, type(None))

        if validate and not isinstance(value, types):
            raise RuntimeError(f'Invalid type provided for object type ({type(value)}).')

        if isinstance(value, BaseModel):
            value = value.dict(exclude_unset=True)

        return value

    @staticmethod
    def is_key_value(data: dict) -> bool:
        """Return True if provided data has proper structure for Key Value."""
        if not isinstance(data, dict):
            return False
        return all(x in data for x in ['key', 'value'])

    def is_requested(self, variable: str) -> bool:
        """Return True if provided variable was requested by downstream App."""
        return variable in self.output_variables

    @staticmethod
    def is_tc_entity(data: dict) -> bool:
        """Return True if provided data has proper structure for TC Entity."""
        if not isinstance(data, dict):
            return False
        return all(x in data for x in ['id', 'value', 'type'])

    # @property
    # def output_variables_by_key(self) -> dict:
    #     """Return output variables stored as name dict."""
    #     if self._output_variables_by_key is None:
    #         self._parse_output_variables()
    #     return self._output_variables_by_key

    # @property
    # def output_variables_by_type(self) -> dict:
    #     """Return output variables stored as name-type dict."""
    #     if self._output_variables_by_type is None:
    #         self._parse_output_variables()
    #     return self._output_variables_by_type

    def any(
        self,
        key: str,
        value: Union[
            'BaseModel', bytes, dict, str, List['BaseModel'], List[bytes], List[dict], List[str]
        ],
        validate: Optional[bool] = True,
        variable_type: Optional[str] = None,
        when_requested: Optional[bool] = True,
    ) -> Optional[Union[bytes, dict, list, str]]:
        """Write the value to the keystore for all types.

        This is a quick helper method, for more advanced features
        the individual write methods should be used (e.g., binary).

        Args:
            key: The variable to write to the DB (e.g., app.colors).
            value: The data to write to the DB.
            variable_type: The variable type being written. Only required if not unique.

        Returns:
            (str): Result string of DB write.
        """
        if self._check_null(key, value) is True:
            return None

        # convert key to variable if required
        variable = self._get_variable(key, variable_type)

        if self._check_requested(variable, when_requested) is False:
            return None

        # get the type from the variable
        variable_type = self.utils.get_playbook_variable_model(variable).type.lower()

        # map type to create method
        variable_type_map = {
            'binary': self.binary,
            'binaryarray': self.binary_array,
            'keyvalue': self.key_value,
            'keyvaluearray': self.key_value_array,
            'string': self.string,
            'stringarray': self.string_array,
            'tcentity': self.tc_entity,
            'tcentityarray': self.tc_entity_array,
            'tcenhancedentity': self.tc_enhanced_entity_array,
        }
        return variable_type_map.get(variable_type, self.raw)(variable, value, validate)

    def binary(
        self,
        key: str,
        value: bytes,
        validate: Optional[bool] = True,
        when_requested: Optional[bool] = True,
    ) -> Optional[int]:
        """Create the value in Redis if applicable."""
        if self._check_null(key, value) is True:
            return None

        # convert key to variable if required
        variable = self._get_variable(key, 'Binary')
        if self._check_requested(variable, when_requested) is False:
            return None

        # quick check to ensure an invalid key was not provided
        self._check_variable_type(variable, 'Binary')

        # basic validation of value
        if validate and not isinstance(value, bytes):
            raise RuntimeError('Invalid data provided for Binary.')

        # prepare value - playbook Binary fields are base64 encoded
        value = base64.b64encode(value).decode('utf-8')
        value = self._serialize_data(value)
        return self._create_data(key, value)

    def binary_array(
        self,
        key: str,
        value: List[bytes],
        validate: Optional[bool] = True,
        when_requested: Optional[bool] = True,
    ):
        """Create the value in Redis if applicable."""
        if self._check_null(key, value) is True:
            return None

        # convert key to variable if required
        variable = self._get_variable(key, 'BinaryArray')
        if self._check_requested(variable, when_requested) is False:
            return None

        # quick check to ensure an invalid key was not provided
        self._check_variable_type(key, 'BinaryArray')

        # basic validation and prep of value
        value_encoded = []
        for v in value:
            if v is not None:
                if validate and not isinstance(v, bytes):
                    raise RuntimeError('Invalid data provided for Binary.')
                v = base64.b64encode(v).decode('utf-8')
            value_encoded.append(v)
        value = value_encoded

        value = self._serialize_data(value)
        return self._create_data(key, value)

    def key_value(
        self,
        key: str,
        value: Union[BaseModel, dict],
        validate: Optional[bool] = True,
        when_requested: Optional[bool] = True,
    ) -> Optional[int]:
        """Create the value in Redis if applicable."""
        if self._check_null(key, value) is True:
            return None

        # convert key to variable if required
        variable = self._get_variable(key, 'KeyValue')
        if self._check_requested(variable, when_requested) is False:
            return None

        # quick check to ensure an invalid key was not provided
        self._check_variable_type(key, 'KeyValue')

        # basic validation and prep of value
        value = self._process_object_types(value, validate)
        if validate and not self.is_key_value(value):
            raise RuntimeError('Invalid data provided for KeyValueArray.')

        value = self._serialize_data(value)
        return self._create_data(key, value)

    def key_value_array(
        self,
        key: str,
        value: List[Union[BaseModel, dict]],
        validate: Optional[bool] = True,
        when_requested: Optional[bool] = True,
    ):
        """Create the value in Redis if applicable."""
        if self._check_null(key, value) is True:
            return None

        # convert key to variable if required
        variable = self._get_variable(key, 'KeyValueArray')
        if self._check_requested(variable, when_requested) is False:
            return None

        # quick check to ensure an invalid key was not provided
        self._check_variable_type(key, 'KeyValueArray')

        # list is technically an Iterable, but callng it out is more explicit
        if validate and (isinstance(value, str) or not isinstance(value, (Iterable, list))):
            raise RuntimeError('Invalid data provided for KeyValueArray.')

        # basic validation and prep of value
        _value = []
        for v in value:
            v = self._process_object_types(v, validate, allow_none=True)
            if validate and not self.is_key_value(v):
                raise RuntimeError('Invalid data provided for KeyValueArray.')
            _value.append(v)
        value = _value

        value = self._serialize_data(value)
        return self._create_data(key, value)

    def string(
        self,
        key: str,
        value: Union[bool, float, int, str],
        validate: Optional[bool] = True,
        when_requested: Optional[bool] = True,
    ) -> Optional[int]:
        """Create the value in Redis if applicable."""
        if self._check_null(key, value) is True:
            return None

        # convert key to variable if required
        variable = self._get_variable(key, 'String')
        if self._check_requested(variable, when_requested) is False:
            return None

        # quick check to ensure an invalid key was not provided
        self._check_variable_type(key, 'String')

        # coerce string values
        value = self._coerce_string_value(value)

        # validation only needs to check str because value was coerced
        if validate and not isinstance(value, str):
            raise RuntimeError('Invalid data provided for String.')

        value = self._serialize_data(value)
        return self._create_data(key, value)

    def string_array(
        self,
        key: str,
        value: List[Union[bool, float, int, str]],
        validate: Optional[bool] = True,
        when_requested: Optional[bool] = True,
    ):
        """Create the value in Redis if applicable."""
        if self._check_null(key, value) is True:
            return None

        # convert key to variable if required
        variable = self._get_variable(key, 'String')
        if self._check_requested(variable, when_requested) is False:
            return None

        # quick check to ensure an invalid key was not provided
        self._check_variable_type(key, 'StringArray')

        # list is technically an Iterable, but callng it out is more explicit
        if validate and (isinstance(value, str) or not isinstance(value, (Iterable, list))):
            raise RuntimeError('Invalid data provided for StringArray.')

        # basic validation and prep of value
        value_coerced = []
        for v in value:
            # coerce string values
            v = self._coerce_string_value(v)

            # validation only needs to check str because value was coerced
            if validate and not isinstance(v, (type(None), str)):
                raise RuntimeError('Invalid data provided for StringArray.')
            value_coerced.append(v)
        value = value_coerced

        value = self._serialize_data(value)
        return self._create_data(key, value)

    # pylint: disable=unused-argument
    def raw(self, key: str, value: Union[bytes, str, int], validate: Optional[bool] = True) -> str:
        """Create method of CRUD operation for raw data.

        Raw data can only be a byte, str or int. Other data
        structures (dict, list, etc) must be serialized.
        """
        if self._check_null(key, value):
            return None

        return self._create_data(key, value)

    def tc_entity(
        self,
        key: str,
        value: Union[BaseModel, dict],
        validate: Optional[bool] = True,
        when_requested: Optional[bool] = True,
    ) -> Optional[int]:
        """Create the value in Redis if applicable."""
        if self._check_null(key, value) is True:
            return None

        # convert key to variable if required
        variable = self._get_variable(key, 'TCEntity')
        if self._check_requested(variable, when_requested) is False:
            return None

        # quick check to ensure an invalid key was not provided
        self._check_variable_type(key, 'TCEntity')

        # basic validation
        value = self._process_object_types(value, validate)
        if validate and not self.is_tc_entity(value):
            raise RuntimeError('Invalid data provided for TcEntityArray.')

        value = self._serialize_data(value)
        return self._create_data(key, value)

    def tc_entity_array(
        self,
        key: str,
        value: List[Union[BaseModel, dict]],
        validate: Optional[bool] = True,
        when_requested: Optional[bool] = True,
    ):
        """Create the value in Redis if applicable."""
        if self._check_null(key, value) is True:
            return None

        # convert key to variable if required
        variable = self._get_variable(key, 'TCEntityArray')
        if self._check_requested(variable, when_requested) is False:
            return None

        # quick check to ensure an invalid key was not provided
        self._check_variable_type(key, 'TCEntityArray')

        # basic validation and prep of value
        _value = []
        for v in value:
            v = self._process_object_types(v, validate, allow_none=True)
            if validate and not self.is_tc_entity(v):
                raise RuntimeError('Invalid data provided for TcEntityArray.')
            _value.append(v)
        value = _value

        value = self._serialize_data(value)
        return self._create_data(key, value)

    def tc_enhanced_entity_array(
        self,
        key: str,
        value: List[dict],
        validate: Optional[bool] = True,
        when_requested: Optional[bool] = True,
    ):
        """Create the value in Redis if applicable."""
        if self._check_null(key, value) is True:
            return None

        # convert key to variable if required
        variable = self._get_variable(key, 'TCEntityArray')
        if self._check_requested(variable, when_requested) is False:
            return None

        # quick check to ensure an invalid key was not provided
        self._check_variable_type(key, 'TCEnhancedEntityArray')

        # list is technically an Iterable, but callng it out is more explicit
        if validate and (isinstance(value, str) or not isinstance(value, (Iterable, list))):
            raise RuntimeError('Invalid data provided for TCEnhancedEntityArray.')

        value = [*value]  # spread the value so that we know it's a list (as opposed to an iterable)

        value = self._serialize_data(value)
        return self._create_data(key, value)

    def variable(
        self,
        key: str,
        value: Union[
            'BaseModel', bytes, dict, str, List['BaseModel'], List[bytes], List[dict], List[str]
        ],
        variable_type: Optional[str] = None,
    ) -> str:
        """Alias for any method of CRUD operation for working with KeyValue DB.

        This method will automatically check to see if provided variable was requested by
        a downstream app and if so create the data in the KeyValue DB.

        Args:
            key: The variable to write to the DB (e.g., app.colors).
            value: The data to write to the DB.
            variable_type: The variable type being written. Only required if not unique.

        Returns:
            (str): Result string of DB write.
        """
        if self._check_null(key, value) is True:
            return None

        # short-circuit the process, if there are no dowstream variables requested.
        if not self.output_variables:  # pragma: no cover
            self.log.debug(f'Variable {key} was NOT requested by downstream app.')
            return None

        # key can be provided as the variable key (e.g., app.output) or
        # the entire (e.g., #App:1234:app.output!String). we need the
        # full variable to proceed.
        variable = self._get_variable(key, variable_type)
        if variable is None or variable not in self.output_variables:
            self.log.debug(f'Variable {key} was NOT requested by downstream app.')
            return None

        # write the variable
        return self.any(variable, value)