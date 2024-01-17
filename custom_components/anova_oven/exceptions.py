class AnovaException(Exception):
    pass


class AnovaOffline(AnovaException):
    pass


class InvalidAuth(AnovaException):
    pass


class NoDevicesFound(AnovaException):
    pass


class CommandError(AnovaException):
    pass
