import os
import psutil
from mininet.log import debug, info, warning


def run_command(command):
    debug(command)
    return os.WEXITSTATUS(os.system(command))


def check_listening_on_port(port):
    for c in psutil.net_connections(kind='inet'):
        if c.status == 'LISTEN' and c.laddr[1] == port:
            return True
    return False