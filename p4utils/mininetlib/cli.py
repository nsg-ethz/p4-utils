"""__ https://github.com/mininet/mininet/blob/master/mininet/cli.py

This module is an extension of `mininet.cli`__. It provides a CLI interface that the user can enable
using the :py:class:`~p4utils.mininetlib.network_API.NetworkAPI` or the JSON network configuration file.
If enabled, the CLI starts right after the network boot and provides useful commands.
"""

import os
import sys
import traceback as tbk
from functools import wraps
from mininet.cli import CLI

from p4utils.utils.helper import *
from p4utils.mininetlib.log import debug, info, output, warning, error, critical


def exception_handler(f):
    """Prevents exceptions from terminating the client, but still
    prints them.
    """
    @wraps(f)
    def handle(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except:
            error(*tbk.format_exception(*sys.exc_info()))
            return False
    return handle


class P4CLI(CLI):
    """Client class to interact with the network once it has been created.

    Attributes:
        network_api (:py:class:`~p4utils.mininetlib.network_API.NetworkAPI`): instance of the network orchestrator.
    """

    def __init__(self, network_api, *args, **kwargs):
        self.net_api = network_api
        super().__init__(network_api.net, *args, **kwargs)
        # self.mn stores the Mininet network object according to the parent object

    def getNode(self, node_name):
        """Retrieves the requested node.

        Args:
            node_name (str): node name

        Returns:
            mininet.node.Node: requested node or **None** if no such object was found.
        """
        # Check if the node is in Mininet
        if node_name not in self.mn:
            error('Node {} not found in the network.\n'.format(node_name))
            return None
        node = self.mn[node_name]
        return node

    def getP4Switch(self, node_name):
        """Retrieves the requested P4 Switch.

        Args:
            node_name (string): P4 switch name

        Returns:
            mininet.node.Node: requested node or **None** if no such object was found.
        """
        node = self.getNode(node_name)

        if node is None:
            return None
        else:
            isP4Switch = get_node_attr(node, 'isP4Switch', False)
            if not isP4Switch:
                error('P4 Switch {} not found in the network\n'.format(node_name))
                return None
            else:
                return node

    @exception_handler
    def do_p4switch_stop(self, line=""):
        """Stops execution of the specified P4 switch.

        **Usage**::

            mininet> p4switch_stop <p4switch name>
        """
        switch_name = parse_line(line)

        # Check args validity
        if not switch_name or len(switch_name) > 1:
            error('Wrong syntax.\n')
            error('usage: p4switch_stop <p4switch name>\n')
            return False

        switch_name = switch_name[0]
        p4switch = self.getP4Switch(switch_name)

        if p4switch is None:
            error('usage: p4switch_stop <p4switch name>\n')
            return False

        p4switch.stop_p4switch()

    @exception_handler
    def do_p4switch_start(self, line=""):
        """Starts a P4 switch.

        **Usage**::

            mininet> p4switch_start <p4switch name> [--p4src <path>] [--cmds <path>]

        Note:
            This command also allows to specify new configuration files for the switch:

            - ``--p4src`` provides a new P4 source,
            - ``--cmds`` provides a new command file.
        """
        args = parse_line(line)

        # Check args validity
        if len(args) > 5:
            error('Wrong syntax.\n')
            error(
                'usage: p4switch_start <p4switch name> [--p4src <path>] [--cmds <path>]\n')
            return False

        switch_name = args[0]

        p4switch = self.getP4Switch(switch_name)

        if p4switch is None:
            error('usage: p4switch_start <p4switch name>\n')
            return False

        # Check if switch is running
        if p4switch.switch_started():
            error('P4 Switch already running, stop it first: p4switch_stop {} \n'.format(
                switch_name))
            return False

        # Check if new P4 source file has been provided
        p4_src = get_node_attr(p4switch, 'p4_src')
        if '--p4src' in args:
            p4_src = args[args.index('--p4src') + 1]
            # Check if file exists
            if not os.path.exists(p4_src):
                error('File Error: P4 source {} does not exist\n'.format(p4_src))
                return False
            # Check if its not a file
            if not os.path.isfile(p4_src):
                error('File Error: p4source {} is not a file\n'.format(p4_src))
                return False
        if p4_src is not None:
            compiler = get_by_attr(
                'p4_src', os.path.realpath(p4_src),
                self.net_api.compilers)
            # If a compiler for the same p4_src has been found
            if compiler is not None:
                # If new file has been provided
                if compiler.new_source():
                    debug('New p4 source file detected!\n')
                    compiler.compile()
                else:
                    debug('P4 source already compiled!\n')
            # If this file is compiled for the first time
            elif self.net_api.modules['comp'] is not None:
                debug('New p4 source file detected!\n')
                compiler = self.net_api.modules['comp']['class'](
                    p4_src=p4_src, **self.net_api.modules['comp']['kwargs'])
                compiler.compile()
                self.net_api.compilers.append(compiler)
            else:
                error('No compiler module provided!\n')
                return False

        # Start switch
        p4switch.start()

        cmd_path = None
        # Check if new cmd file has been provided
        if '--cmds' in args:
            cmd_path = args[args.index("--cmds") + 1]
            # Check if file exists
            if not os.path.exists(cmd_path):
                error(
                    'File Error: command file {} does not exist\n'.format(
                        cmd_path))
                return False
            # Check if its not a file
            if not os.path.isfile(cmd_path):
                error(
                    'File Error: command file {} is not a file\n'.format(
                        cmd_path))
                return False
        if cmd_path is not None:
            client = get_by_attr('sw_name', switch_name,
                                 self.net_api.sw_clients)
            # If a client is present
            if client is not None:
                client.set_conf(cmd_path)
                client.configure()
            # If the switch has no client yet
            elif self.net_api.modules['sw_cli'] is not None:
                thrift_port = get_node_attr(p4switch, 'thrift_port')
                if thrift_port is not None:
                    client = self.net_api.modules['sw_cli']['class'](sw_name=switch_name,
                                                                     thrift_port=thrift_port,
                                                                     **self.net_api.modules['sw_cli']['kwargs'])
                    client.set_conf(cmd_path)
                    client.configure()
                    self.net_api.sw_clients.append(client)
                else:
                    error(
                        'Switch {} has not thrift server enabled.\n'.format(
                            switch_name))
                    return False
            else:
                error('No client module provided!\n')
                return False

    @exception_handler
    def do_p4switch_reboot(self, line=""):
        """Reboots a P4 switch.

        **Usage**::

            mininet> p4switch_reboot <p4switch name> [--p4src <path>] [--cmds <path>]

        Note:
            This command also allows to specify new configuration files for the switch:

            - ``--p4src`` provides a new P4 source,
            - ``--cmds`` provides a new command file.
        """
        if not line or len(parse_line(line)) > 5:
            error(
                'usage: p4switch_reboot <p4switch name> [--p4src <path>] [--cmds <path>]\n')
            return False
        else:
            switch_name = parse_line(line)[0]
            self.do_p4switch_stop(line=switch_name)
            self.do_p4switch_start(line=line)

    @exception_handler
    def do_p4switches_reboot(self, line=""):
        """Reboots all P4 switches with new program.

        **Usage**::

            mininet> p4switches_reboot [--p4src <path>] [--cmds <path>]

        Note:
            This command also allows to specify the same 
            new configuration files for all the switches:

            - ``--p4src`` provides a new P4 source,
            - ``--cmds`` provides a new command file.
        """
        if len(parse_line(line)) > 4:
            error(
                'usage: p4switches_reboot [--p4src <path>] [--cmds <path>]\n')
            return False
        else:
            for sw in self.mn.p4switches:
                switch_name = sw.name
                self.do_p4switch_stop(line=switch_name)

                tmp_line = switch_name + " " + line
                self.do_p4switch_start(line=tmp_line)

            # Run scripts
            if isinstance(self.net_api.scripts, list):
                for script in self.net_api.scripts:
                    if script["reboot_run"]:
                        info("Exec Script: {}\n".format(script["cmd"]))
                        run_command(script["cmd"], script["out_file"])

    @exception_handler
    def do_test_p4(self, line=""):
        """Tests start stop functionalities.

        **Usage**::

            mininet> test_p4
        """
        self.do_p4switch_stop("s1")
        self.do_p4switch_start("s1")
        self.do_p4switch_reboot("s1")
        self.do_p4switches_reboot()

    @exception_handler
    def do_printSwitches(self, line=""):
        """Prints the names of all switches.

        **Usage**::

            mininet> printSwitches
        """
        for sw in self.mn.p4switches:
            output(sw.name+'\n')

    @exception_handler
    def do_pingset(self, line=""):
        """Pings between the hosts in the set.

        **Usage**::

            mininet> pingset <host1> ... <hostN>
        """
        hosts_names = line.strip().split()
        hosts = [x for x in self.mn.hosts if x.name in hosts_names]
        self.mn.ping(hosts=hosts, timeout=1)

    @exception_handler
    def do_task(self, line=""):
        """Executes a task on the given host. 

        **Usage**::

            mininet> task <node> <start> <duration> <exe> [<arg1>] ... [<argN>] [--mod <module>] [--<key1> <kwarg1>] ... [--<keyM> <kwargM>]

        Note:
            The starting delay (specified with ``<start>``) is taken with 
            respect to the current time. The deafult module in which functions
            are looked up is :py:mod:`p4utils.utils.traffic_utils`. A different
            module can be specified in the command with ``--mod <module>``.
        """
        args, kwargs = parse_task_line(line)
        node = args[0]
        if self.getNode(node) is not None:
            if not self.net_api.hasScheduler(node):
                self.net_api.enableScheduler(node)
                self.net_api.start_scheduler(node)
            self.net_api.addTask(*args, enableScheduler=False, **kwargs)
            self.net_api.distribute_tasks()
        else:
            error('Node {} does not exist!\n'.format(node))
            return False

    @exception_handler
    def do_enable_scheduler(self, line=""):
        """Enables the :py:class:`~p4utils.utils.task_scheduler.TaskServer` on a node.

        **Usage**::

            mininet> enable_scheduler [<node>] [--path <dir>]

        Note:
            The directory where the socket file will be placed can be specified
            using ``--path <dir>``.
        """
        args = parse_line(line)
        node = args[0]
        if self.getNode(node) is not None:
            if len(args) > 2:
                error('usage: enable_scheduler [<node>] [--path <dir>]\n')
                return False
            else:
                if not self.net_api.hasScheduler(node):
                    if len(args) == 2:
                        try:
                            self.net_api.enableScheduler(node, path=args[1])
                            self.net_api.start_scheduler(node)
                        except Exception as e:
                            error(e+'\n')
                            return False
                    else:
                        try:
                            self.net_api.enableScheduler(node)
                            self.net_api.start_scheduler(node)
                        except Exception as e:
                            error(e+'\n')
                            return False
                else:
                    error(
                        'Node {} has already a task scheduler running.\n'.format(node))
                    return False
        else:
            error('Node {} does not exist!\n'.format(node))
            return False
