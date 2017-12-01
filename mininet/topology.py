import json
from ipaddress import ip_interface
from minigenerator.logger import log
from . import InvalidIP, HostDoesNotExist
import networkx as nx
import copy
import pprint

class TopologyDB(object):
    """A convenience storage for auto-allocated mininet properties.

    Based on Olivie Tilmans TopologyDB from fibbing project:
    https://github.com/Fibbing/FibbingNode/blob/master/fibbingnode/misc/mininetlib/ipnet.py
    """
    def __init__(self, db=None, net=None, *args, **kwargs):
        super(TopologyDB, self).__init__(*args, **kwargs)
        """
        dict keyed by node name ->
            dict keyed by - properties -> val
                          - neighbor   -> interface properties
        """
        self._network = {}

        if net:
            self.parse_net(net)

        elif db:
            self.load(db)

        else:
            log.warning('Topology instantiated without any data')

    def __iter__(self):
        return self._network.iteritems()

    def __repr__(self):
        return pprint.pformat(self._network)

    def load(self, fpath):
        """Load a topology database from the given filename."""
        with open(fpath, 'r') as f:
            self._network = json.load(f)

    def save(self, fpath):
        """Save the topology database to the given filename."""
        with open(fpath, 'w') as f:
            json.dump(self._network, f)

    def _node(self, node):
        try:
            return self._network[node]
        except KeyError:
            raise ValueError('No node named %s in the network' % node)

    def __getitem__(self, item):
        return self._node(item)

    def _interface(self, x, y):
        return self._network[x][y]

    def interface(self, x, y):
        """Return the ip_interface for node x facing node y."""
        return ip_interface(self._interface(x, y)['ip'])

    def interface_bandwidth(self, x, y):
        """Return the bandwidth capacity of the interface on node x facing node y.
        If it is unlimited, return -1."""
        connected_to = self._network[x]["interfaces_to_node"][y]
        return self._interface(x, connected_to)['bw']

    def subnet(self, x, y):
        """Return the subnet linking node x and y."""
        return self.interface(x, y).network.with_prefixlen

    def set_router_id(self, x):
        """Return the OSPF router id for node named x."""
        router = self._network[x]
        if router['type'] != 'router':
            raise TypeError('%s is not a router' % x)

        return router.get('routerid')

    def get_router_id(self, x):
        router = self._network[x]
        if router['type'] != 'router':
            raise TypeError('%s is not a router' % x)

        return router['routerid']

    def interface_ip(self, node, interface):
        """Returns the IP address of a given interface and node.

        :param node:
        :param interface:
        :return:
        """
        connected_to = self._network[node]["interfaces_to_node"][interface]
        return self._interface(node, connected_to)['ip'].split("/")[0]

    def type(self, node):
        return self._network[node]['type']

    def get_neighbors(self, node):
        return self._network[node]["interfaces_to_node"].itervalues()

    def interfaces(self, node):
        return self._network[node]["interfaces_to_node"].iterkeys()

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
        for switch in net.switches:
            self.add_switch(switch)
        if hasattr(net, "routers"):
            for router in net.routers:
                self.add_router(router)
        for controller in net.controllers:
            self.add_controller(controller)

    def _add_node(self, n, props):
        """Register a network node."""
        # does not add nodes that have inTopology set to false
        if 'inTopology' in n.params:
            if not n.params['inTopology']:
                return

        interfaces_to_nodes = {}
        interfaces_to_port = {}

        for port, port_id in n.ports.iteritems():
            interfaces_to_port[port.name] = port_id

        for itf in n.intfList():
            nh = TopologyDB.other_intf(itf)
            if not nh:
                continue  # Skip loopback and the likes

            # do not create connection
            if 'inTopology' in nh.node.params:
                # import ipdb
                # ipdb.set_trace()
                if not nh.node.params['inTopology']:
                    continue

            props[nh.node.name] = {
                'ip': '%s/%s' % (itf.ip, itf.prefixLen),
                'mac' : '%s' % (itf.mac),
                'intf': itf.name,
                'bw': itf.params.get('bw', -1)
            }
            interfaces_to_nodes[itf.name] = nh.node.name
        # add an interface to node mapping that can be useful
        props['interfaces_to_node'] = interfaces_to_nodes
        props['interfaces_to_port'] = interfaces_to_port
        self._network[n.name] = props

    def add_host(self, n):
        """Register a host."""
        attributes = {'type': 'host'}
        # n.gateway attribute only exists in my custom mininet
        if hasattr(n, "gateway"):
            attributes.update({'gateway': n.gateway})
        elif 'defaultRoute' in n.params:
            attributes.update({'gateway': n.params['defaultRoute']})
        self._add_node(n, attributes)

    def add_controller(self, n):
        """Register a controller."""
        self._add_node(n, {'type': 'controller'})

    def add_switch(self, n):
        """Register a switch."""
        self._add_node(n, {'type': 'switch'})

    def add_router(self, n):
        """Register a router."""
        self._add_node(n, {'type': 'router',
                           'routerid': n.id})
        # We overwrite the router id using our own function.
        self._network[n.name]["routerid"] = self.set_router_id(n.name)


# TODO: Check what can be reused.
class NetworkGraph(object):
    def __init__(self, topologyDB):
        self.topologyDB = topologyDB
        self.graph = self.load_graph_from_db(self.topologyDB)

    def load_graph_from_db(self, topologyDB):
        g = nx.Graph()

        for node, attributes in topologyDB._original_network.iteritems():
            if node not in g.nodes():
                g.add_node(node)
                g.node[node]['type'] = topologyDB.type(node)

                for neighbor in topologyDB.get_neighbors(node):
                    if neighbor in g.nodes():
                        g.add_edge(node, neighbor)
        return g

    def add_edge(self, node1, node2):
        if node1 in self.graph.node and node2 in self.graph.node:
            self.graph.add_edge(node1, node2)

    def add_node(self, node):
        self.graph.add_node(node)
        self.graph.node[node]['type'] = self.topologyDB.type(["type"])

        for neighbor_node in self.topologyDB.get_neighbors(node):

            if neighbor_node in self.graph.node:
                self.graph.add_edge(node, neighbor_node)

    def remove_node(self, node):
        self.graph.remove_node(node)

    def remove_edge(self, node1, node2):
        self.graph.remove_edge(node1, node2)

    def keep_only_routers(self):
        to_keep = [x for x in self.graph.node if self.graph.node[x]['type'] == 'router']
        return self.graph.subgraph(to_keep)

    def setNodeShape(self, node, shape):
        self.graph.node[node]['node_shape'] = shape

    def setNodeColor(self, node, color):
        self.graph.node[node]['node_color'] = color

    def setNodeTypeShape(self, type, shape):
        for node in self.graph.node:
            if self.graph.node[node]['type'] == type:
                self.setNodeShape(node, shape)

    def setNodeTypeColor(self, type, color):
        for node in self.graph.node:
            if self.graph.node[node]['type'] == type:
                self.setNodeColor(node, color)

    def setEdgeWeights(self, link_loads={}):
        pass

    def getHosts(self):
        return [x for x in self.graph.node if self.graph.node[x]['type'] == 'host']

    def getRouters(self):
        return [x for x in self.graph.node if self.graph.node[x]["type"] == "router"]

    def areNeighbors(self, n1, n2):
        return n1 in self.graph.adj[n2]

    def get_neighbors(self, node):
        return self.graph.adj[node].keys()

    def total_number_of_paths(self):
        """This function is very useful if the topology is unknown, however if we are using a fat tree, the number of paths is more or less
        (k/2**2) = number of paths from one node to another node that its not in the same pod
        number of nodes its k**3 / 4
        so number of paths is : (k/2**2) * (k**3)/4 - k**2/4)(this is number of nodes outside the pod) * total number of nodes
        here we should add the number of paths inside the pod
        + number of paths between hosts connected by the same router.
        :return:
        """
        total_paths = 0
        for host in self.getHosts():
            for host_pair in self.getHosts():
                if host == host_pair:
                    continue

                # compute the number of paths
                npaths = sum(1 for _ in nx.all_shortest_paths(self.graph, host, host_pair))
                total_paths += npaths

        return total_paths

    def getPathsBetweenNodes(self, nodeA, nodeB):
        """Compute the paths between two nodes."""
        paths = nx.all_shortest_paths(self.graph, nodeA, nodeB)
        paths = [tuple(x) for x in paths]

        return paths


class Topology(TopologyDB):
    def __init__(self, loadNetworkGraph=True,hostsMappings=True, *args, **kwargs):
        super(Topology, self).__init__(*args, **kwargs)

        # save network startup state
        # in case of link removal we use this objects to remember the state of links and nodes before removal
        # this assumes that the topology will not be enhanced, meaning that links and nodes can be removed and added, but
        # new links or devices can not be added.

        self._original_network = copy.deepcopy(self._network)

        try:
            if loadNetworkGraph:
                self.networkGraph = NetworkGraph(self)
        except:
            import traceback
            traceback.print_exc()

        # loads hosts to ip and ip to hosts mappings
        self.hostsIpMapping = {}
        if hostsMappings:
            self.hostsIpMappings()

    def hostsIpMappings(self):
        """Creates a mapping between host names and ip and vice versa."""
        self.hostsIpMapping = {}
        hosts = self.getHosts()
        self.hostsIpMapping["ipToName"] = {}
        self.hostsIpMapping["nameToIp"] = {}
        for host in hosts:
            ip = self.interface_ip(host, self.getHostFirstInterface(host).format(host))
            self.hostsIpMapping["ipToName"][ip] = host
            self.hostsIpMapping["nameToIp"][host] = ip

    def getHostFirstInterface(self, name):
        return self._network[name]["interfaces_to_node"].keys()[0]

    def getHostName(self, ip):
        """Returns the host name of the host that has the ip address."""
        name = self.hostsIpMapping.get("ipToName").get(ip)
        if name:
            return name
        raise InvalidIP("Any host of the network has the ip {0}".format(ip))

    def getHostIp(self, name):
        """Returns the ip of host name."""
        ip = self.hostsIpMapping.get("nameToIp").get(name)
        if ip:
            return ip
        raise HostDoesNotExist("Any host of the network has the name {0}".format(name))

    def areNeighbors(self, n1, n2):
        return self.networkGraph.areNeighbors(n1, n2)

    def getRouters(self):
        "Gets the routers from the topologyDB"
        return {node: self._network[node] for node in self._network if self._network[node]["type"] == "router"}

    def getHosts(self):
        "Gets the routers from the topologyDB"
        return {node: self._network[node] for node in self._network if self._network[node]["type"] == "host"}

    def getSwitches(self):
        return {node: self._network[node] for node in self._network if self._network[node]["type"] == "switch"}


def main():
    import sys
    if len(sys.argv) > 1:
        db = sys.argv[1]
    else:
        db = "./topology.db"

    topo = Topology(db=db)


if __name__ == '__main__':
    main()
