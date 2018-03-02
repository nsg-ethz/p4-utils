class NodeDoesNotExist(Exception):

    def __init__(self, node):
        self.message = "Node <{0}> does not exist".format(node)
        super(NodeDoesNotExist, self).__init__('NodeDoesNotExist: {0}'.format(self.message))

    def __str__(self):
        return self.message


class InvalidHostIP(Exception):

    def __init__(self, ip):
        self.message = "".format(ip)
        super(InvalidHostIP, self).__init__('InvalidHostIP: {0}'.format(self.message))

    def __str__(self):
        return self.message

FAILED_STATUS = 100
SUCCESS_STATUS = 200

DEFAULT_COMPILER = "p4c-bm2-ss -I /usr/local/share/p4c/p4include/"
DEFAULT_CLI = "simple_switch_CLI"
DEFAULT_SWITCH = "simple_switch"