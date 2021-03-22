import os
import sys
import psutil
import mininet
import hashlib
import importlib
import json
import subprocess
from mininet.log import info, output, error, warn, debug


def check_listening_on_port(port):
    for c in psutil.net_connections(kind='inet'):
        if c.status == 'LISTEN' and c.laddr[1] == port:
            return True
    return False


def cksum(filename):
    """Returns the md5 checksum of a file."""
    return hashlib.md5(open(filename,'rb').read()).hexdigest()


def cleanup():
    mininet.clean.cleanup()
    bridges = mininet.clean.sh("brctl show | awk 'FNR > 1 {print $1}'").splitlines()
    for bridge in bridges:
        mininet.clean.sh("ifconfig {} down".format(bridge))
        mininet.clean.sh("brctl delbr {}".format(bridge))


def formatLatency(latency):
    """Helper method for formatting link latencies."""
    if isinstance(latency, str):
        return latency
    else:
        return str(latency) + "ms"


def ip_address_to_mac(ip):
    """Generate MAC from IP address."""
    if "/" in ip:
        ip = ip.split("/")[0]

    split_ip = list(map(int, ip.split(".")))
    mac_address = '00:%02x' + ':%02x:%02x:%02x:%02x' % tuple(split_ip)
    return mac_address


def is_compiled(p4_filepath, compilers):
    """
    Check if a file has been already compiled by at least
    one compiler in the list.

    Arguments:
        p4_filepath (string)    : P4 file path
        compilers (list)        : list of P4 compiler objects (see compiler.py)
    
    Returns:
        True/False depending on whether the file has been already compiled.
    """
    for compiler in compilers:
        if compiler.compiled and compiler.p4_filepath == p4_filepath:
            return True
    else:
        return False

def get_node_attr(node, attr_name):
    """
    Finds the value of the attribute attr_name of the Mininet node
    by looking also inside node.params (for implicit attributes).
    """
    try:
        value = getattr(node, attr_name)
    except AttributeError:
        params = getattr(node, 'params')
        if attr_name in params.keys():
            return params[attr_name]
        else:
            raise AttributeError

def get_by_attr(attr_name, attr_value, obj_list):
    """
    Return the object in the list which has the attribute 'attr_name'
    value equal to attr_value
    """
    for obj in obj_list:
        if attr_value == getattr(obj, attr_name):
            return obj
    else:
        return None


def load_conf(conf_file):
    with open(conf_file, 'r') as f:
        config = json.load(f)
    return config


def load_custom_object(obj):
    """
    Load object from module
    
    Arguments:
        
    
    This function takes as input a module object
    {
        "file_path": path_to_module,
        "module_name": module_file_name,
        "object_name": module_object,
    }

    "file_path" is optional and has to be used if the module is not present in sys.path.
    """

    file_path = obj.get("file_path", ".")
    sys.path.insert(0, file_path)

    module_name = obj["module_name"]
    object_name = obj["object_name"]

    module = importlib.import_module(module_name)
    return getattr(module, object_name)


def run_command(command):
    debug(command+'\n')
    return os.WEXITSTATUS(os.system(command))