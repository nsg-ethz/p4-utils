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

import argparse
from copy import deepcopy
from mininet.log import debug, info, output, warning, error
from mininet.clean import sh

from p4utils.utils.helper import *
from p4utils.utils.compiler import P4C as DEFAULT_COMPILER
from p4utils.utils.client import ThriftClient as DEFAULT_CLIENT
from p4utils.mininetlib.node import P4Switch as DEFAULT_SWITCH
from p4utils.mininetlib.node import FRRouter as DEFAULT_ROUTER
from p4utils.mininetlib.node import P4Switch, P4RuntimeSwitch
from p4utils.mininetlib.node import P4Host as DEFAULT_HOST
from p4utils.mininetlib.net import P4Mininet as DEFAULT_NET
from p4utils.mininetlib.network_API import NetworkAPI


class AppRunner(NetworkAPI):
    """
    Class for running P4 applications.
    """

    def __init__(self, conf_file,
                 cli_enabled=True,
                 log_dir=None,
                 pcap_dir=None,
                 verbosity='info'):
        """
        Initializes some attributes and reads the topology json.

        Attributes:
            conf_file (string): a JSON file which describes the mininet topology.
            cli_enabled (bool): enable mininet CLI.
            log_dir (string): directory for mininet log files.
            pcap_dir (string): directory where to store pcap files.
            verbosity (string): see https://github.com/mininet/mininet/blob/57294d013e780cccc6b4b9af151906b382c4d8a7/mininet/log.py#L14

        The following attributes are initialized during the execution and are
        not specified in the constructor:
            pcap_dump (bool)    : determines if we generate pcap files for interfaces.
            hosts (list)        : list of mininet host names.
            switches (dict)     : mininet host names and their associated properties.
            links (list)        : list of mininet link properties.
            clients (list)      : list of clients (one per client-capable switch) to populate tables
            compilers (list)    : list of compilers (one per P4 source provided) to compile P4 code
            conf (dict)         : parsed configuration from conf_file.
            net (Mininet object): the mininet instance.
            *_module (dict/obj) : module dict used to import the specified module (see below)
            *_node (dict/obj)   : node dict uset to import the specified Mininet node (see below)
            
        Modules and nodes available
        Inside self.conf can be present several module configuration objects. These are the possible values:
            - "switch_node" loads the switch node to be used with Mininet (see mininetlib/node.py),
            - "compiler_module" loads the compiler for P4 codes,
            - "host_node" loads the host node to be used with Mininet,
            - "client_module" loads the client to program switches from files.
            - "mininet_module" loads the network module

        Example of JSON structure of conf_file:
        {
            "p4_src": <path to gobal p4 source> (string),
            "cli": <true|false> (bool),
            "pcap_dump": <true|false> (bool),
            "enable_log": <true|false> (bool),
            "tasks_file": <path to the tasks file> (string)
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
            "router_node":
            {
                "file_path": <path to module> (string),
                "module_name": <module file name> (string),
                "object_name": <module object> (string)
            }
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
                    <default links and hosts configurations, see parse_links and parse_hosts>
                }
                "links": 
                [
                    <see parse_links>
                ],
                "hosts": 
                {
                    <see parse_hosts>
                },
                "switches": 
                {
                    <see parse_switch>
                },
                "routers": 
                {
                    <see parse_routers>
                }
            }
        }

        Notice: none of the modules or nodes are mandatory. In case they are not specified,
        default settings will be used.
        """
        
        super().__init__()

        self.setLogLevel(verbosity)

        # Read JSON configuration file
        self.conf_file = conf_file

        info('Reading JSON configuration file...\n')
        debug('Opening file {}\n'.format(self.conf_file))
        if not os.path.isfile(self.conf_file):
            raise FileNotFoundError("{} is not in the directory!".format(os.path.realpath(self.conf_file)))
        self.conf = load_conf(self.conf_file)

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
        # Load default router node
        self.router_node = {}
        router_node = self.conf.get('router_node')
        if router_node is not None:
            self.router_node = load_custom_object(router_node)
        else:
            self.router_node = DEFAULT_ROUTER

        # Load default switch node
        self.switch_node = {}
        switch_node = self.conf.get('switch_node')
        if switch_node is not None:
            self.switch_node = load_custom_object(switch_node)
        else:
            self.switch_node = DEFAULT_SWITCH

        # Load default host node
        self.host_node = {}
        host_node = self.conf.get('host_node')
        if host_node is not None:
            self.host_node = load_custom_object(host_node)
        else:
            self.host_node = DEFAULT_HOST

        ## Modules
        # Load default compiler module
        # Set default options for the compiler
        compiler_kwargs = {
                            'opts': '--target bmv2 --arch v1model --std p4-16',
                            'p4rt': False
                          }
        compiler = DEFAULT_COMPILER
        compiler_module = self.conf.get('compiler_module')
        if compiler_module is not None:
            if compiler_module.get('object_name'):
                compiler = load_custom_object(compiler_module)
            else:
                compiler = DEFAULT_COMPILER
            # Load compiler module default arguments
            compiler_kwargs = compiler_module.get('options', {})
        self.setCompiler(compiler, **compiler_kwargs)

        # Load default client module
        # Set default options for the client
        client_kwargs = {
                            'log_enabled': self.log_enabled,
                            'log_dir': self.log_dir
                        }
        client = DEFAULT_CLIENT
        client_module = self.conf.get('client_module')
        if client_module is not None:
            if client_module.get('object_name'):
                client = load_custom_object(client_module)
            else:
                client = DEFAULT_CLIENT
            # Load client module default arguments
            compiler_kwargs = client_module.get('options', {})
        self.setSwitchClient(client, **client_kwargs)

        # Load default Mininet network
        mininet_module = self.conf.get('mininet_module')
        if mininet_module is not None:
            mininet = load_custom_object(mininet_module)
        else:
            mininet = DEFAULT_NET
        self.setNet(mininet)

        ## Load topology
        topology = self.conf.get('topology')
        if topology is None:
            raise Exception('no topology defined in {}.'.format(self.conf))

        # Import topology components
        unparsed_hosts = topology.get('hosts')
        if unparsed_hosts is not None:
            self.parse_hosts(unparsed_hosts)
        unparsed_switches = topology.get('switches')
        if unparsed_switches is not None:
            self.parse_switches(unparsed_switches)
        unparsed_routers = topology.get('routers')
        if unparsed_routers is not None:
            self.parse_routers(unparsed_routers)
        unparsed_links = topology.get('links')
        if unparsed_links is not None:
            self.parse_links(unparsed_links)

        # Execute scripts
        self._exec_scripts()

        # Set assignment strategy
        assignment_strategy = topology.get('assignment_strategy')
        if assignment_strategy is not None:
            if assignment_strategy == 'l2':
                self.l2()
            elif assignment_strategy == 'l3':
                self.l3()
            elif assignment_strategy == 'mixed':
                self.mixed()
            else:
                warning('Unknown assignment strategy "{}".\n'.format(assignment_strategy))

        # Enable/disable Mininet client
        if self.cli_enabled:
            self.enableCli()
        else:
            self.disableCli()

        tasks_file = self.conf.get('tasks_file')
        if tasks_file is not None:
            # Add tasks file
            self.addTaskFile(tasks_file)

        # Start the network
        self.startNetwork()

    def parse_hosts(self, unparsed_hosts):
        """
        Parse hosts and add them to the network. Hosts have
        the following structure:
        "hosts":
        {
            host_name:
            {
                "scheduler": <true|false> (*)
                "socket_path": <dir to socket file> (*)
                "defaultRoute": "via <gateway ip>" (*)
                "dhcp": <true|false> (*)
                "log_enabled" : <true|false> (bool), (*)
                "log_dir": <log path for switch binary> (string), (*)
                "host_node": custom_switch_node (dict) (*)
            },
            ...
        }

        (*) None of these parameters is mandatory.
        """
        default_params = {
                            'log_enabled': self.log_enabled,
                            'log_dir': self.log_dir,
                            'host_node': deepcopy(self.host_node),
                         }
        for host, custom_params in unparsed_hosts.items():
            # Set general default host options
            params = deepcopy(default_params)

            ## Parse Host node type
            # Set non default node type (the module JSON is converted into a Host object)
            if 'host_node' in custom_params:
                custom_params['cls'] = load_custom_object(custom_params['host_node'])
                # This field is not propagated further
                del custom_params['host_node']
            else:
                params['cls'] = params['host_node']
            # This field is not propagated further
            del params['host_node']

            # Update default parameters with custom ones
            params.update(custom_params)
            self.addHost(host, **params)
    
    def parse_switches(self, unparsed_switches):
        """
        Parse switches and add them to the network. A switch has 
        the following structure inside the topology object
        "switches":
        {
            switch_name:
            {
                "p4_src": path_to_p4_program (string),
                "cpu_port": <true|false> (bool),
                "cli_input": <path to cli input file> (string),
                "switch_node": custom_switch_node (dict) (*),
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
        default_params = {
                            'p4_src': self.conf.get('p4_src'),
                            'switch_node': deepcopy(self.switch_node),
                            'pcap_dump': self.pcap_dump,
                            'pcap_dir': self.pcap_dir,
                            'log_enabled': self.log_enabled,
                            'log_dir': self.log_dir
                         }
        
        for switch, custom_params in unparsed_switches.items():

            # Set general default switch options
            params = deepcopy(default_params)

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

            # Update default parameters with custom ones
            params.update(custom_params)

            if issubclass(params['cls'], P4Switch):
                if issubclass(params['cls'], P4RuntimeSwitch):
                    self.addP4RuntimeSwitch(switch, **params)
                else:
                    self.addP4Switch(switch, **params)
                if params.get('cpu_port', False):
                    self.enableCpuPort(switch)
            else:
                self.addSwitch(switch, **params)

    def parse_routers(self, unparsed_routers):
        """
        Parse hosts and add them to the network. Hosts have
        the following structure:
        "routers":
        {
            router_name:
            {
                "int_conf": <path to the router's integrate configuration file>
                "conf_dir": <path to the directory which contains the folder 
                             (named after the router) with the configuration 
                             files for all the daemons>
                daemon1_name: <true|false> (bool) (*),
                daemon2_name: <true|false> (bool) (*),
                ...
            },
            ...
        }

        Notice that if int_conf is specified, then conf_dir is ignored.

        (*) None of these parameters is mandatory.
        """
        default_params = {
                            'router_node': deepcopy(self.router_node),
                            'zebra': True,
                            'ospfd': True,
                            'staticd': True,
                            'bgpd': True
                         }
        
        for router, custom_params in unparsed_routers.items():
            # Set general default router options
            params = deepcopy(default_params)

            ## Parse Router node type
            # Set non default node type (the module JSON is converted into a Router object)
            if 'router_node' in custom_params:
                custom_params['cls'] = load_custom_object(custom_params['router_node'])
                # This field is not propagated further
                del custom_params['router_node']
            else:
                params['cls'] = params['router_node']
            # This field is not propagated further
            del params['router_node']

            # Update default parameters with custom ones
            params.update(custom_params)
            self.addRouter(router, **params)

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
            "max_queue_size": max_queue_size,
            "auto_arp_tables": <true|false>,
            "auto_gw_arp": <true|false>
        }

        Args:
            uparsed_links (array): unparsed links from topology json
        """
        default_params = self.conf['topology'].get('default', {})

        # Default topology settings
        if default_params.get('auto_arp_tables', True):
            self.enableArpTables()
        else:
            self.disableArpTables()

        if default_params.get('auto_gw_arp', True):
            self.enableGwArp()
        else:
            self.disableGwArp()

        # This field is not propagated further
        if 'auto_arp_tables' in default_params.keys():
            del default_params['auto_arp_tables']
        
        # This field is not propagated further
        if 'auto_gw_arp' in default_params.keys():
            del default_params['auto_gw_arp']

        for link in unparsed_links:
            node1 = link[0]
            node2 = link[1]
            params = deepcopy(default_params)
            # If attributes are present for that link
            if len(link) > 2:
                params.update(link[2])
            self.addLink(node1, node2, **params)

    def _exec_scripts(self):
        """
        Executes the script present in the "exec_scripts" field of self.conf.
        """
        if isinstance(self.conf.get('exec_scripts'), list):
            for script in self.conf.get('exec_scripts'):
                self.execScript(script['cmd'], reboot=script.get('reboot_run', False))


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

    return parser.parse_args()


def main():

    args = get_args()

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
                    log_dir=args.log_dir,
                    pcap_dir=args.pcap_dir,
                    verbosity=args.verbosity)


if __name__ == '__main__':
    main()