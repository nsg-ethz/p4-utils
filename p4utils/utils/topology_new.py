import networkx as nx
from networkx.classes.graph import Graph
from networkx.classes.reportviews import NodeView

class NetworkGraph(Graph):
    """
    An extension to networkx.classes.Graph which allows querying
    network information and loads the topology from the JSON file
    generated during the execution of p4run. The basic methods
    used to manage nodes are available on the NetworkX documentation
    webpage (https://networkx.org/documentation/stable/index.html) 
    since this class inherits from it.
    """

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
        return self.nodes[node].get('isHost',False)

    def isSwitch(self, node):
        """Return True if the node is a switch."""
        return self.nodes[node].get('isSwitch', False)

    def isP4Switch(self, node):
        """Return True if the node is a P4 switch."""
        return self.nodes[node].get('isP4Switch', False)

    def isP4RuntimeSwitch(self, node):
        """Return True if the node is a P4 runtime switch."""
        return self.nodes[node].get('isP4RuntimeSwitch', False)
    
    def interface(self, node1, node2):
        """Returns interface information of node1 facing node2"""
        link = self.edges[(node1, node2)]
        intf = {}
        # Get information about node1
        if node1 == link['node1'] and node2 == link['node2']:
            for key, value in link:
                if '2' not in key:
                    intf[key] = value
        # Get information about node2
        else:
            for key, value in link:
                if '1' not in key:
                    intf[key] = value
        return intf

