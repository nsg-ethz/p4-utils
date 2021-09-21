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

"""This module is responsible for the legacy network configuration method that makes
use of JSON files. Indeed, it uses the information contained within it to start and
configure all the components of the virtualized network.
"""

import argparse
from copy import deepcopy
from mininet.log import debug, info, output, warning, error
from mininet.clean import cleanup, sh

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
    """Class used to run P4 applications from a JSON configuration file.

    The ``AppRunner`` creates a *Mininet* network reading information from the JSON
    configuration file. It also specifies whether logs and sniffed packets are to be
    saved on the disk at some location.

    Args:
        conf_file (str): a JSON file which describes the *Mininet* topology
        cli_enabled (bool): enable *Mininet* CLI
        log_dir (str): directory for *Mininet* log files
        pcap_dir (str): directory where to store pcap files
        verbosity (str): amount of information shown during the execution

    .. _verbosity:

    Possible **verbosity** values, listed from the most to less verbose, are the following:

    - ``debug``
    - ``info``
    - ``output``
    - ``warning``
    - ``warn``
    - ``error``
    - ``critical``

    Example:
        The structure of the **JSON** network configuration file parsed by the ``AppRunner`` is
        the following::

            {
                "p4_src": <path to gobal p4 source> (string),
                "cli": <true|false> (bool),
                "pcap_dump": <true|false> (bool),
                "enable_log": <true|false> (bool),
                "tasks_file": <path to the tasks file> (string),
                "host_node":
                {
                    "file_path": <path to module> (string),
                    "module_name": <module file name> (string),
                    "object_name": <module object name> (string)
                },
                "switch_node":
                {
                    "file_path": <path to module> (string),
                    "module_name": <module file name> (string),
                    "object_name": <module object name> (string)
                },
                "router_node":
                {
                    "file_path": <path to module> (string),
                    "module_name": <module file name> (string),
                    "object_name": <module object name> (string)
                },
                "compiler_module":
                {
                    "file_path": <path to module> (string),
                    "module_name": <module file name> (string),
                    "object_name": <module object name> (string),
                    "options": <options passed to init> (dict)
                },
                "client_module":
                {
                    "file_path": <path to module> (string),
                    "module_name": <module file name> (string),
                    "object_name": <module object name> (string),
                    "options": <options passed to init> (dict)
                },
                "mininet_module":
                {
                    "file_path": <path to module> (string),
                    "module_name": <module file name> (string),
                    "object_name": <module object name> (string)
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
                    "assignment_strategy": <assignment strategy> (string),
                    "default":
                    {
                        <default links and hosts configurations, see parse_links>
                    },
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

        Inside the network configuration file, several modules and nodes
        JSON objects can be present. These are the possible values:
        
        - __ #p4utils.p4run.AppRunner.host_node

          ``host_node`` loads an extension to *Mininet* node class into the `homonymous 
          attribute`__. 
        - __ #p4utils.p4run.AppRunner.switch_node

          ``switch_node`` loads an extension to *Mininet* switch node class into the 
          `homonymous attribute`__.
        - __ #p4utils.p4run.AppRunner.router_node

          ``router_node`` loads an extension to *Mininet* node class 
          into the `homonymous attribute`__.
        - ``mininet_module`` loads an extension to *Mininet* network class.
        - ``compiler_module`` loads the external P4 compiler class.
        - ``client_module`` loads the external *Thrift* client class.

    Note: 
        __ p4utils.utils.helper.html#p4utils.utils.helper.load_custom_object
        
        None of the modules or nodes are mandatory. In case they are not specified,
        default settings will be used. For further information about how these modules
        are imported and the related JSON syntax, please check out `this`__ helper function.

    Attributes:
        cli_enabled (:py:class:`bool`)       : enable an extension to *Mininet* CLI after the network starts.
        log_enabled (:py:class:`bool`)       : enable saving log files to the disk.
        log_dir (:py:class:`str`)            : directory used to store log files.
        pcap_dump (:py:class:`bool`)         : generate ``.pcap`` files for interfaces.
        pcap_dir (:py:class:`str`)           : directory where to store ``.pcap`` files.
        hosts (:py:class:`dict`)             : dictionary of host and their properties.
        switches (:py:class:`dict`)          : dictionary of switches and their properties.
        routers (:py:class:`dict`)           : dictionary of routers and their properties.
        links (:py:class:`dict`)             : dictionary of mininet links and their properties.
        clients (:py:class:`list`)           : list of *Thrift* clients (one per P4 switch) to populate tables.
        compilers (:py:class:`list`)         : list of compiler instances (one per P4 source provided) to compile P4 code.
        conf (:py:class:`dict`)              : parsed configuration from the JSON configuration file.
        net (:py:class:`mininet.net.Mininet`): network instance implemented using an extension to *Mininet* network class.
        host_node (:py:class:`type`)         : extension to *Mininet* node class used as default host class.
        switch_node (:py:class:`type`)       : extension to *Mininet* switch node class used as default switch class.
        router_node (:py:class:`type`)       : extension to *Mininet* node class used as default router class.
    """

    def __init__(self, conf_file,
                 cli_enabled=True,
                 log_dir=None,
                 pcap_dir=None,
                 verbosity='info'):
        
        super().__init__()

        self.setLogLevel(verbosity)

        # Read JSON configuration file
        info('Reading JSON configuration file...\n')
        debug('Opening file {}\n'.format(conf_file))
        if not os.path.isfile(conf_file):
            raise FileNotFoundError("{} is not in the directory!".format(os.path.realpath(conf_file)))
        self.conf = load_conf(conf_file)

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
        self.execute_scripts()

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
        """Parses hosts from the JSON configuration files and add 
        them to the network initializer.

        Args:
            unparsed_host (dict): dictionary of hosts and properties retrieved from
                                  the JSON network configuration file

        Example:
            Hosts have the following description in the ``topology`` field of the 
            JSON network configuration file::

                "hosts":
                {
                    host_name:
                    {
                        "scheduler": <true|false> (bool) (*),
                        "socket_path": <dir to socket file> (string) (*),
                        "defaultRoute": "via <gateway ip>" (string) (*),
                        "dhcp": <true|false> (bool) (*),
                        "log_enabled" : <true|false> (bool) (*),
                        "log_dir": <log path for host> (string) (*),
                        "host_node": <custom host node> (dict) (*)
                    },
                    ...
                }

        Note:
            None of the fields marked with ``(*)`` is mandatory. If they are not specified
            default values will be used.
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
        """Parses the switches and adds them to the network.

        Args:
            unparsed_switches (dict): dictionary of switches and properties retrieved from
                                      the JSON network configuration file

        Example:
            Switches have the following description in the ``topology`` field of the 
            JSON network configuration file::
        
                "switches":
                {
                    switch_name:
                    {
                        "p4_src": <path to p4 program> (string) (*),
                        "cpu_port": <true|false> (bool) (*),
                        "cli_input": <path to cli input file> (string) (*),
                        "switch_node": <custom switch node> (dict) (*),
                        "log_enabled" : <true|false> (bool) (*),
                        "log_dir": <log path for switch binary> (string) (*),
                        "pcap_dump": <true|false> (bool) (*),
                        "pcap_dir": <path for pcap files> (string) (*),
                        "sw_bin": <switch binary> (string) (*),
                        "thrift_port": <thrift port> (int) (*),
                        "grpc_port": <grpc port> (int) (*)
                    },
                    ...
                }

        Note:
            None of the fields marked with ``(*)`` is mandatory. If they are not specified
            default values will be used.
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
        """Parse hosts and add them to the network. Hosts have
        the following structure:

        Args:
            unparsed_routers (dict): dictionary of routers and properties retrieved from
                                     the JSON network configuration file

        Example:
            Routers have the following description in the ``topology`` field of the 
            JSON network configuration file::

                "routers":
                {
                    router_name:
                    {
                        "int_conf": <path to the router's integrate configuration file> (string),
                        "conf_dir": <path to the directory which contains the folder 
                                    (named after the router) with the configuration 
                                    files for all the daemons> (string),
                        "router_node": <custom router node> (dict) (*),
                        "zebra": <true|false> (bool) (*),
                        "bgpd": <true|false> (bool) (*),
                        "ospfd": <true|false> (bool) (*),
                        "ospf6d": <true|false> (bool) (*),
                        "ripd": <true|false> (bool) (*),
                        "ripngd": <true|false> (bool) (*),
                        "isisd": <true|false> (bool) (*),
                        "pimd": <true|false> (bool) (*),
                        "ldpd": <true|false> (bool) (*),
                        "nhrpd": <true|false> (bool) (*),
                        "eigrpd": <true|false> (bool) (*),
                        "babeld": <true|false> (bool) (*),
                        "sharpd": <true|false> (bool) (*),
                        "staticd": <true|false> (bool) (*),
                        "pbrd": <true|false> (bool) (*),
                        "bfdd": <true|false> (bool) (*),
                        "fabricd" : <true|false> (bool) (*)
                    },
                    ...
                }

        Note:
            None of the fields marked with ``(*)`` is mandatory. If they are not specified
            default values will be used. Moreover, if ``int_conf`` is specified,
            then ``conf_dir`` is ignored.
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
        """Load a list of links descriptions of the form.

        Args:
            uparsed_links (list): list of links and properties retrieved from
                                  the JSON network configuration file

        Example:
            Links have the following description in the ``topology`` field of the 
            JSON network configuration file::

                "links":
                [
                    [
                        node1,
                        node2, 
                        { 
                            "weight": <link weight> (int) (*),
                            "port1": <number of port1> (int) (*),
                            "port2": <number of port2> (int) (*),
                            "intfName1": <name of the interface1> (string) (*),
                            "intfName2": <name of the interface2> (string) (*),
                            "addr1": <mac address of interface1> (string) (*),
                            "addr2": <mac address of interface2> (string) (*),
                            "params1": <parameters for interface1> (dict) (*),
                            "params2": <parameters for interface2> (dict) (*),
                            "bw": <bandwidth weight> (int) (*),
                            "delay": <transmit delay> (int) (*),
                            "loss": <link data loss> (float) (*),
                            "max_queue_size": <max queue size> (int) (*)
                        }
                    ],
                    ...
                ]

        One can also specify default values for some links and hosts configuration parameters.
        In particular, this can be done by putting the following structure in the ``topology`` field of the 
        JSON network configuration file::

            "default":
            {
                "weight": <weight> (int) (*),
                "bw": <bandwidth> (int) (*),
                "delay": <transmit_delay> (int) (*),
                "loss": <loss> (float) (*),
                "max_queue_size": <max_queue_size> (int) (*),
                "auto_arp_tables": <true|false> (bool) (*),
                "auto_gw_arp": <true|false> (bool) (*)
            }

        Note:
            None of the fields marked with ``(*)`` is mandatory. If they are not specified
            default values will be used.
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

    def execute_scripts(self):
        """Executes the script listed in the JSON network configuration file."""
        if isinstance(self.conf.get('exec_scripts'), list):
            for script in self.conf.get('exec_scripts'):
                self.execScript(script['cmd'], reboot=script.get('reboot_run', False))


def get_args():
    """Parses command line options.

    Returns:
        argparse.Namespace: namespace containing all the argument parsed.

    Here is a complete list of the command line invocation options available with ``p4run``:

    - ``--config`` is the path to configuration (if it is not specified,
      it is assumed to be ``./p4app.json``).
    - ``--log-dir`` is the path to log files (if it is not specified,
      it is assumed to be ``./log``).
    - ``--pcap-dir`` is the path to the ``.pcap`` files generated for each switch interface
      (if it is not specified, it is assumed to be ``./pcap``).
    - __ verbosity_
    
      ``--verbosity`` specifies the desired verbosity of the output (if it is not specified,
      it is assumed to be set to ``info``). Valid verbosity values are listed `here`__.
    - ``--no-cli`` disables the *Mininet* client (it is enabled by default).
    - ``--clean`` cleans old log files, if specified.
    - ``--clean-dir`` cleans old log files and closes, if specified.
    """

    cwd = os.getcwd()
    default_log = os.path.join(cwd, 'log')
    default_pcap = os.path.join(cwd, 'pcap')

    parser = argparse.ArgumentParser()

    parser.add_argument('--config', help='Path to configuration.',
                        type=str, required=False, default='./p4app.json')
    parser.add_argument('--log-dir', help='Generate logs in the specified folder.',
                        type=str, required=False, default=default_log)
    parser.add_argument('--pcap-dir', help='Generate .pcap files for interfaces.',
                        type=str, required=False, default=default_pcap)
    parser.add_argument('--verbosity', help='Set messages verbosity.',
                        type=str, required=False, default='info')
    parser.add_argument('--no-cli', help='Do not run the Mininet CLI.',
                        action='store_true', required=False, default=False)
    parser.add_argument('--clean', help='Cleans old log files.',
                        action='store_true', required=False, default=False)
    parser.add_argument('--clean-dir', help='Cleans old log files and closes.',
                        action='store_true', required=False, default=False)             

    return parser.parse_args()


def main():
    """Cleans up files created by old executions and starts the virtual network."""

    args = get_args()

    # Cleanup
    cleanup()
    bridges = sh("brctl show | awk 'FNR > 1 {print $1}'").splitlines()
    for bridge in bridges:
        sh("ifconfig {} down".format(bridge))
        sh("brctl delbr {}".format(bridge))

    if args.clean or args.clean_dir:
        # Removes first level pcap and log dirs
        sh("rm -rf %s" % args.pcap_dir)
        sh("rm -rf %s" % args.log_dir)
        # Tries to recursively remove all pcap and log dirs if they are named 'log' and 'pcap'
        sh('find -type d -regex ".*pcap" | xargs rm -rf')
        sh('find -type d -regex ".*log" | xargs rm -rf')
        # Removes topologies files
        sh('find -type f -regex ".*topology.json" | xargs rm')
        # Remove compiler outputs
        sh('find -type f -regex ".*\(p4i\|p4rt\)" | xargs rm')

        # Remove all the jsons that come from a p4
        out = sh('find -type f -regex ".*p4"')
        p4_files = [x.split("/")[-1].strip() for x in out.split("\n") if x]
        for p4_file in p4_files:
            tmp = p4_file.replace("p4", "json")
            reg_str = ".*{}".format(tmp)
            sh('find -type f -regex {} | xargs rm -f'.format(reg_str))

        if args.clean_dir:
            return

    app = AppRunner(args.config,
                    cli_enabled=(not args.no_cli),
                    log_dir=args.log_dir,
                    pcap_dir=args.pcap_dir,
                    verbosity=args.verbosity)


if __name__ == '__main__':
    main()