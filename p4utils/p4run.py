#!/usr/bin/env python3
# Copyright 2013-present Barefoot Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Adapted by Robert MacDavid (macdavid@cs.princeton.edu) from scripts found in
# the p4app repository (https://github.com/p4lang/p4app)
#
#
# Further work: Edgar Costa Molero (cedgar@ethz.ch)
# Further work: Fabian Schleiss (fabian.schleiss@alumni.ethz.ch)
# Further work: Jurij Nota (junota@student.ethz.ch)

import os
import argparse
import mininet
import json
from copy import deepcopy
from time import sleep
from ipaddress import ip_interface
from mininet.log import setLogLevel, info, output, debug, warning
from mininet.link import TCIntf
from mininet.clean import sh
from networkx.classes.multigraph import MultiGraph
from networkx.classes.graph import Graph
from networkx.readwrite.json_graph import node_link_data

from p4utils.utils.helper import *
from p4utils.utils.compiler import P4InfoDisabled
from p4utils.utils.compiler import P4C as DEFAULT_COMPILER
from p4utils.utils.client import ThriftClient as DEFAULT_CLIENT
from p4utils.utils.topology import NetworkGraph
from p4utils.mininetlib.node import P4Switch as DEFAULT_SWITCH
from p4utils.mininetlib.node import Router as DEFAULT_ROUTER
from p4utils.mininetlib.node import P4Host as DEFAULT_HOST
from p4utils.mininetlib.topo import AppTopoStrategies as DEFAULT_TOPO
from p4utils.mininetlib.cli import P4CLI
from p4utils.mininetlib.net import P4Mininet as DEFAULT_NET


class AppRunner(object):
    """
    Class for running P4 applications.
    """

    def __init__(self, conf_file,
                 cli_enabled=True,
                 empty_p4=False,
                 log_dir=None,
                 pcap_dir=None,
                 verbosity='info'):
        """
        Initializes some attributes and reads the topology json.

        Attributes:
            conf_file (string): a JSON file which describes the mininet topology.
            cli_enabled (bool): enable mininet CLI.
            empty_p4 (bool): use an empty program for debugging.
            log_dir (string): directory for mininet log files.
            pcap_dir (string): directory where to store pcap files.
            verbosity (string): see https://github.com/mininet/mininet/blob/master/mininet/log.py#L14

        The following attributes are initialized during the execution and are
        not specified in the constructor:
            pcap_dump (bool)    : determines if we generate pcap files for interfaces.
            hosts (list)        : list of mininet host names.
            switches (dict)     : mininet host names and their associated properties.
            links (list)        : list of mininet link properties.
            clients (list)      : list of clients (one per client-capable switch) to populate tables
            compilers (list)    : list of compilers (one per P4 source provided) to compile P4 code
            conf (dict)         : parsed configuration from conf_file.
            topo (Topo object)  : the mininet topology instance.
            net (Mininet object): the mininet instance.
            *_module (dict/obj) : module dict used to import the specified module (see below)
            *_node (dict/obj)   : node dict uset to import the specified Mininet node (see below)
            
        Modules and nodes available
        Inside self.conf can be present several module configuration objects. These are the possible values:
            - "switch_node" loads the switch node to be used with Mininet (see mininetlib/node.py),
            - "compiler_module" loads the compiler for P4 codes,
            - "host_node" loads the host node to be used with Mininet,
            - "client_module" loads the client to program switches from files.
            - "topo_module" loads Mininet topology module
            - "mininet_module" loads the network module

        Example of JSON structure of conf_file:
        {
            "p4_src": <path to gobal p4 source> (string),
            "cli": <true|false> (bool),
            "pcap_dump": <true|false> (bool),
            "enable_log": <true|false> (bool),
            "host_node":
            {
                "file_path": <path to module> (string),
                "module_name": <module file name> (string),
                "object_name": <module object> (string)
            },
            "switch_node":
            {
                "file_path": <path to module> (string),
                "module_name": <module file name> (string),
                "object_name": <module object> (string)
            },
            "compiler_module":
            {
                "file_path": <path to module> (string),
                "module_name": <module file name> (string),
                "object_name": <module object> (string),
                "options": <options passed to init> (dict)
            },
            "client_module":
            {
                "file_path": <path to module> (string),
                "module_name": <module file name> (string),
                "object_name": <module object> (string),
                "options": <options passed to init> (dict)
            },
            "topo_module":
            {
                "file_path": <path to module> (string),
                "module_name": <module file name> (string),
                "object_name": <module object> (string)
            },
            "mininet_module":
            {
                "file_path": <path to module> (string),
                "module_name": <module file name> (string),
                "object_name": <module object> (string)
            },
            "exec_scripts": 
            [
                {
                    "cmd": <path to script> (string),
                    "reboot_run": <true|false> (bool)
                },
                ...
            ],
            "topology": 
            {
                "assignment_strategy": assignment_strategy,
                "default":
                {
                    <default links and hosts configurations, see parse_links>
                }
                "links": 
                [
                    <see parse_links>
                ],
                "hosts": 
                {
                    "h1":{}
                },
                "switches": {
                    <see parse_switch>
                }
            }
        }

        Notice: none of the modules or nodes are mandatory. In case they are not specified,
        default settings will be used.
        """
        # Clients of switches
        self.clients = []
        # Compilers of switches
        self.compilers = []

        # Set verbosity
        self.verbosity = verbosity
        setLogLevel(self.verbosity)

        # Read JSON configuration file
        self.conf_file = conf_file

        mininet.log.info('Reading JSON configuration file...\n')
        debug('Opening file {}\n'.format(self.conf_file))
        if not os.path.isfile(self.conf_file):
            raise FileNotFoundError("{} is not in the directory!".format(os.path.realpath(self.conf_file)))
        self.conf = load_conf(self.conf_file)

        # we can start topologies with no program to test
        # Should verify this to see if it works...
        if empty_p4:
            info('Empty P4 program selected.\n')
            import p4utils
            lib_path = os.path.dirname(p4utils.__file__)
            lib_path += '/../empty_program/empty_program.p4'
            # Set default program to empty program
            self.conf['p4_src'] = lib_path

            # Override custom switch programs with empty program
            for switch, params in self.conf['topology']['switches'].items():
                if params.get('p4_src', False):
                    params['p4_src'] = lib_path

        self.cli_enabled = cli_enabled
        self.pcap_dir = pcap_dir
        self.log_dir = log_dir

        ## Get log settings
        self.log_enabled = self.conf.get("enable_log", False)

        # Ensure that all the needed directories exist and are directories
        if self.log_enabled:
            if not os.path.isdir(self.log_dir):
                if os.path.exists(self.log_dir):
                    raise FileExistsError("'{}' exists and is not a directory!".format(self.log_dir))
                else:
                    debug('Creating directory {} for logs.\n'.format(self.log_dir))
                    os.mkdir(self.log_dir)
        
        os.environ['P4APP_LOGDIR'] = self.log_dir

        ## Get pcap settings
        self.pcap_dump = self.conf.get("pcap_dump", False)

        # Ensure that all the needed directories exist and are directories
        if self.pcap_dump:
            if not os.path.isdir(self.pcap_dir):
                if os.path.exists(self.pcap_dir):
                    raise FileExistsError("'{}' exists and is not a directory!".format(self.pcap_dir))
                else:
                    debug('Creating directory {} for pcap files.\n'.format(self.pcap_dir))
                    os.mkdir(self.pcap_dir)

        ## Mininet nodes
        # Load default switch node
        self.switch_node = {}
        if self.conf.get('switch_node', None):
            self.switch_node = load_custom_object(self.conf.get('switch_node'))
        else:
            self.switch_node = DEFAULT_SWITCH

        # Load default host node
        self.host_node = {}
        if self.conf.get('host_node', None):
            self.host_node = load_custom_object(self.conf.get('host_node'))
        else:
            self.host_node = DEFAULT_HOST

        # Load default router node
        self.router_node = {}
        if self.conf.get('router_node', None):
            self.switch_node = load_custom_object(self.conf.get('router_node'))
        else:
            self.router_node = DEFAULT_ROUTER

        ## Modules
        # Load default compiler module
        self.compiler_module = {}
        # Set default options for the compiler
        default_compiler_kwargs = {
                                     'opts': '--target bmv2 --arch v1model --std p4-16',
                                     'p4rt': False 
                                  }
        if self.conf.get('compiler_module', None):
            if self.conf['compiler_module'].get('object_name', None):
                self.compiler_module['module'] = load_custom_object(self.conf.get('compiler_module'))
            else:
                self.compiler_module['module'] = DEFAULT_COMPILER
            # Load default compiler module arguments
            self.compiler_module['kwargs'] = self.conf['compiler_module'].get('options', default_compiler_kwargs)
        else:
            self.compiler_module['module'] = DEFAULT_COMPILER
            self.compiler_module['kwargs'] = default_compiler_kwargs

        # Load default client module
        self.client_module = {}
        # Set default options for the client
        default_client_kwargs = {
                                    'log_enabled': self.log_enabled,
                                    'log_dir': self.log_dir
                                }
        if self.conf.get('client_module', None):
            if self.conf['client_module'].get('object_name', None):
                self.client_module['module'] = load_custom_object(self.conf.get('client_module'))
            else:
                self.client_module['module'] = DEFAULT_CLIENT
            # Load default client module arguments
            self.client_module['kwargs'] = self.conf['client_module'].get('options', default_client_kwargs)
        else:
            self.client_module['module'] = DEFAULT_CLIENT
            self.client_module['kwargs'] = default_client_kwargs

        ## Old modules
        if self.conf.get('topo_module', None):
            self.app_topo = load_custom_object(self.conf.get('topo_module'))
        else:
            self.app_topo = DEFAULT_TOPO

        if self.conf.get('mininet_module', None):
            self.app_mininet = load_custom_object(self.conf.get('mininet_module'))
        else:
            self.app_mininet = DEFAULT_NET

        # Clean default switches
        self.switch_node.stop_all()
        self.router_node.stop_all()

        ## Load topology 
        topology = self.conf.get('topology', False)
        if not topology:
            raise Exception('Topology to create is not defined in {}'.format(self.conf))
        else:
            # Import topology components
            self.hosts = topology['hosts']
            self.links = self.parse_links(topology['links'])
            self.switches = self.parse_switches(topology.get('switches', None))
            self.routers = self.parse_routers(topology.get('routers', None))
            self.assignment_strategy = topology.get('assignment_strategy', "l2")
            import ipdb; ipdb.set_trace()

    def exec_scripts(self):
        """
        Executes the script present in the "exec_scripts" field of self.conf.
        """
        if isinstance(self.conf.get('exec_scripts', None), list):
            for script in self.conf.get('exec_scripts'):
                info('Exec Script: {}\n'.format(script['cmd']))
                run_command(script['cmd'])

    def parse_switches(self, unparsed_switches):
        """
        A switch should have the following structure inside the topology object
        "switches":
        {
            switch_name:
            {
                "p4_src": path_to_p4_program (string),
                "cpu_port": <true|false> (bool),
                "cli_input": <path to cli input file> (string),
                "switch_node": custom_switch_node (dict),
                "client_module": custom_client_module (dict),
                "log_enabled" : <true|false> (bool), (*)
                "log_dir": <log path for switch binary> (string), (*)
                "pcap_dump": <true|false> (bool), (*)
                "pcap_dir": <path for pcap files> (string), (*)
                "sw_bin": switch_binary (string), (*)
                "thrift_port": thrift_port (int), (*)
                "grpc_port": grpc_port (int) (*)
            },
            ...
        }

        (*) Parameters used to initialize the actual Mininet node (see p4utils.mininetlib.node).
        The other parameters are needed for other application features and functions and can be retrieved
        under getattr(mininetlib.net['node_name'],'params') dictionary.
        These settings override the default ones. None of these fields is mandatory.
        """
        switches = {}
        # When there are no switches in the topology
        if not unparsed_switches:
            return switches
        next_thrift_port = 9090
        next_grpc_port = 9559

        for switch, custom_params in unparsed_switches.items():
            # Set general default switch options
            params = {
                         'p4_src': self.conf['p4_src'],
                         'cpu_port': False,
                         'switch_node': deepcopy(self.switch_node),
                         'client_module': deepcopy(self.client_module),
                         'pcap_dump': self.pcap_dump,
                         'pcap_dir': self.pcap_dir,
                         'log_enabled': self.log_enabled,
                         'thrift_port': next_thrift_port,
                         'grpc_port': next_grpc_port
                     }

            ## Parse Switch node type
            # Set non default node type (the module JSON is converted into a Switch object)
            if 'switch_node' in custom_params:
                custom_params['cls'] = load_custom_object(custom_params['switch_node'])
                # This field is not propagated further
                del custom_params['switch_node']
            else:
                params['cls'] = params['switch_node']
            # This field is not propagated further
            del params['switch_node']

            ## Parse Switch client type
            # Set non default client type (the module JSON is converted into a Contoller object)
            kwargs = params['client_module']['kwargs']
            if 'client_module' in custom_params:
                module = load_custom_object(custom_params['client_module'])
                kwargs.update(custom_params['client_module']['kwargs'])
                # This field is not propagated further
                del custom_params['client_module']
            else:
                module = params['client_module']['module']
            # This field is not propagated further
            del params['client_module']
            # If a client command input is set
            if 'cli_input' in custom_params:
                kwargs.setdefault('conf_path',custom_params['cli_input'])
            # Add client to list
            self.clients.append(module(sw_name=switch,
                                       thrift_port=next_thrift_port,
                                       grpc_port=next_grpc_port,
                                       **kwargs))
 
            # Update default parameters with custom ones
            params.update(custom_params)
            switches[switch] = deepcopy(params)
            # Update switch port numbers
            next_thrift_port = max(next_thrift_port + 1, params['thrift_port'])
            next_grpc_port = max(next_grpc_port + 1, params['grpc_port'])
    
        return switches

    def parse_routers(self, unparsed_routers):
        """ Parse the routers from the json file to run FRR on the routers
            Due to the code sturcture requirements, parsing the routers similar to
            the switches but with minimum requirements?
        """

        routers = {}
        # when there are no routers in the topology
        if not unparsed_routers:
            return routers

        for router, custom_params in unparsed_routers.items():
            routers[router] = deepcopy(custom_params)
        return routers        

    def parse_links(self, unparsed_links):
        """
        Load a list of links descriptions of the form 
        "links":
        [
            [
                node1,
                node2, 
                { 
                    "weight": weight,
                    "port1": port1,
                    "port2": port2,
                    "intfName1": intfName1,
                    "intfName2": intfName2,
                    "addr1": addr1,
                    "addr2": addr2,
                    "params1": { parameters_for_interface1 },
                    "params2": { parameters_for_interface2 },
                    "bw": bandwidth,
                    "delay": transmit_delay,
                    "loss": loss,
                    "max_queue_size": max_queue_size
                }
            ],
            ...
        ]
        where the only mandatory fields are node1 and node2 and complete missing with
        default values and store them as self.links.

        For what concernes the Mininet classes used, we have that:
            "weight" is used by Networkx,
            "port*" are used by mininet.Topo and are propagated to mininet.Link.
            "intfName*" are propagated to mininet.Link and used by each mininet.link.Intf of the mininter.Link.
            "addr*" are propagated to mininet.Link and used by each mininet.link.Intf of the mininet.Link.
            "params*" are propagated to mininet.Link and used by each mininet.link.Intf of the link.
            "bw", "delay", "loss" and "max_queue_size" are propagated to mininet.Link and used by both mininet.link.Intf of the mininet.Link.
        
        "weight", "bw", "delay", "loss", "max_queue_size" default value can be set by
        putting inside "topology" the following object:
        "default":
        {
            "weight": weight,
            "bw": bandwidth,
            "delay": transmit_delay,
            "loss": loss,
            "max_queue_size": max_queue_size
        }

        Args:
            uparsed_links (array): unparsed links from topology json

        Returns:
            array of parsed link dictionaries
        """

        links = []

        default = self.conf['topology'].get('default', {})
        default.setdefault('weight', 1)
        default.setdefault('bw', None)
        default.setdefault('delay', None)
        default.setdefault('loss', None)
        default.setdefault('max_queue_size', None)

        for link in unparsed_links:
            node1 = link[0]
            node2 = link[1]
            opts = default.copy()
            # If attributes are present for that link
            if len(link) > 2:
                opts.update(link[2])
            # Hosts are not allowed to connect to another host.
            if node1 in self.hosts:
                assert node2 not in self.hosts, 'Hosts should be connected to switches: {} <-> {} link not possible'.format(node1, node2)
            links.append([node1, node2, deepcopy(opts)])

        return links

    def compile_p4(self):
        """
        Compile all the P4 files provided by the configuration file.

        Side effects:
            - The path of the compiled P4 JSON file is added to each switch
              in the field 'opts' under the name 'json_path'.
            - The dict self.compilers contains all the compilers object used
              (one per different P4 file).
        """
        info('Compiling P4 programs...\n')
        self.compilers = []
        for switch, params in self.switches.items():
            # If the file has not been compiled yet
            if not is_compiled(os.path.realpath(params['p4_src']), self.compilers):
                compiler = self.compiler_module['module'](p4_src=params['p4_src'],
                                                          **self.compiler_module['kwargs'])
                compiler.compile()
                self.compilers.append(compiler)
            else:
                # Retrieve compiler
                compiler = get_by_attr('p4_src', os.path.realpath(params['p4_src']), self.compilers)
            # Retrieve json_path
            params['json_path'] = compiler.get_json_out()
            # Try to retrieve p4 runtime info file path
            try:
                params['p4rt_path'] = compiler.get_p4rt_out()
            except P4InfoDisabled:
                pass
            # Deepcopy needed for non flat dicts
            self.switches[switch] = deepcopy(params)

    def create_network(self):
        """
        Create the mininet network object, and store it as self.net.

        Side effects:
            - Mininet topology instance stored as self.topo
            - Mininet instance stored as self.net
        """
        debug('Generating topology...\n')
        # Generate topology
        self.topo = self.app_topo(hosts = self.hosts, 
                                  switches = self.switches,
                                  routers = self.routers,
                                  links = self.links,
                                  assignment_strategy = self.assignment_strategy)

        # Start P4 Mininet
        debug('Starting network...\n')
        self.net = self.app_mininet(topo=self.topo,
                                    intf=TCIntf,
                                    host=self.host_node,
                                    controller=None)

    def program_hosts(self):
        """
        Adds static ARP entries and default routes to each mininet host.

        Assumes:
            A mininet instance is stored as self.net and self.net.start() has been called.
            A default field is found in "topology" containing (possibly) these fields.
            "default":
            {
                "auto_arp_tables": <true|false>,
                "auto_gw_arp": <true|false>
            }
        """
        default = self.conf['topology'].get('default', {})
        auto_arp_tables = default.get('auto_arp_tables', True)
        auto_gw_arp = default.get('auto_gw_arp', True)

        for host_name in self.topo.hosts():
            h = self.net.get(host_name)

            # Ensure each host's interface name is unique, or else
            # mininet cannot shutdown gracefully
            h_iface = list(h.intfs.values())[0]

            # if there is gateway assigned
            if auto_gw_arp:
                if 'defaultRoute' in h.params:
                    link = h_iface.link
                    sw_iface = link.intf1 if link.intf1 != h_iface else link.intf2
                    gw_ip = h.params['defaultRoute'].split()[-1]
                    h.cmd('arp -i {} -s {} {}'.format(h_iface.name, gw_ip, sw_iface.mac))

            if auto_arp_tables:
                # set arp rules for all the hosts in the same subnet
                host_address = ip_interface('{}/{}'.format(h.IP(), self.topo.hosts_info[host_name]["mask"]))
                for hosts_same_subnet in self.topo.hosts():
                    if hosts_same_subnet == host_name:
                        continue

                    #check if same subnet
                    other_host_address = ip_interface(str("%s/%d" % (self.topo.hosts_info[hosts_same_subnet]['ip'],
                                                                            self.topo.hosts_info[hosts_same_subnet]["mask"])))

                    if host_address.network.compressed == other_host_address.network.compressed:
                        h.cmd('arp -i %s -s %s %s' % (h_iface.name, self.topo.hosts_info[hosts_same_subnet]['ip'],
                                                            self.topo.hosts_info[hosts_same_subnet]['mac']))

            # if the host is configured to use dhcp
            auto_ip = self.hosts[host_name].get('auto', False)
            if auto_ip:
                h.cmd('dhclient -r {}'.format(h_iface.name))
                h.cmd('dhclient {} &'.format(h_iface.name))

            # run startup commands (this commands must be non blocking)
            commands = self.hosts[host_name].get('commands', [])
            for command in commands:
                h.cmd(command)

    def program_switches(self):
        """
        If any command files were provided for the switches, this method will start up the
        CLI on each switch and use the contents of the command files as input.

        Assumes:
            self.clients has been populated and self.net.start() has been called.
        """
        for cli in self.clients:
            if cli.get_conf():
                cli.configure()

    def save_topology(self, json_path='topology.json', multigraph=False):
        """
        Saves mininet topology to a JSON file.
        
        Arguments:
            json_path (string): output JSON file path
            multigraph (bool) : whether to convert to multigraph (multiple links
                                allowed between two nodes) or graph (only one link
                                allowed between two nodes).

        Notice that multigraphs are not supported yet by p4utils.utils.Topology
        """
        # This function return None for each not serializable
        # obect so that no TypeError is thrown.
        def default(obj):
            return None

        info('Saving mininet topology to database: {}\n'.format(json_path))
        if multigraph:
            warning('Multigraph topology selected!\n')
            graph = self.topo.g.convertTo(MultiGraph, data=True, keys=True)
        else:
            graph = self.topo.g.convertTo(NetworkGraph, data=True, keys=False)
            
            ## Add additional informations to the graph which are not loaded automatically
            # Add links informations
            for _, _, params in graph.edges(data=True):
                node1_name = params['node1']
                node2_name = params['node2']
                node1 = self.net[node1_name]
                node2 = self.net[node2_name]
                edge = graph[node1_name][node2_name]

                # Get link
                link = self.net.linksBetween(node1, node2)[0]

                # Get interfaces
                intf1 =  getattr(link, 'intf1')
                intf2 =  getattr(link, 'intf2')

                # Get interface names
                edge['intfName1'] = getattr(intf1, 'name')
                edge['intfName2'] = getattr(intf2, 'name')
                
                # Get interface addresses
                try:
                    # Fake switch IP
                    edge['ip1'] = edge['sw_ip1']
                    del edge['sw_ip1']
                except KeyError:
                    # Real IP
                    ip1, prefixLen1 = getattr(intf1, 'ip'), getattr(intf1, 'prefixLen')
                    if ip1 and prefixLen1:
                        edge['ip1'] = ip1 + '/' + prefixLen1

                try:
                    # Fake switch IP
                    edge['ip2'] = edge['sw_ip2']
                    del edge['sw_ip2']
                except KeyError:
                    # Real IP
                    ip2, prefixLen2 = getattr(intf2, 'ip'), getattr(intf2, 'prefixLen')
                    if ip2 and prefixLen2:
                        edge['ip2'] = ip2 + '/' + prefixLen2

                mac1 = getattr(intf1, 'mac')
                if mac1:
                    edge['addr1'] = mac1

                mac2 = getattr(intf2, 'mac')
                if mac1:
                    edge['addr2'] = mac2

        graph_dict = node_link_data(graph)
        with open(json_path,'w') as f:
            json.dump(graph_dict, f, default=default)
    
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
        print('To inspect or change the switch configuration, connect to')
        print('its CLI from your host operating system using this command:')
        print('  {} --thrift-port <switch thrift port>'.format(DEFAULT_CLIENT.cli_bin))
        print('')
        print('To view a switch log, run this command from your host OS:')
        print('  tail -f {}/<switchname>.log'.format(self.log_dir))
        print('')
        print('To view the switch output pcap, check the pcap files in \n {}:'.format(self.pcap_dir))
        print(' for example run:  sudo tcpdump -xxx -r s1-eth1.pcap')
        print('')

        # Start CLI
        P4CLI(mininet=self.net,
              clients=self.clients,
              compilers=self.compilers,
              compiler_module=self.compiler_module,
              client_module=self.client_module,
              scripts=self.conf.get('exec_scripts', None))

    def run_app(self):
        """
        Sets up the mininet instance, programs the switches, and starts the mininet CLI.
        This is the main method to run after initializing the object.
        """
        # Compile P4 programs
        self.compile_p4()
        # Initialize Mininet with the topology specified by the configuration
        self.create_network()
        # Start Mininet
        self.net.start()
        sleep(1)

        # Some programming that must happen after the network has started
        self.program_hosts()
        self.program_switches()

        # Save mininet topology to a database
        self.save_topology()
        sleep(1)

        # Execute configuration scripts on the nodes
        self.exec_scripts()

        # Start up the mininet CLI
        if self.cli_enabled or (self.conf.get('cli', False)):
            self.do_net_cli()
            # Stop right after the CLI is exited
            self.net.stop()


def get_args():
    cwd = os.getcwd()
    default_log = os.path.join(cwd, 'log')
    default_pcap = os.path.join(cwd, 'pcap')

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', help='Path to configuration',
                        type=str, required=False, default='./p4app.json')
    parser.add_argument('--log-dir', type=str, required=False, default=default_log)
    parser.add_argument('--pcap-dir', help='Generate pcap files for interfaces.',
                        action='store_true', required=False, default=default_pcap)
    parser.add_argument('--cli', help='Run mininet CLI.',
                        action='store_true', required=False, default=True)
    parser.add_argument('--verbosity', help='Set messages verbosity.',
                        action='store_true', required=False, default='info')
    parser.add_argument('--clean', help='Cleans previous log files',
                        action='store_true', required=False, default=False)
    parser.add_argument('--clean-dir', help='Cleans previous log files and closes',
                        action='store_true', required=False, default=False)
    parser.add_argument('--empty-p4', help='Runs the topology with an empty p4 program that does nothing',
                    action='store_true', required=False, default=False)              

    return parser.parse_args()


def main():

    args = get_args()

    setLogLevel('info')

    # clean
    cleanup()

    # remove cli logs
    sh('find -type f -regex ".*cli_output.*" | xargs rm')

    if args.clean or args.clean_dir:
        # removes first level pcap and log dirs
        sh("rm -rf %s" % args.pcap_dir)
        sh("rm -rf %s" % args.log_dir)
        # tries to recursively remove all pcap and log dirs if they are named 'log' and 'pcap'
        sh('find -type d -regex ".*pcap" | xargs rm -rf')
        sh('find -type d -regex ".*log" | xargs rm -rf')
        # removes topologies files
        sh('find -type f -regex ".*db" | xargs rm')
        # remove compiler outputs
        sh('find -type f -regex ".*\(p4i\|p4rt\)" | xargs rm')

        # remove all the jsons that come from a p4
        out = sh('find -type f -regex ".*p4"')
        p4_files = [x.split("/")[-1].strip() for x in out.split("\n") if x]
        for p4_file in p4_files:
            tmp = p4_file.replace("p4", "json")
            reg_str = ".*{}".format(tmp)
            sh('find -type f -regex {} | xargs rm -f'.format(reg_str))

        if args.clean_dir:
            return

    app = AppRunner(args.config,
                    cli_enabled=args.cli,
                    empty_p4=args.empty_p4,
                    log_dir=args.log_dir,
                    pcap_dir=args.pcap_dir,
                    verbosity=args.verbosity)                  
    app.run_app()


if __name__ == '__main__':
    main()