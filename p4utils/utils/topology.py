import copy
import json
import pprint

import networkx as nx
from ipaddress import ip_interface

from p4utils import NodeDoesNotExist, InvalidHostIP
from p4utils.logger import log


class TopologyDB(object):
    """
    Topology API to save mininet topologies and load them to query useful information.

    dict keyed by node name ->
        dict keyed by - properties -> val
                      - neighbor   -> interface properties

    Attributes:
        db: path to network database object. This attribute is used when loading the database.
        net: mininet object. When present, TopologyDB saves it in a json format to the disk
    """

    def __init__(self, db=None, net=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._network = {}
        if net:
            self.topo = net.topo
            self.parse_net(net)
        elif db:
            self.load(db)
        else:
            log.warning('Topology instantiated without any data')

    def __iter__(self):
        """Enables iteration on this object"""
        return iter(self._network)

    def __repr__(self):
        """Transforms the object into a string when printed"""
        return pprint.pformat(self._network)

    def __getitem__(self, item):
        """Items can be accessed by using []"""
        return self._node(item)

    def __contains__(self, item):
        """Enables X in Self"""
        return item in self._network

    def load(self, fpath):
        """
        Load a topology database from the given filename.

        Args:
            fpath: path to json file
        """
        with open(fpath, 'r') as f:
            self._network = json.load(f)

    def save(self, fpath):
        """
        Save the topology database to the given filename.

        Args:
            fpath: path to json file
        """
        with open(fpath, 'w') as f:
            json.dump(self._network, f)

    @staticmethod
    def other_intf(intf):
        """Get the interface on the other end of a link."""
        link = intf.link
        if link:
            if link.intf2 == intf:
                return link.intf1
            else:
                return link.intf2
        else:
            return None

    def parse_net(self, net):
        """Stores the content of the given network in the TopologyDB object."""

        for host in net.hosts:
            self.add_host(host)
        for controller in net.controllers:
            self.add_controller(controller)
        for switch in net.switches:
            if net.topo.isP4Switch(switch.name):
                self.add_p4switch(switch)
            else:
                self.add_switch(switch)

    def _add_node(self, node, props):
        """Register a network node.

        Args:
            node: mininet.node.Node object
            props: properties (dictionary)
        """

        if node.params.get('isHiddenNode', False):
            return

        interfaces_to_nodes = {}
        interfaces_to_port = {}

        for port, port_id in node.ports.items():
            interfaces_to_port[port.name] = port_id

        for itf in node.intfList():
            nh = TopologyDB.other_intf(itf)
            if not nh:
                continue  # Skip loopback and the likes

            # do not create connection to hidden node in topology
            if nh.node.params.get('isHiddenNode', False):
                continue

            props[nh.node.name] = {
                'ip': '%s/%s' % (itf.ip, itf.prefixLen),
                'mac': '%s' % (itf.mac),
                'intf': itf.name,
                'bw': itf.params.get('bw', -1),
                'loss': itf.params.get('loss', 0),
                'weight': itf.params.get('weight', 1),
                'delay': itf.params.get('delay', 0),
                'queue_length': itf.params.get('max_queue_size', -1)
            }
            interfaces_to_nodes[itf.name] = nh.node.name

        # add an interface to node mapping
        props['interfaces_to_node'] = interfaces_to_nodes
        props['interfaces_to_port'] = interfaces_to_port
        self._network[node.name] = props

    def add_host(self, node):
        """Register a host."""
        attributes = {'type': 'host'}
        # node.gateway attribute only exists in my custom mininet

        if hasattr(node, "gateway"):
            attributes.update({'gateway': node.gateway})
        elif 'defaultRoute' in node.params:
            attributes.update({'gateway': node.params['defaultRoute'].replace("via ", "")})
        self._add_node(node, attributes)

    def add_controller(self, node):
        """Register a controller."""
        self._add_node(node, {'type': 'controller'})

    def add_switch(self, node):
        """Register a switch."""
        self._add_node(node, {'type': 'switch'})

    def _node(self, node):
        """
        Returns node's information

        Args:
            node: node's name
        Raises:
            NodeDoesNotExist: if node's name does not exist in the topology
        """
        try:
            return self._network[node]
        except KeyError:
            raise NodeDoesNotExist(node)

    def node(self, node):
        """
        Public version of _node

        Args:
            node: nodes'name

        Returns: Node if exists
        """
        return self._node(node)

    def _interface(self, node1, node2):
        """Returns interface information of node1 facing node2"""

        # this functions checks if node 2 exists, if not raises exeption.
        self._node(node2)
        return self._node(node1)[node2]

    def _node_interface(self, node, intf):
        """Returns interface information of node1's interface intf"""

        connected_to = self._node(node)["interfaces_to_node"][intf]
        return self._interface(node, connected_to)

    def node_to_node_interface_ip(self, node1, node2):
        """Return the ip_interface for node1 facing node2."""

        return self._interface(node1, node2)['ip']

    def node_to_node_interface_bw(self, node1, node2):
        """Return the bandwidth capacity of the interface on node1 facing node2.
        If it is unlimited, return -1."""

        # checks if they exist
        self._node(node2)
        return self._interface(node1, node2)['bw']

    def node_interface_ip(self, node, intf):
        """Returns the IP address of a given interface and node."""
        return self._node_interface(node, intf)['ip'].split("/")[0]

    def node_interface_bw(self, node, intf):
        """Returns the bw of a given interface and node"""
        return self._node_interface(node, intf)['bw']

    def subnet(self, node1, node2):
        """Return the subnet linking node1 and node2."""
        return ip_interface(self.node_to_node_interface_ip(node1, node2)).network.with_prefixlen

    def get_node_type(self, node):
        """Returns node's type"""
        return self._node(node)['type']

    def get_neighbors(self, node):
        """Returns node's neighbors (all of them)"""
        return list(self._node(node)["interfaces_to_node"].values())

    def get_interfaces(self, node):
        """Returns node's interfaces names"""
        return list(self._node(node)["interfaces_to_node"].keys())

class TopologyDBP4(TopologyDB):
    """See base class.

    Adds some special methods for P4 switches.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_p4switch(self, node):
        """Adds P4 Switch node."""

        # set fake ips so they can be queried with the topo
        for intf in node.intfList():
            if intf.name == "lo":
                continue
            if intf.params.get('sw_ip', None):
                intf.ip, intf.prefixLen = intf.params['sw_ip'].split("/")

        self._add_node(node, {'type': 'switch', 'subtype': 'p4switch',
                              'thrift_port': node.thrift_port, 'sw_id': node.device_id})

        # clean the IPs, this seems to make no sense, but when the p4switch is
        # started again, if the interface has an IP, the interface is not added
        # There are two options, remove that check, or clear the IP after creating
        # the object.

        for intf in node.intfList():
            if intf.name == "lo":
                continue
            intf.ip, intf.prefixLen = None, None

    def get_cpu_port_intf(self, p4switch, quiet=False):
        """
        Returns the port index of p4switch's cpu port

        Args:
            p4switch: name of the p4 switch
            cpu_node: name of the cpu-node (usually a bridge)

        Returns: index
        """
        has_cpu_port = any('cpu' in x for x in list(self[p4switch]['interfaces_to_port'].keys()))
        if self.is_p4switch(p4switch) and has_cpu_port:
            return [x for x in list(self[p4switch]['interfaces_to_port'].keys()) if 'cpu' in x][0]
        else:
            if not quiet:
                print(("Switch %s has no cpu port" % p4switch))
            return None

    def get_cpu_port_index(self, p4switch, quiet=False):
        """
        Returns the port index of p4switch's cpu port
        Args:
            p4switch: name of the p4 switch

        Returns: index
        """
        has_cpu_port = any('cpu' in x for x in list(self[p4switch]['interfaces_to_port'].keys()))
        if self.is_p4switch(p4switch) and has_cpu_port:
            intf = self.get_cpu_port_intf(p4switch)
            return self[p4switch]['interfaces_to_port'][intf]
        else:
            if not quiet:
                print(("Switch %s has no cpu port" % p4switch))
            return None

    def get_thrift_port(self, switch):
        """Return the Thrift port used to communicate with the P4 switch."""
        if self._node(switch).get('subtype', None) != 'p4switch':
            raise TypeError('%s is not a P4 switch' % switch)
        return self._node(switch)['thrift_port']


    def get_thrift_ip(self, switch):
        """Return the Thrift ip used to communicate with the P4 switch."""
        if self._node(switch).get('subtype', None) != 'p4switch':
            raise TypeError('%s is not a P4 switch' % switch)
        return self._node(switch)['thrift_ip']

    def get_ctl_cpu_intf(self, switch):
        """Returns the controller side cpu interface used to listent for cpu packets"""
        if self._node(switch).get('subtype', None) != 'p4switch':
            raise TypeError('%s is not a P4 switch' % switch)
        
        if self._node(switch).get('ctl_cpu_intf', None):
            return self._node(switch)['ctl_cpu_intf']
        else:
            return self.get_cpu_port_intf(switch)

class Topology(TopologyDBP4):
    """
    Builds or loads a topology object from a mininet or properly json file.

    The topology object provides an API to query information about the mininet topology

    Attributes:
        db: json file describint the topology. The file had to be saved using this same class but using a mininet object.

    """

    def __init__(self, db="topology.db", *args, **kwargs):
        super().__init__(db, *args, **kwargs)

        # Save network startup state:
        # In case of link removal, we use this objects to remember the state of links and nodes
        # before the removal. This assumes that the topology will not be enhanced, i.e., links and
        # nodes can be removed and added, but new links or devices cannot be added.

        self._original_network = copy.deepcopy(self._network)
        self.network_graph = NetworkGraph()
        # this was separated so the Graph constructors has no parameters. Otherwise it would
        # fail when creating SubGraphs. This happens since networkx 2.x
        self.network_graph.load_topology_from_database(self)

        # Creates hosts to IP and IP to hosts mappings
        self.hosts_ip_mapping = {}
        self.create_hosts_ip_mapping()

    def create_hosts_ip_mapping(self):
        """Creates a mapping between host names and IP addresses, and vice versa."""
        self.hosts_ip_mapping = {}
        hosts = self.get_hosts()
        self.hosts_ip_mapping["ipToName"] = {}
        self.hosts_ip_mapping["nameToIp"] = {}
        for host in hosts:
            ip = self.node_interface_ip(host, self.get_host_first_interface(host).format(host))
            self.hosts_ip_mapping["ipToName"][ip] = host
            self.hosts_ip_mapping["nameToIp"][host] = ip

    def get_host_name(self, ip):
        """Returns the host name to an IP address.

        Args:
            ip: host's ip
        """
        name = self.hosts_ip_mapping.get("ipToName", {}).get(ip, None)
        if name:
            return name
        raise InvalidHostIP(ip)

    def get_host_gateway_name(self, host):
        """Get host gateway name"""

        if self.is_host(host):
            return self[host]["interfaces_to_node"][self.get_host_first_interface(host)]

    def get_host_ip(self, name):
        """Returns the IP to a host name.

        Args:
            name: host's name
        """
        ip = self.hosts_ip_mapping.get("nameToIp", {}).get(name, None)
        if ip:
            return ip
        raise NodeDoesNotExist(name)

    def get_host_mac(self, name):
        """Returns the mac to a host name

        Args:
            name: host's name
        """
        intf = self.get_host_first_interface(name)
        nhop = self.get_interfaces_to_node(name)[intf]
        return self[name][nhop]['mac']

    def is_router(self, node):
        """Checks if node is a router.

        Args:
            node: name of router

        Returns:
            True if node is a router, False otherwise
        """
        return self[node]["type"] == "router"


    def is_host(self, node):
        """Checks if node is a host.

        Args:
            node: name of Mininet node

        Returns:
            True if node is a host, False otherwise
        """
        return self[node]["type"] == "host"

    def is_switch(self, node):
        """Checks if node is a switch.

        Args:
            node: name of Mininet node

        Returns:
            True if node is a switch, False otherwise
        """
        return self[node]["type"] == "switch"

    def is_p4switch(self, node):
        """Checks if node is a P4 switch.

        Args:
            node: name of Mininet node

        Returns:
            True if node is a P4 switch, False otherwise
        """
        return self[node]["type"] == "switch" and self[node].get('subtype', None) == 'p4switch'

    def get_hosts(self):
        """Returns the hosts from the topologyDB."""
        return {node: self[node] for node in self if self.is_host(node)}

    def get_switches(self):
        """Returns the switches from the topologyDB."""
        return {node: self[node] for node in self if self.is_switch(node)}

    def get_p4switches(self):
        """Returns the P4 switches from the topologyDB."""
        return {node: self[node] for node in self if self.is_p4switch(node)}

    def get_routers(self):
        """Returns the routers from the topologyDB."""
        return {node: self[node] for node in self if self.is_router(node)}


    def get_host_first_interface(self, name):
        """Returns the first interface from a host. Assume it's single-homed.

        Args:
            name: host name

        Returns:
            interface name (str)
        """
        return list(self[name]["interfaces_to_node"].keys())[0]

    def get_p4switch_id(self, sw_name):
        """Returns the ID of a P4 switch.

        Args:
            sw_name: P4 switch name in the topology
        Raises:
            TypeError if sw_name is not a P4 switch
        Returns:
            ID of P4 switch as a string
        """
        if self[sw_name].get('subtype', None) != 'p4switch':
            raise TypeError('%s is not a P4 switch' % sw_name)
        return self[sw_name]['sw_id']

    def are_neighbors(self, node1, node2):
        """
        Returns if two nodes are direct neighbors

        Args:
            node1: first node
            node2: second node

        Returns:

        """
        return self.network_graph.are_neighbors(node1, node2)

    def get_hosts_connected_to(self, node):
        """
        Returns the hosts directly connected to the node

        Args:
            node:

        Returns: list of hosts

        """
        nodes = self.get_neighbors(node)
        return [host for host in nodes if self.get_node_type(host) == 'host']

    def get_switches_connected_to(self, node):
        """
        Returns the switches directly connected to the node

        Args:
            node:

        Returns: list of switches

        """
        nodes = self.get_neighbors(node)
        return [host for host in nodes if self.is_p4switch(host)]


    def get_routers_connected_to(self, node):
        """
        Returns the routers directly connected to the node

        Args:
            node:

        Returns: list of routers

        """
        nodes = self.get_neighbors(node)
        return [host for host in nodes if self.is_router(host)]


    def get_direct_host_networks_from_switch(self, switch):
        """
        Returns all the subnetworks a switch can reach directly

        Args:
            switch: switch name

        Returns: Returns set of networks

        """
        networks = []
        hosts = self.get_hosts_connected_to(switch)
        for host in hosts:
            sub_nets = [self.subnet(host, neighbor) for neighbor in list(self[host]['interfaces_to_node'].values())]
            networks += sub_nets
        return set(networks)

    def get_interfaces_to_node(self, node):
        """
        Returns dictionary with all interface_name -> node

        Args:
            node: node's name
        """
        return self[node]['interfaces_to_node']

    def get_interfaces_to_port(self, node):
        """
        Returns dictionary with all interface_name -> port_num
        Args:
            node: node's name
        """
        return self[node]['interfaces_to_port']

    def interface_to_node(self, node, intf):
        """
        Returns name of the neigbor at node[intf]

        Args:
            node: node we are quering
            intf: name of the interface
        """
        return self[node]['interfaces_to_node'][intf]

    def interface_to_port(self, node, intf):
        """
        Returns port number of the node[intf]

        Args:
            node: node we are quering
            intf: name of the interface
        """
        return self[node]['interfaces_to_port'][intf]

    def node_to_node_port_num(self, node1, node2):
        """
        Returns the port number from node1 point of view that connects to node2

        Args:
            node1: src node
            node2: dst node
        """
        intf = self[node1][node2]['intf']
        return self.interface_to_port(node1, intf)

    def node_to_node_mac(self, node1, node2):
        """
        Returns mac address of node1's interface facing node2
        Args:
            node1: src node
            node2: dst node
        """
        return self[node1][node2]['mac']

    def get_shortest_paths_between_nodes(self, node1, node2):
        """
        Returns all the shortest paths between node1 and node2
        Args:
            node1: src node
            node2: dst node

        Returns: List of shortests paths

        """
        return self.network_graph.get_paths_between_nodes(node1, node2)

    def get_all_paths_between_nodes(self, node1, node2):
        """
        Returns all the paths between node1 and node2
        Args:
            node1: src node
            node2: dst node

        Returns: List of shortests paths

        """        
        return self.network_graph.get_all_paths_between_nodes(node1, node2)




class NetworkGraph(nx.Graph):
    """
    Uses a networkx object as a base to load the topology.

    This object is used to get useful information about the topology
    using networkx useful graph algorithms. For instance we can easily
    get short paths between two nodes.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.node = {}

    def load_topology_from_database(self, topology_db):
        self.topology_db = topology_db
        self.load_graph_from_db()

    def load_graph_from_db(self):
        """Loads networkx object from topologyDB"""
        for node, attributes in self.topology_db._original_network.items():
            if node not in self.nodes():
                self.add_node(node, attributes)

    def add_edge(self, node1, node2):
        """Connects node1 and node2 using an edge"""
        if node1 in self.node and node2 in self.node:
            super(NetworkGraph, self).add_edge(node1, node2)

    def add_node(self, node, attributes):
        """
        Adds node and connects it with all its neighbors.

        Args:
            node: node's name
            attributes: node's attributes
        """
        super(NetworkGraph, self).add_node(node)
        self.node[node] = {'type' : self.topology_db.get_node_type(node)}
        # check if the node has a subtype
        subtype = attributes.get('subtype', None)
        if subtype:
            self.node[node] = {'subtype': subtype}

        for neighbor_node in self.topology_db.get_neighbors(node):
            if neighbor_node in self.nodes():
                weight = attributes[neighbor_node].get("weight", 1)
                bw = attributes[neighbor_node].get("bw", 1000)
                super(NetworkGraph, self).add_edge(node, neighbor_node, weight=weight, bw=bw)

    def set_node_shape(self, node, shape):
        """Sets node's shape. Used when plotting the network"""
        self.node[node] = {'node_shape': shape}

    def set_node_color(self, node, color):
        """Sets node's color. Used when plotting the network"""
        self.node[node] = {'node_color': color}

    def set_node_type_shape(self, type, shape):
        """Sets all node's with a given type shape. Used when plotting the network"""
        for node in self.node:
            if self.node[node]['type'] == type:
                self.set_node_shape(node, shape)

    def set_node_type_color(self, type, color):
        """Sets all node's with a given type color. Used when plotting the network"""
        for node in self.node:
            if self.node[node]['type'] == type:
                self.set_node_color(node, color)

    def get_hosts(self):
        """Returns all the nodes that are hosts"""
        return [x for x in self.node if self.node[x]['type'] == 'host']

    def get_switches(self):
        """Returns all the nodes that are switches"""
        return [x for x in self.node if self.node[x]["type"] == "switch"]

    def get_routers(self):
        """Returns all the nodes that are routers"""
        return [x for x in self.node if self.node[x]["type"] == "router"]        

    def get_p4switches(self):
        """Returns all the nodes that are P4 switches"""
        return [x for x in self.node if
                self.node[x]['type'] == "switch" and self.node[x].get('subtype', "") == 'p4switch']

    def keep_only_switches(self):
        """Returns a networkx subgraph including only switch nodes"""
        return self.subgraph(self.get_switches())

    def keep_only_p4switches(self):
        """Returns a networkx subgraph including only P4 switch nodes"""
        return self.subgraph(self.get_p4switches())

    def keep_only_p4switches_and_hosts(self):
        """Returns a networkx subgraph including only hosts and P4 switch nodes"""
        return self.subgraph(self.get_p4switches() + self.get_hosts())

    def are_neighbors(self, node1, node2):
        """Returns True if node1 and node2 are neighbors, False otherwise."""
        return node1 in self.adj[node2]

    def get_neighbors(self, node):
        """Return all neighbors for a given node."""
        return list(self.adj[node].keys())

    def total_number_of_paths(self):
        """Returns the total number of shortests paths between all host pairs in the network"""
        total_paths = 0
        for host in self.get_hosts():
            for host_pair in self.get_hosts():
                if host == host_pair:
                    continue

                # compute the number of paths
                npaths = sum(1 for _ in nx.all_shortest_paths(self, host, host_pair, 'weight'))
                total_paths += npaths

        return total_paths

    def get_paths_between_nodes(self, node1, node2):
        """Compute the paths between two nodes."""
        paths = nx.all_shortest_paths(self, node1, node2, 'weight')
        paths = [tuple(x) for x in paths]
        return paths

    def get_all_paths_between_nodes(self, node1, node2):
        """Compute all the paths between two nodes."""
        paths = nx.shortest_simple_paths(self, node1, node2, 'weight')
        paths = [tuple(x) for x in paths]
        return paths

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        db = sys.argv[1]
    else:
        db = "./topology.db"

    topo = Topology(db=db)