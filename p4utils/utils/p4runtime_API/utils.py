# See https://stackoverflow.com/a/32997046
def my_partialmethod(func, *args1, **kwargs1):
    def method(self, *args2, **kwargs2):
        return func(self, *args1, *args2, **kwargs1, **kwargs2)
    return method


class UserError(Exception):
    def __init__(self, info=""):
        self.info = info

    def __str__(self):
        return self.info

    # TODO(antonin): is this the best way to get a custom traceback?
    def _render_traceback_(self):
        return [str(self)]


class InvalidP4InfoError(Exception):
    def __init__(self, info=""):
        self.info = info

    def __str__(self):
        return "Invalid P4Info message: {}".format(self.info)

    def _render_traceback_(self):
        return [str(self)]
