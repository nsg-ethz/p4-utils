import os
import re
import sys
import random
import psutil
import mininet
import hashlib
import importlib
import json
import subprocess
from networkx.readwrite.json_graph import node_link_graph
from mininet.log import info, output, error, warn, debug

from p4utils.utils.topology import NetworkGraph


def merge_dict(dst, src):
    """
    Merge dictionary src into dictionary dst (nested dictionaries
    are updated).
    """
    stack = [(dst, src)]
    while stack:
        current_dst, current_src = stack.pop()
        for key in current_src:
            if key not in current_dst:
                current_dst[key] = current_src[key]
            else:
                if isinstance(current_src[key], dict) and isinstance(current_dst[key], dict):
                    stack.append((current_dst[key], current_src[key]))
                else:
                    current_dst[key] = current_src[key]


def next_element(elems, minimum=None, maximum=None):
    """
    Given a list of integers, return the next number not
    already present in the set starting from minimum and
    ending in maximum.
    """
    elements = set(elems)
    if len(elems) != len(elements):
        raise Exception('the list contains duplicates.')
    if len(elems) == 0:
        return minimum
    else:
        if maximum is None:
            maximum = max(elements)
        if minimum is None:
            minimum = min(elements)
        else:
            # Remove elements lower than minimum
            del_elements = set()
            for elem in elements:
                if elem < minimum:
                    del_elements.add(elem)
            elements.difference_update(del_elements)
            # Update maximum
            maximum = max(maximum, minimum)

        if len(elements) == (maximum - minimum) + 1:
            return maximum + 1
        elif len(elements) < (maximum - minimum) + 1:
            for elem in range(minimum, maximum+1):
                if elem not in elements:
                    return elem
        else:
            raise Exception('too many elements in the list.')


def natural(text):
    """
    To sort sanely/alphabetically: sorted(l, key=natural).
    """
    def num(s):
        """
        Convert text segment to int if necessary.
        """
        return int(s) if s.isdigit() else s
    return [num(s) for s in re.split(r'(\d+)', str(text))]


def naturalSeq(t):
    """
    Natural sort key function for sequences.
    """
    return [ natural( x ) for x in t ]


def rand_mac():
    """
    Return a random, non-multicast MAC address.
    """
    hex_str = hex(random.randint(1, 2**48-1) & 0xfeffffffffff | 0x020000000000)[2:]
    hex_str = '0'*(12-len(hex_str)) + hex_str
    mac_str = ''
    i = 0
    while i < len(hex_str):
        mac_str += hex_str[i]
        mac_str += hex_str[i+1]
        mac_str += ':'
        i += 2
    return mac_str[:-1]


def dpidToStr(id):
    """
    Compute a string dpid from an integer id.
    """
    strDpid = hex(id)[2:]
    if len(strDpid) < 16:
        return '0'*(16-len(strDpid)) + strDpid
    return strDpid


def check_listening_on_port(port):
    """
    Check if the given port is listening in the main
    namespace.
    """
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


def get_node_attr(node, attr_name, default=None):
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
        return getattr(node, attr_name)
    except AttributeError:
        try:
            params = getattr(node, 'params')
            if attr_name in params.keys():
                return params[attr_name]
            else:
                return default
        except AttributeError:
            return default


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
        p4_src (string) : P4 file path
        compilers (list): list of P4 compiler objects (see compiler.py)
    
    Returns:
        True/False depending on whether the file has been already compiled.
    """
    for compiler in compilers:
        if getattr(compiler, 'compiled') and getattr(compiler, 'p4_src') == p4_src:
            return True
    else:
        return False


def load_conf(conf_file):
    """
    Load JSON application configuration file.
    """
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

    'file_path' is optional and has to be used if the module is not present in sys.path.
    """

    file_path = obj.get("file_path", ".")
    sys.path.insert(0, file_path)

    module_name = obj["module_name"]
    object_name = obj["object_name"]

    module = importlib.import_module(module_name)
    return getattr(module, object_name)


def run_command(command):
    """
    Execute command in the main namespace.
    """
    debug(command+'\n')
    return os.WEXITSTATUS(os.system(command))


def parse_line(line):
    """
    Parse text line returning a list of substrings.
    Example:
        ahjdjf djdfkfo1 --jdke hdjejeek --dfjfj "vneovn rijvtg"
    Return:
        ["ahjdjf", "djdfkfo1", "--jdke", "hdjejeek", "--dfjfj", "vneovn rijvtg"]
    """
    # Isolate "" terms
    args1 = line.split('"')
    args2 = []
    for i in range(len(args1)):
        if i % 2 == 0:
            # Isolate and append spaced terms
            args2.extend(args1[i].split())
        else:
            # Append "" terms
            args2.append(args1[i])
    return args2


def parse_task_line(line, def_mod='p4utils.utils.traffic_utils'):
    """
    Parse text line and return all the parameters needed
    to create a task with NetworkAPI.addTask().

    Arguments:
        line (str)   : string containing all the task information
        def_mod (str): default module where to look for exe functions

    Notice:
        The file has to be a set of lines, where each has the following syntax.
        A non-default module can be specified in the command with '--mod <module>'.
        <node> <start> <duration> <exe> [<arg1>] ... [<argN>] [--mod <module>] [--<key1> <kwarg1>] ... [--<keyM> <kwargM>]

    Return:
        (args, kwargs)
    """
    args = []
    kwargs = {}
    skip_next = False
    mod = importlib.import_module(def_mod) 
    parsed_cmd = parse_line(line)
    if len(parsed_cmd) < 4:
        error('usage: <node> <start> <duration> <exe> [<arg1>] ... [<argN>] [--mod <module>] [--<key1> <kwarg1>] ... [--<keyM> <kwargM>]\n')
    for i in range(len(parsed_cmd)):
        if skip_next:
            skip_next = False
            continue
        # Parse node (index 0 in args)
        if i == 0:
            args.append(parsed_cmd[i])
        # Parse start
        elif i == 1:
            kwargs['start'] = float(parsed_cmd[i])
        # Parse duration
        elif i == 2:
            kwargs['duration'] = float(parsed_cmd[i])
        # Parse exe (index 1 in args)
        elif i == 3:
            args.append(parsed_cmd[i])
        # Parse args and kwargs
        elif i >= 4:
            # Parse kwargs
            if len(parsed_cmd[i]) > 2 and parsed_cmd[i][:2] == '--':
                # Parse module
                if parsed_cmd[i] == '--mod':
                    mod = importlib.import_module(parsed_cmd[i+1])
                else:
                    kwargs[parsed_cmd[i][2:]] = parsed_cmd[i+1]
                skip_next = True
            # Parse args
            else:
                args.append(parsed_cmd[i])
    
    try:
        # Import function from module
        exe = getattr(mod, args[1])
        # Set function as the executable
        args[1] = exe
    except AttributeError:
        # Interpret the executable as a command
        pass

    return args, kwargs
