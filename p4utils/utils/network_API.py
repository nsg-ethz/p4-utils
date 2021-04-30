from ipaddress import IPv4Network
from mininet.link import TCIntf
from mininet.nodelib import LinuxBridge
from mininet.cli import CLI
from mininet.log import setLogLevel, info, output, debug, warning

from p4utils.utils.helper import *
from p4utils.mininetlib.node import *
from p4utils.mininetlib.net import P4Mininet as DEFAULT_NET
from p4utils.mininetlib.topo import P4Topo


class NetworkAPI:
    """
    Network definition and initialization API.
    """

    def __init__(self):
        self.topo = P4Topo()
        # List of switch IDs
        self.switch_ids = []
        self.node_ports = {}
        # Name of the CPU bridge
        self.cpu_bridge = None
        # Whether to enable the client or not
        self.cli_enabled = True
        setLogLevel('info')

## Utils
    def check_host_valid_ip_from_name(self, host):
        """
        Utils for assignment strategies.
        """
        valid = True
        if host[0] == 'h':
            try:
                int(host[1:])
            except:
                valid = False
        else:
            valid = False
        
        return valid

    def next_switch_id(self, base=1):
        """
        Compute the next switch id that can be used.
        """
        if len(self.switch_ids) == 0:
            return base
        else:
            return next_element(self.switch_ids, minimum=base)

    def next_port_num(self, node, base=0):
        """
        Compute the next port number that can be used on the node.
        """
        ports = self.node_ports.get(node)
        if ports:
            ports_list = list(ports.keys())
            if len(ports_list) == 0:
                return base
            else:
                return next_element(ports_list, minimum=base)
        else:
            return base

### Links
## Link setter
    def addLink(self, node1, node2, port1=None, port2=None,
                key=None, **opts):
        """
        Add link between two nodes. If key is None, then the next
        ordinal number is used.

        Arguments:
            node1, node2 (string): nodes to link together
            port1, port2 (int)   : ports (optional)
            key (int)            : id used to identify multiple edges which
                                   link two same nodes (optional)
            opts                 : link options (optional)
        
        Returns:
           link info key
        """
        if port1:
            if node1 in self.node_ports.keys():
                if port1 in self.node_ports[node1].keys():
                    raise Exception('port {} already present on node {}.'.format(port1, node1))
        else:
            if self.isSwitch(node1):
                port1 = self.next_port_num(node1, base=1)
            else:
                port1 = self.next_port_num(node1)

        self.node_ports.setdefault(node1, {})
        self.node_ports[node1][port1] = node2

        if port2:
            if node2 in self.node_ports.keys():
                if port2 in self.node_ports[node2].keys():
                    raise Exception('port {} already present on node {}.'.format(port2, node2))
        else:
            if self.isSwitch(node2):
                port2 = self.next_port_num(node2, base=1)
            else:
                port2 = self.next_port_num(node2)

        self.node_ports.setdefault(node2, {})
        self.node_ports[node2][port2] = node1

        opts.setdefault('intf', TCIntf)
        return self.topo.addLink(node1, node2, port1=port1, port2=port2,
                                 key=key, **opts)

## Link getter
    def getLink(self, node1, node2, key=None):
        """
        Return link metadata dict. If key is None, then the 
        link with the lowest key value is considered.

        Arguments:
            node1, node2 (string): nodes linked together
            key (int)        : id used to identify multiple edges which
                               link two same nodes (optional)

        Returns:
            link metadata dict
        """
        return self.topo.linkInfo(node1, node2, key=key)

## Link updater
    def updateLink(self, node1, node2, key=None, **opts):
        """
        Update link metadata dict. In fact, delete the node
        and create a new one with the updated information. 
        If key is None, then the link with the lowest key 
        value is considered.

        Arguments:
            node1, node2 (string): nodes to link together
            key (int)            : id used to identify multiple edges which
                                   link two same nodes (optional)
            opts                 : link options to update (optional)

        Returns:
            link metadata dict
        """
        info = self.popLink(node1, node2, key=key)
        # Check if the edge is in the wrong direction and
        # change all the fields accordingly
        if node1 == info['node2'] and node2 == info['node1']:
            info_new = {}
            for key, value in info.items():
                if '1' in key:
                    info_new[key.replace('1','2')] = value
                elif '2' in key:
                    info_new[key.replace('2','1')] = value
                else:
                    info_new[key] = value
        else:
            info_new = info
        # Remove 'node1' and 'node2' fields from link's information
        info_new.pop('node1')
        info_new.pop('node2')
        merge_dict(info_new, opts)
        return self.addLink(node1, node2, key=key, **info_new)

## Link deleter
    def popLink(self, node1, node2, key=None):
        """
        Pop link. If key is None, then the link with the lowest
        key value is considered.

        Arguments:
            node1, node2 (string): nodes to link together
            key (int)            : id used to identify multiple edges which
                                   link two same nodes (optional)

        Returns:
            link metadata dict
        """
        link = self.getLink(node1, node2, key=key)
        port1 = link.get('port1')
        port2 = link.get('port2')
        if port1:
            self.node_ports[node1].pop(port1)
        if port2:
            self.node_ports[node2].pop(port2)
        self.topo.deleteLink(node1, node2, key=key)
        return link

## Method to check neighbors
    def areNeighbors(self, node1, node2):
        """
        Check whether two node are neighbors.

        Arguments:
            node1, node2 (string): names of the nodes

        Returns:
            True if node1 and node2 are neighbors, False else.
        """
        if node1 in self.topo.g.edge.keys():
            if node2 in self.topo.g.edge[node1].keys():
                return True
        return False

## List of links
    def links(self, sort=False, withKeys=False, withInfo=False):
        """
        Return links only preserving (src, dst) order, i.e. no duplicated 
        edges are listed.

        Arguments:
            sort (bool)    : sort links alphabetically, preserving (src, dst) order
            withKeys (bool): return link keys
            withInfo (bool): return link info

        Returns: 
            list of (src, dst [,key, info ])
        """
        return self.topo.links(sort, withKeys, withInfo)

### Nodes
## Node setters
    def addNode(self, name, **opts):
        """
        Add Node to graph.

        Arguments:
            name (string): name
            opts (kwargs): node options

        Returns:
            node name
        """
        return self.topo.addNode(name, **opts)

    def addHost(self, name, **opts):
        """
        Add P4 host node to Mininet topology.
        If the node is already present, overwrite it.

        Arguments:
            name (string): switch name
            opts (kwargs): switch options (optional)

        Returns:
            P4 host name (string)
        """
        opts.setdefault('cls', P4Host)
        return self.topo.addHost(name, **opts)

    def addSwitch(self, name, **opts):
        """
        Add switch node to Mininet topology.
        If the node is already present, overwrite it.

        Arguments:
            name (string): switch name
            opts (kwargs): switch options

        Returns:
            switch name (string)
        """
        if 'dpid' in opts.keys():
            dpid = opts['dpid']
            switch_id = int(dpid, 16)
            if switch_id in self.switch_ids:
                raise Exception('dpid {} already in use.'.format(dpid))
        else:
            switch_id = self.next_switch_id()
            dpid = dpidToStr(switch_id)
            opts['dpid'] = dpid

        self.switch_ids.append(switch_id)
        return self.topo.addSwitch(name, **opts)

    def addP4Switch(self, name, **opts):
        """
        Add P4 switch node to Mininet topology.
        If the node is already present, overwrite it.

        Arguments:
            name (string): switch name
            opts (kwargs): switch options

        Returns:
            P4 switch name (string)
        """
        if 'device_id' in opts.keys():
            switch_id = opts['device_id']
            if switch_id in self.switch_ids:
                raise Exception('switch ID {} already in use.'.format(switch_id))
        else:
            switch_id = self.next_switch_id()
            opts['device_id'] = switch_id

        self.switch_ids.append(switch_id)
        opts.setdefault('cls', P4Switch)
        return self.topo.addP4Switch(name, **opts)

    def addP4RuntimeSwitch(self, name, **opts):
        """
        Add P4 runtime switch node to Mininet topology.
        If the node is already present, overwrite it.

        Arguments:
            name (string): switch name
            opts (kwargs): switch options

        Returns:
            P4 runtime switch name (string)
        """
        if 'device_id' in opts.keys():
            switch_id = opts['device_id']
            if switch_id in self.switch_ids:
                raise Exception('switch ID {} already in use.'.format(switch_id))
        else:
            switch_id = self.next_switch_id()
            opts['device_id'] = switch_id

        self.switch_ids.append(switch_id)
        opts.setdefault('cls', P4RuntimeSwitch)
        return self.topo.addP4RuntimeSwitch(name, **opts)

## Node getter
    def getNode(self, name):
        """
        Get node information.

        Arguments:
            node (string): Mininet node name

        Returns:
            node metadata dict
        """
        return self.topo.nodeInfo(name)

## Node updaters
    def updateNode(self, name, **opts):
        """
        Update node metadata dict. In fact, delete the node
        and create a new one with the updated information.

        Arguments:
            name (string): node name
            opts         : node options to update (optional)
        
        Returns:
            node name
        """
        if self.isHost(name):
            node_setter = self.addHost
        elif self.isP4RuntimeSwitch(name):
            node_setter = self.addP4RuntimeSwitch
        elif self.isP4Switch(name):
            node_setter = self.addP4Switch
        elif self.isSwitch(name):
            node_setter = self.addSwitch
        else:
            node_setter = self.addNode

        info = self.popNode(name)
        merge_dict(info, opts)
        return node_setter(name, **info)

## Node deleter
    def popNode(self, name):
        """
        Pop node.

        Arguments:
            node1, node2 (string): nodes to link together
            key (int)            : id used to identify multiple edges which
                                   link two same nodes (optional)

        Returns:
            node metadata dict
        """
        node = self.getNode(name)
        switch_id = node.get('device_id')
        if switch_id:
            self.switch_ids.remove(switch_id)
        else:
            # Non P4 switches have only dpid
            dpid = node.get('dpid')
            if dpid:
                switch_id = int(dpid, 16)
                self.switch_ids.remove(switch_id)
        self.topo.deleteNode(name)
        return node

## Methods to check the node type
    def isHost(self, name):
        """
        Check if node is a host.

        Arguments:
            node (string): Mininet node name

        Returns:
            True if node is a host, else False (bool)
        """
        return self.topo.isHost(name)

    def isSwitch(self, name):
        """
        Check if node is a switch.

        Arguments:
            node (string): Mininet node name

        Returns:
            True if node is a switch, else False (bool)
        """
        return self.topo.isSwitch(name)

    def isP4Switch(self, node):
        """
        Check if node is a P4 switch.

        Arguments:
            node (string): Mininet node name

        Returns:
            True if node is a P4 switch, else False (bool)
        """
        return self.topo.isP4Switch(node)

    def isP4RuntimeSwitch(self, node):
        """
        Check if node is a P4 runtime switch.

        Arguments:
            node (string): Mininet node name

        Returns:
            True if node is a P4 switch, else False (bool)
        """
        return self.topo.isP4RuntimeSwitch(node)

    def hasCpuPort(self, node):
        """
        Check if node has a CPU port.

        Arguments:
            node (string): Mininet node name

        Returns:
            True if node has a CPU port, else False (bool)
        """
        return self.getNode(node).get('cpu_port', False)

## Lists of node names by type
    def nodes(self, sort=True):
        """
        Return nodes.
        
        Arguments:
           sort (bool): sort nodes alphabetically

        Returns:
           list of node names
        """
        return self.topo.nodes(sort)

    def hosts(self, sort=True):
        """
        Return hosts.
        
        Arguments:
           sort (bool): sort hosts alphabetically

        Returns:
           list of host names
        """
        return self.topo.hosts(sort)

    def switches(self, sort=True):
        """
        Return switches.

        Arguments:
           sort (bool): sort switches alphabetically

        Returns:
            list of switch names    
        """
        return self.topo.switches(sort)

    def p4switches(self, sort=True):
        """
        Return P4 switches.

        Arguments:
           sort (bool): sort P4 switches alphabetically

        Returns:
           list of P4 switch names
        """
        return self.topo.p4switches(sort)

    def p4rtswitches(self, sort=True):
        """
        Return P4 runtime switches.

        Arguments:
           sort (bool): sort P4 runtime switches alphabetically

        Returns:
           list of P4 runtime switch names
        """
        return self.topo.p4rtswitches(sort)

## Hosts
    def setHostMAC(self, name, mac):
        """
        Set MAC address of the host's default interface.

        Arguments:
            name (string): name of the host
            mac (string) : MAC address to configure
        """
        if self.isHost(name):
            self.updateNode(name, mac=mac)
        else:
            raise Exception('{} is not a host.'.format(name))

    def setHostIP(self, name, ip):
        """
        Set IP address of the host's default interface.

        Arguments:
            name (string): name of the host
            ip (string)  : IP address/mask to configure
        """
        if self.isHost(name):
            self.updateNode(name, ip=ip)
        else:
            raise Exception('{} is not a host.'.format(name))

    def setHostDefaultRoute(self, name, default_route):
        """
        Set the host's default route.

        Arguments:
            name (string)         : name of the host
            default_route (string): default route IP
        """
        if self.isHost(name):
            self.updateNode(name, defaultRoute='via {}'.format(default_route))
        else:
            raise Exception('{} is not a host.'.format(name))

## P4 Switches
    def setSwitchID(self, name, id):
        """
        Set P4 Switch ID.

        Arguments:
            name (string): name of the P4 switch
            id (int)     : P4 switch ID
        """
        if self.isP4Switch(name):
            self.updateNode(name, device_id=id)
        else:
            raise Exception('{} is not a P4 switch.'.format(name))


    def setThriftPort(self, name, port):
        """
        Set the thrift port number for the P4 switch.

        Arguments:
            name (string): name of the P4 switch
            port (int)   : thrift port number
        """
        if self.isP4Switch(name):
            self.updateNode(name, thrift_port=port)
        else:
            raise Exception('{} is not a P4 switch.'.format(name))

    def enableDebugger(self, name):
        """
        Enable debugger for switch.

        Arguments:
            name (string): name of the P4 switch
        """
        if self.isP4Switch(name):
            self.updateNode(name, enable_debugger=True)
        else:
            raise Exception('{} is not a P4 switch.'.format(name))

    def disableDebugger(self, name):
        """
        Disable debugger for switch.

        Arguments:
            name (string): name of the P4 switch
        """            
        if self.isP4Switch(name):
            self.updateNode(name, enable_debugger=False)
        else:
            raise Exception('{} is not a P4 switch.'.format(name))

    def enableDebuggerAll(self):
        """
        Enable debugger for all the switches.
        """
        for switch in self.p4switches():
            self.enableDebugger(switch)

    def disableDebuggerAll(self):
        """
        Disable debugger for all the switches.
        """
        for switch in self.p4switches():
            self.disableDebugger(switch)

    def enableLog(self, name, log_dir='/tmp'):
        """
        Enable log for switch.

        Arguments:
            name (string)   : name of the P4 switch
            log_dir (string): where to save log files
        """            
        if self.isP4Switch(name):
            self.updateNode(name, log_enabled=True, log_dir=log_dir)
        else:
            raise Exception('{} is not a P4 switch.'.format(name))

    def disableLog(self, name):
        """
        Disable log for switch.

        Arguments:
            name (string): name of the P4 switch
        """            
        if self.isP4Switch(name):
            self.updateNode(name, log_enabled=False)
        else:
            raise Exception('{} is not a P4 switch.'.format(name))

    def enableLogAll(self, log_dir='/tmp'):
        """
        Enable log for all the switches.

        Arguments:
            log_dir (string): where to save log files
        """
        for switch in self.p4switches():
            self.enableLog(switch, log_dir=log_dir)

    def disableLogAll(self):
        """
        Disable log for all the switches.
        """
        for switch in self.p4switches():
            self.disableLog(switch)

    def enablePcapDump(self, name, pcap_dir='.'):
        """
        Enable pcap dump for switch.

        Arguments:
            name (string)    : name of the P4 switch
            pcap_dir (string): where to save pcap files
        """            
        if self.isP4Switch(name):
            self.updateNode(name, pcap_dump=True, pcap_dir=pcap_dir)
        else:
            raise Exception('{} is not a P4 switch.'.format(name))

    def disablePcapDump(self, name):
        """
        Disable pcap dump for switch.

        Arguments:
            name (string): name of the P4 switch
        """
        if self.isP4Switch(name):
            self.updateNode(name, pcap_dump=False)
        else:
            raise Exception('{} is not a P4 switch.'.format(name))

    def enablePcapDumpAll(self, pcap_dir='.'):
        """
        Enable pcap dump for all the switches.

        Arguments:
            pcap_dir (string): where to save pcap files
        """
        for switch in self.p4switches():
            self.enablePcapDump(switch, pcap_dir=pcap_dir)

    def disablePcapDumpAll(self):
        """
        Disable pcap dump for all the switches.
        """
        for switch in self.p4switches():
            self.disablePcapDump(switch)

    def enableCpuPort(self, name):
        """
        Enable CPU port on switch.

        Arguments:
            name (string): name of the P4 switch
        """
        if self.isP4Switch(name):
            # We use the bridge but at the same time we use the bug it has so the
            # interfaces are not added to it, but at least we can clean easily thanks to that.
            if not self.cpu_bridge:
                self.cpu_bridge = self.addSwitch('sw-cpu', cls=LinuxBridge, dpid='1000000000000000')
            self.addLink(name, self.cpu_bridge, intfName1='{}-cpu-eth0'.format(name), intfName2= '{}-cpu-eth1'.format(name), deleteIntfs=True)
            self.updateNode(name, cpu_port=True)
        else:
            raise Exception('{} is not a P4 switch.'.format(name))

    def disableCpuPort(self, name):
        """
        Disable CPU port on switch.

        Arguments:
            name (string): name of the P4 switch
        """
        if self.isP4Switch(name):
            self.popLink(name, sw)
            self.updateNode(name, cpu_port=False)
            delete_cpu_bridge = True
            for node in self.nodes():
                if self.hasCpuPort(node):
                    delete_cpu_bridge = False
                    break
            if delete_cpu_bridge:
                self.popNode(self.cpu_bridge)
                self.cpu_bridge = None
        else:
            raise Exception('{} is not a P4 switch.'.format(name))

    def enableCpuPortAll(self):
        """
        Enable CPU port on all the P4 switches.
        """
        for switch in self.p4switches():
            self.enableCpuPort(switch)

    def disableCpuPortAll(self):
        """
        Disable CPU port on all the P4 switches.
        """
        for switch in self.p4switches():
            self.popLink(name, sw)
            self.updateNode(name, cpu_port=False)
        delete_cpu_bridge = True
        for node in self.nodes():
            if self.hasCpuPort(node):
                delete_cpu_bridge = False
                break
        if delete_cpu_bridge:
            self.popNode(self.cpu_bridge)
            self.cpu_bridge = None

## P4 Runtime Switches
    def setGrpcPort(self, name, port):
        """
        Set the grpc port number for the P4 runtime switch.

        Arguments:
            name (string): name of the P4 runtime switch
            port (int)   : thrift port number
        """
        if self.isP4RuntimeSwitch(name):
            self.updateNode(name, grpc_port=port)
        else:
            raise Exception('{} is not a P4 runtime switch.'.format(name))

## Links
    def setBw(self, node1, node2, bw, key=None):
        """
        Set link bandwidth. If key is None, then the link with the lowest
        key value is considered.

        Arguments:
            node1, node2 (string): nodes linked together
            bw (float)           : bandwidth (in Mbps)
            key (int)            : id used to identify multiple edges which
                                   link two same nodes (optional)
        """
        if isinstance(bw, float):
            self.updateLink(node1, node2, key=key, bw=bw)
        else:
            raise TypeError('bw is not an integer.')

    def setDelay(self, node1, node2, delay, key=None):
        """
        Set link delay. If key is None, then the link with the lowest
        key value is considered.

        Arguments:
            node1, node2 (string): nodes linked together
            delay (int)          : transmission delay (in ms)
            key (int)            : id used to identify multiple edges which
                                   link two same nodes (optional)
        """
        if isinstance(delay, int):
            self.updateLink(node1, node2, key=key, delay=str(delay)+'ms')
        else:
            raise TypeError('delay is not an integer.')

    def setLoss(self, node1, node2, loss, key=None):
        """
        Set link loss. If key is None, then the link with the lowest
        key value is considered.

        Arguments:
            node1, node2 (string): nodes linked together
            loss (float)         : packet loss rate (e.g. 0.5 means that 50% of
                                   packets will exeperience a loss)
            key (int)            : id used to identify multiple edges which
                                   link two same nodes (optional)
        """
        if isinstance(loss, float):
            if loss <= 1 and loss >= 0:
                loss *= 100
                self.updateLink(node1, node2, key=key, loss=loss)
            else:
                raise Exception('the selected loss rate is not allowed.')
        else:
            raise TypeError('bw is not an integer.')

    def setMaxQueueSize(self, node1, node2, max_queue_size, key=None):
        """
        Set link max queue size. If key is None, then the link with the lowest
        key value is considered.

        Arguments:
            node1, node2 (string): nodes linked together
            max_queue_size (int) : maximum number of packets the qdisc may hold queued at a time.
            key (int)            : id used to identify multiple edges which
                                   link two same nodes (optional)
        """
        if isinstance(max_queue_size, int):
            self.updateLink(node1, node2, key=key, max_queue_size=max_queue_size)
        else:
            raise TypeError('max_queue_size is not an integer.')

    def setIntfIP(self, node1, node2, ip, key=None):
        """
        Set IP of node1's interface facing node2 with the specified key. If key is None,
        then the link with the lowest key value is considered. It is overridden by 
        self.setHostIP for the default interface.

        Arguments:
            node1, node2 (string): nodes linked together
            ip (string)          : IP address/mask to configure
            key (int)            : id used to identify multiple edges which
                                   link two same nodes (optional)
        """
        if self.isSwitch(node1):
            # Set fake IP for switches
            self.updateLink(node1, node2, key=key, sw_ip1=ip)
        else:
            # Set real IP for other devices
            self.updateLink(node1, node2, key=key, params1={'ip': ip})

    def setIntfMAC(self, node1, node2, mac, key=None):
        """
        Set MAC of node1's interface facing node2 with the specified key.

        Arguments:
            node1, node2 (string): nodes linked together
            mac (string)         : MAC address to configure
            key (int)            : id used to identify multiple edges which
                                   link two same nodes (optional)
        """
        self.updateLink(node1, node2, key=key, addr1=mac)

    def setBwAll(self, bw):
        """
        Set bandwidth for all the links currently in the network.

        Arguments:
            bw (float): bandwidth (in Mbps)
        """
        for node1, node2, key in self.links(withKeys=True):
            self.setBw(node1, node2, bw, key=key)

    def setDelayAll(self, delay):
        """
        Set delay for all the links currently in the network.

        Arguments:
            delay (int): transmission delay (in ms)
        """
        for node1, node2, key in self.links(withKeys=True):
            self.setDelay(node1, node2, delay, key=key)

    def setLossAll(self, loss):
        """
        Set loss for all the links currently in the network.

        Arguments:
            loss (float): packet loss rate (e.g. 0.5 means that 50% of
                          packets will exeperience a loss)
        """
        for node1, node2, key in self.links(withKeys=True):
            self.setLoss(node1, node2, loss, key=key)
    
    def setMaxQueueSizeAll(self, max_queue_size):
        """
        Set max queue size for all the links currently in the network.

        Arguments:
            max_queue_size (int): maximum number of packets the qdisc may hold queued at a time.
        """
        for node1, node2, key in self.links(withKeys=True):
            self.setMaxQueueSize(node1, node2, max_queue_size, key=key)

## Assignment strategies
    def printPortMapping(self):
        """
        Print the port mapping of all the devices.
        """
        print('Port mapping:')
        for node1 in sorted(self.node_ports.keys()):
            print('{}: '.format(node1), end=' ')
            for port1, node2 in self.node_ports[node1].items():
                print('{}:{}\t'.format(port1, node2), end=' ')
            print()

    def l2(self):
        """
        Automated IP/MAC assignment strategy for already initialized 
        links and nodes. All the devices are placed inside the same
        IPv4 network (10.0.0.0/16).

        Assumptions:
            Each host is connected to one switch only.
            Only switches and hosts are allowed.
        """
        info('"l2" assignment strategy selected.\n')
        ip_generator = IPv4Network('10.0.0.0/16').hosts()
        reserved_ips = {}
        assigned_ips = set()

        for node in self.nodes():
            if self.isHost(node):
                # Reserve IPs for normal hosts
                if self.check_host_valid_ip_from_name(node):
                    host_num = int(host_name[1:])
                    upper_byte = (host_num & 0xff00) >> 8
                    lower_byte = (host_num & 0x00ff)
                    host_ip = '10.0.%d.%d' % (upper_byte, lower_byte)
                    reserved_ips[host_name] = host_ip
            else:
                # If it is not a host, it must be a switch
                assert self.isSwitch(node)

        for node1, node2, key in self.links(withKeys=True):
            # Node-switch link
            if self.isHost(node1):
                host_name = node1
                direct_sw = node2
                assert self.isSwitch(node2)
            # Switch-node link
            elif self.isHost(node2):
                host_name = node2
                direct_sw = node1
                assert self.isSwitch(node1)
            # Switch-switch link
            else:
                continue

            if self.check_host_valid_ip_from_name(host_name):
                host_ip = reserved_ips[host_name]
                # We check if for some reason the ip was already given by the ip_generator. 
                # This can only happen if the host naming is not <h_x>.
                # This should not be possible anymore since we reserve ips for h_x hosts.
                while host_ip in assigned_ips:
                    host_ip = str(next(ip_generator).compressed)
                assigned_ips.add(host_ip)
            else:
                host_ip = next(ip_generator).compressed
                # We check if for some reason the ip was already given by the ip_generator. 
                # This can only happen if the host naming is not <h_x>.
                # This should not be possible anymore since we reserve ips for h_x hosts.
                while host_ip in assigned_ips or host_ip in list(reserved_ips.values()):
                    host_ip = str(next(ip_generator).compressed)
                assigned_ips.add(host_ip)

            host_mac = ip_address_to_mac(host_ip) % (0)
            direct_sw_mac = ip_address_to_mac(host_ip) % (1)

            self.setIntfMAC(host_name, direct_sw, host_mac)
            self.setIntfMAC(direct_sw, host_name, direct_sw_mac)

            self.setHostIP(host_name, host_ip+'/16')
            self.setHostMAC(host_name, host_mac)

## Create and start network
    def enableCLI(self):
        self.cli_enabled = True

    def disableCLI(self):
        self.cli_enabled = False

    def do_net_cli(self):
        """
        Starts up the mininet CLI and prints some helpful output.

        Assumes:
            A mininet instance is stored as self.net and self.net.start() has been called.
        """
        for switch in self.net.switches:
            if self.topo.isP4Switch(switch.name):
                switch.describe()
        for host in self.net.hosts:
            host.describe()
        info("Starting mininet CLI...\n")
        # Generate a message that will be printed by the Mininet CLI to make
        # interacting with the simple switch a little easier.
        print('')
        print('======================================================================')
        print('Welcome to the P4 Utils Mininet CLI!')
        print('======================================================================')
        print('Your P4 program is installed into the BMV2 software switch')
        print('and your initial configuration is loaded. You can interact')
        print('with the network using the mininet CLI below.')
        print('')
        # print('To inspect or change the switch configuration, connect to')
        # print('its CLI from your host operating system using this command:')
        # print('  {} --thrift-port <switch thrift port>'.format(DEFAULT_CLIENT.cli_bin))
        # print('')
        # print('To view a switch log, run this command from your host OS:')
        # print('  tail -f {}/<switchname>.log'.format(self.log_dir))
        # print('')
        # print('To view the switch output pcap, check the pcap files in \n {}:'.format(self.pcap_dir))
        # print(' for example run:  sudo tcpdump -xxx -r s1-eth1.pcap')
        # print('')

        CLI(self.net)

    def startNetwork(self, network=DEFAULT_NET):
        """
        Once the topology has been created, create and start the Mininet network.
        If enabled, start the client

        Arguments:
            network (Mininet network class): the network class to use (optional)
        """
        debug('Creating network...\n')
        self.net = network(topo=self.topo,
                           controller=None)

        debug('Starting network...\n')
        self.net.start()

        if self.cli_enabled:
            self.do_net_cli()
            # Stop right after the CLI is exited
            self.net.stop()