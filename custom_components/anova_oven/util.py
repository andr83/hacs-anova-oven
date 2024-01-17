import re
from typing import Dict
from dataclasses import fields, is_dataclass


def snake_case_to_camel_case(input_string):
    words = re.split("-|_", input_string)
    camel_case_words = [words[0]] + [word.capitalize() for word in words[1:]]
    return "".join(camel_case_words)


def dict_keys_to_camel_case(data: Dict):
    res = {}
    for k, v in data.items():
        if isinstance(v, dict):
            v = dict_keys_to_camel_case(v)
        elif isinstance(v, list):
            v = [dict_keys_to_camel_case(x) for x in v]
        res[snake_case_to_camel_case(k)] = v
    return res


def to_fahrenheit(celsius: int):
    return int((1.8 * celsius) + 32)


def to_dict(instance):
    res = {}
    for field in fields(instance):
        value = getattr(instance, field.name)
        if is_dataclass(value):
            value = to_dict(value)
        elif isinstance(value, list):
            value = [to_dict(x) if is_dataclass(x) else x for x in value]
        if value is not None:
            res[field.name] = value
    return res
