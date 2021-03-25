import networkx as nx
from ipaddress import ip_interface
from networkx.classes.graph import Graph
from networkx.classes.function import neighbors
from networkx.classes.reportviews import NodeView

class NodeDoesNotExist(Exception):

    def __init__(self, node):
        self.message = 'Node <{}> does not exist'.format(node)
        super().__init__('NodeDoesNotExist: {}'.format(self.message))

    def __str__(self):
        return self.message

class IntfDoesNotExist(Exception):

    def __init__(self, intf, node):
        self.message = 'Interface <{}> does not exist on node <{}>'.format(intf, node)
        super().__init__('IntfDoesNotExist: {}'.format(self.message))

    def __str__(self):
        return self.message

class NetworkGraph(Graph):
    """
    An extension to networkx.classes.Graph which allows querying
    network information and loads the topology from the JSON file
    generated during the execution of p4run. The basic methods
    used to manage nodes are available on the NetworkX documentation
    webpage (https://networkx.org/documentation/stable/index.html) 
    since this class inherits from it.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the Graph."""
        super().__init__(*args, **kwargs)
        self.edge_to_intf = {}          # Stores interface1 dict indexed by [node1][node2]
        self.node_to_intf = {}          # Stores interface1 dict indexed by [node][intfName]
        self._populate_dicts()

    def _populate_dicts(self):
        """
        Populate dicts self.intf_to_edge, self.edge_to_intfs and self.node_to_edges
        to speedup searches.
        """
        for node in self.nodes:
            self.edge_to_intf[node] = {}
            self.node_to_intf[node] = {}

        for node in self.nodes:
            for neighbor in neighbors(self, node):
                self.edge_to_intf[node][neighbor] = self._edge_to_intf(node, neighbor)
                self.edge_to_intf[neighbor][node] = self._edge_to_intf(neighbor, node)
                self.node_to_intf[node][self.edge_to_intf[node][neighbor]['intfName']] = self.edge_to_intf[node][neighbor]
                self.node_to_intf[neighbor][self.edge_to_intf[neighbor][node]['intfName']] = self.edge_to_intf[neighbor][node]

    def _edge_to_intf(self, node1, node2):
        """
        Returns interface information of node1 facing node2.
        """
        link = self.edges[(node1, node2)]
        intf = {}
        # Get information about node1
        if node1 == link['node1'] and node2 == link['node2']:
            for key, value in link.items():
                if '2' not in key:
                    intf[key.replace('1','')] = value

        # Get information about node2
        else:
            for key, value in link.items():
                if '1' not in key:
                    intf[key.replace('2','')] = value
        return intf

    @property
    def switches(self):
        """
        A NodeView of the Graph as G.switches or G.switches().
        Can be used as `G.switches` for data lookup and for set-like operations.
        Can also be used as `G.switches(data='color', default=None)` to return a
        NodeDataView which reports specific node data but no set operations.
        It presents a dict-like interface as well with `G.switches.items()`
        iterating over `(node, nodedata)` 2-tuples and `G.switches[3]['foo']`
        providing the value of the `foo` attribute for node `3`. In addition,
        a view `G.switches.data('foo')` provides a dict-like interface to the
        `foo` attribute of each node. `G.switches.data('foo', default=1)`
        provides a default for switches that do not have attribute `foo`.
        """
        switches_subgraph = nx.subgraph_view(self, filter_node=self.isSwitch)
        switches = NodeView(switches_subgraph)
        self.__dict__['switches'] = switches
        return switches

    @property
    def p4switches(self):
        """
        A NodeView of the Graph as G.switches or G.switches().
        Can be used as `G.switches` for data lookup and for set-like operations.
        Can also be used as `G.switches(data='color', default=None)` to return a
        NodeDataView which reports specific node data but no set operations.
        It presents a dict-like interface as well with `G.switches.items()`
        iterating over `(node, nodedata)` 2-tuples and `G.switches[3]['foo']`
        providing the value of the `foo` attribute for node `3`. In addition,
        a view `G.switches.data('foo')` provides a dict-like interface to the
        `foo` attribute of each node. `G.switches.data('foo', default=1)`
        provides a default for switches that do not have attribute `foo`.
        """
        p4switches_subgraph = nx.subgraph_view(self, filter_node=self.isP4Switch)
        p4switches = NodeView(p4switches_subgraph)
        self.__dict__['switches'] = p4switches
        return p4switches

    @property
    def p4rntswitches(self):
        """
        A NodeView of the Graph as G.switches or G.switches().
        Can be used as `G.switches` for data lookup and for set-like operations.
        Can also be used as `G.switches(data='color', default=None)` to return a
        NodeDataView which reports specific node data but no set operations.
        It presents a dict-like interface as well with `G.switches.items()`
        iterating over `(node, nodedata)` 2-tuples and `G.switches[3]['foo']`
        providing the value of the `foo` attribute for node `3`. In addition,
        a view `G.switches.data('foo')` provides a dict-like interface to the
        `foo` attribute of each node. `G.switches.data('foo', default=1)`
        provides a default for switches that do not have attribute `foo`.
        """
        p4rntswitches_subgraph = nx.subgraph_view(self, filter_node=self.isP4RuntimeSwitch)
        p4rntswitches = NodeView(p4rntswitches_subgraph)
        self.__dict__['switches'] = p4rntswitches
        return p4rntswitches

    @property
    def hosts(self):
        """
        A NodeView of the Graph as G.hosts or G.hosts().
        Can be used as `G.hosts` for data lookup and for set-like operations.
        Can also be used as `G.hosts(data='color', default=None)` to return a
        NodeDataView which reports specific node data but no set operations.
        It presents a dict-like interface as well with `G.hosts.items()`
        iterating over `(node, nodedata)` 2-tuples and `G.hosts[3]['foo']`
        providing the value of the `foo` attribute for node `3`. In addition,
        a view `G.hosts.data('foo')` provides a dict-like interface to the
        `foo` attribute of each node. `G.hosts.data('foo', default=1)`
        provides a default for hosts that do not have attribute `foo`.
        """
        hosts_subgraph = nx.subgraph_view(self, filter_node=self.isHost)
        hosts = NodeView(hosts_subgraph)
        self.__dict__['hosts'] = hosts
        return hosts

    def isHost(self, node):
        """Return True if the node is a host."""
        return self.nodes[node].get('isHost', False)

    def isSwitch(self, node):
        """Return True if the node is a switch."""
        return self.nodes[node].get('isSwitch', False)

    def isP4Switch(self, node):
        """Return True if the node is a P4 switch."""
        return self.nodes[node].get('isP4Switch', False)

    def isP4RuntimeSwitch(self, node):
        """Return True if the node is a P4 runtime switch."""
        return self.nodes[node].get('isP4RuntimeSwitch', False)

    def _interface(self, node1, node2):
        """Returns interface information of node1 facing node2."""
        try:
            intfs = self.edge_to_intf[node1]
        except KeyError:
            raise NodeDoesNotExist(node1)
        try:
            return intfs[node2]
        except KeyError:
            raise NodeDoesNotExist(node2)

    def _node_interface(self, node, intf):
        """Returns interface information of node1's interface intf."""
        try:
            intfs = self.node_to_intf[node]
        except KeyError:
            raise NodeDoesNotExist(node)
        try:
            return intfs[intf]
        except KeyError:
            raise IntfDoesNotExist(intf, node)

    def node_to_node_interface_ip(self, node1, node2):
        """Return the ip_interface for node1 facing node2."""
        return self._interface(node1, node2).get('ip', None)

    def node_to_node_interface_bw(self, node1, node2):
        """
        Return the bandwidth capacity of the interface on node1 facing node2.
        If it is unlimited, return -1.
        """
        if self._interface(node1, node2).get('bw', None) is None:
            return -1
        else:
            return self._interface(node1, node2)['bw']
    
    def node_interface_ip(self, node, intf):
        """Returns the IP address of a given interface and node."""
        ip = self._node_interface(node, intf).get('ip', None)
        if ip is not None:
            return ip.split("/")[0]
        else:
            return None

    def node_interface_bw(self, node, intf):
        """Returns the bw of a given interface and node."""
        if self._node_interface(node, intf).get('bw', None) is None:
            return -1
        else:
            return self._node_interface(node, intf)['bw']

    def subnet(self, node1, node2):
        """Return the subnet linking node1 and node2."""
        ip = self.node_to_node_interface_ip(node1, node2)
        if ip is not None:
            return ip_interface(ip).network.with_prefixlen
        else:
            return None

    def get_neighbors(self, node):
        """Returns node's neighbors (all of them)."""
        return list(neighbors(self, node))

    def get_interfaces(self, node):
        """Returns node's interfaces names."""
        return list(self.node_to_intf[node].keys())

### Up to topology.py line 250