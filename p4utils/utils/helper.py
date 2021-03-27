import os
import sys
import psutil
import mininet
import hashlib
import importlib
import json
import subprocess
from networkx.readwrite.json_graph import node_link_graph
from mininet.log import info, output, error, warn, debug

from p4utils.utils.topology_new import NetworkGraph


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


def get_node_attr(node, attr_name):
    """
    Finds the value of the attribute 'attr_name' of the Mininet node
    by looking also inside node.params (for unparsed attributes).

    Arguments:
        node                : Mininet node object
        attr_name (string)  : attribute to looking for (also inside unparsed ones)
    
    Returns:
        the value of the requested attribute.
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
    Return the first object in the list that has the attribute 'attr_name'
    value equal to attr_value.

    Arguments:
        attr_name (string)  : attribute name
        attr_value          : attrubute value
        obj_list (list)     : list of objects

    Returns:
        obj : the requested object or None
    """
    for obj in obj_list:
        if attr_value == getattr(obj, attr_name):
            return obj
    else:
        return None


def ip_address_to_mac(ip):
    """Generate MAC from IP address."""
    if "/" in ip:
        ip = ip.split("/")[0]

    split_ip = list(map(int, ip.split(".")))
    mac_address = '00:%02x' + ':%02x:%02x:%02x:%02x' % tuple(split_ip)
    return mac_address


def is_compiled(p4_src, compilers):
    """
    Check if a file has been already compiled by at least
    one compiler in the list.

    Arguments:
        p4_src (string)    : P4 file path
        compilers (list)        : list of P4 compiler objects (see compiler.py)
    
    Returns:
        True/False depending on whether the file has been already compiled.
    """
    for compiler in compilers:
        if getattr(compiler, 'compiled') and getattr(compiler, 'p4_src') == p4_src:
            return True
    else:
        return False


def load_conf(conf_file):
    with open(conf_file, 'r') as f:
        config = json.load(f)
    return config


def load_topo(json_path):
    """
    Load the topology from the json_path provided

    Arguments:
        json_path (string): path of the JSON file to load

    Returns:
        p4utils.utils.topology.NetworkGraph object
    """
    with open(json_path,'r') as f:
        graph_dict = json.load(f)
        graph = node_link_graph(graph_dict)
    return NetworkGraph(graph)


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