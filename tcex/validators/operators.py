"""Validators that implement the operators in the operator module."""
# standard library
import operator
from typing import Any, Callable

from .validation_exception import ValidationError


def _operator(
    operator_call: Callable, compare_to: Any, message_posfix: str, allow_none=False,
):
    def _validate(value, arg_name):
        if not isinstance(value, list):
            value = [value]

        for v in value:
            if allow_none and v is None:
                continue

            if not operator_call(v, compare_to):
                raise ValidationError(f'{arg_name} {message_posfix}')

    return _validate


def equal_to(compare_to: Any, allow_none=False) -> Callable[[str, str], None]:
    """Validate that an argument is equal to a given value.

    Allowed argument types: String

    Args:
        compare_to (Any): the value to compare the argument value to.
        allow_none (bool): skip any None elements
    Returns:
        A validator function that can be used in the validators argument to @ReadArg.
    """
    formatted_value = f'"{compare_to}"' if isinstance(compare_to, str) else compare_to
    return _operator(operator.eq, compare_to, f'is not equal to {formatted_value}', allow_none)


def less_than(compare_to: Any, allow_none=False) -> Callable[[str, str], None]:
    """Validate that an argument is less than a given value.

    Allowed argument types: String, StringArray

    Args:
        compare_to (Any): the value to compare the argument value to.
        allow_none (bool): skip any None elements
    Returns:
        A validator function that can be used in the validators argument to @ReadArg.
    """
    formatted_value = f'"{compare_to}"' if isinstance(compare_to, str) else compare_to
    return _operator(operator.lt, compare_to, f'is not less than {formatted_value}', allow_none)


def less_than_or_equal(compare_to: Any, allow_none=False) -> Callable[[str, str], None]:
    """Validate that an argument is less than or equal to a given value.

    Allowed argument types: String, StringArray

    Args:
        compare_to (Any): the value to compare the argument value to.
        allow_none (bool): skip any None elements
    Returns:
        A validator function that can be used in the validators argument to @ReadArg.
    """
    formatted_value = f'"{compare_to}"' if isinstance(compare_to, str) else compare_to
    return _operator(
        operator.le, compare_to, f'is not less than or equal to {formatted_value}', allow_none,
    )


def greater_than(compare_to: Any, allow_none=False) -> Callable[[str, str], None]:
    """Validate that an argument is greater than a given value.

    Allowed argument types: String, StringArray

    Args:
        compare_to (Any): the value to compare the argument value to.
        allow_none (bool): skip any None elements
    Returns:
        A validator function that can be used in the validators argument to @ReadArg.
    """
    formatted_value = f'"{compare_to}"' if isinstance(compare_to, str) else compare_to
    return _operator(operator.gt, compare_to, f'is not greater than {formatted_value}', allow_none)


def greater_than_or_equal(compare_to: Any, allow_none=False) -> Callable[[str, str], None]:
    """Validate that an argument is greater than or equal to a given value.

    Allowed argument types: String, StringArray

    Args:
        compare_to (Any): the value to compare the argument value to.
        allow_none (bool): skip any None elements
    Returns:
        A validator function that can be used in the validators argument to @ReadArg.
    """
    formatted_value = f'"{compare_to}"' if isinstance(compare_to, str) else compare_to
    return _operator(
        operator.ge, compare_to, f'is not greater than or equal to {formatted_value}', allow_none,
    )