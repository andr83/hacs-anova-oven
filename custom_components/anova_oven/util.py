import re
from dataclasses import fields, is_dataclass


def snake_case_to_camel_case(input_string):
    words = re.split("-|_", input_string)
    camel_case_words = [words[0]] + [word.capitalize() for word in words[1:]]
    return "".join(camel_case_words)


def camel_to_snake(name):
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def dict_keys_to_camel_case(data: dict):
    res = {}
    for k, v in data.items():
        if isinstance(v, dict):
            v = dict_keys_to_camel_case(v)
        elif isinstance(v, list):
            v = [dict_keys_to_camel_case(x) for x in v]
        res[snake_case_to_camel_case(k)] = v
    return res


def dict_keys_to_snake_case(data: dict):
    res = {}
    for k, v in data.items():
        if isinstance(v, dict):
            v = dict_keys_to_snake_case(v)
        elif isinstance(v, list):
            v = [dict_keys_to_snake_case(x) for x in v]
        res[camel_to_snake(k)] = v
    return res


def to_fahrenheit(celsius: int):
    return int((1.8 * celsius) + 32)


def to_celsius(fahrenheit):
    celsius = (fahrenheit - 32) * 5.0 / 9.0
    return celsius


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
