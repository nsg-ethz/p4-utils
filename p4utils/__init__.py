class HostDoesNotExist(Exception):

    def __init__(self, message):
        super(HostDoesNotExist, self).__init__('HostDoesNotExist: {0}'.format(message))
        self.message = message

    def __str__(self):
        return self.message


class InvalidIP(Exception):

    def __init__(self, message):
        super(InvalidIP, self).__init__('InvalidIP: {0}'.format(message))
        self.message = message

    def __str__(self):
        return self.message

FAILED_STATUS = 100