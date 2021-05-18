import os
from mininet.cli import CLI
from mininet.log import info, output, error, warn, debug

from p4utils.utils.helper import *


class P4CLI(CLI):

    def __init__(self, network_api, *args, **kwargs):
        """
        Attributes:
            network_api: instance of NetworkAPI
        """
        self.net_api = network_api
        super().__init__(network_api.net, *args, **kwargs)
        # self.mn stores the Mininet network object according to the parent object

    def getNode(self, node_name):
        """
        Return the requested node.

        Arguments:
            node_name (string): name of the P4 Switch
        
        Returns:
            node (Mininet node object): requested node or None if no such object was found
        """
        # Check if the node is in Mininet
        if node_name not in self.mn:
            error('Node {} not found in the network.\n'.format(node_name))
            return None
        node = self.mn[node_name]
        return node

    def getP4Switch(self, node_name):
        """
        Return the requested P4 Switch.
        
        Arguments:
            node_name (string): name of the P4 Switch
        
        Returns:
            p4switch (Mininet node object): requested node or None if no such object was found
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

    def do_p4switch_stop(self, line=""):
        """Stop simple switch from switch namespace."""
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

    def do_p4switch_start(self, line=""):
        """Start again simple switch from namespace."""
        args = parse_line(line)

        # Check args validity
        if len(args) > 5:
            error('Wrong syntax.\n')
            error('usage: p4switch_start <p4switch name> [--p4src <path>] [--cmds <path>]\n')
            return False

        switch_name = args[0]

        p4switch = self.getP4Switch(switch_name)

        if p4switch is None:
            error('usage: p4switch_start <p4switch name>\n')
            return False

        # Check if switch is running
        if p4switch.switch_started():
            error('P4 Switch already running, stop it first: p4switch_stop {} \n'.format(switch_name))
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
            compiler = get_by_attr('p4_src', os.path.realpath(p4_src), self.net_api.compilers)
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
                compiler = self.net_api.modules['comp']['class'](p4_src=p4_src,
                                                                 **self.net_api.modules['comp']['kwargs'])
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
                error('File Error: command file {} does not exist\n'.format(cmd_path))
                return False
            # Check if its not a file
            if not os.path.isfile(cmd_path):
                error('File Error: command file {} is not a file\n'.format(cmd_path))
                return False
        if cmd_path is not None:
            client = get_by_attr('sw_name', switch_name, self.net_api.sw_clients)
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
                    error('Switch {} has not thrift server enabled.\n'.format(switch_name))
                    return False
            else:
                error('No client module provided!\n')
                return False

    def do_p4switch_reboot(self, line=""):
        """Reboot a P4 switch with a new program."""
        if not line or len(parse_line(line)) > 5:
            error('usage: p4switch_reboot <p4switch name> [--p4src <path>] [--cmds <path>]\n')
            return False
        else:
            switch_name = parse_line(line)[0]
            self.do_p4switch_stop(line=switch_name)
            self.do_p4switch_start(line=line)

    def do_p4switches_reboot(self, line=""):
        """
        Reboot all P4 switches with new program.

        Note:
            If you provide a P4 source code or cmd, all switches will have the same.
        """
        if len(parse_line(line)) > 4:
            error('usage: p4switches_reboot [--p4src <path>] [--cmds <path>]\n')
            return False
        else:
            for sw in self.mn.p4switches:
                switch_name = sw.name
                self.do_p4switch_stop(line=switch_name)

                tmp_line = switch_name + " " +line
                self.do_p4switch_start(line=tmp_line)

            # Run scripts
            if isinstance(self.net_api.scripts, list):
                for script in self.net_api.scripts:
                    if script["reboot_run"]:
                        info("Exec Script: {}\n".format(script["cmd"]))
                        run_command(script["cmd"])

    def do_test_p4(self, line=""):
        """Tests start stop functionalities."""
        self.do_p4switch_stop("s1")
        self.do_p4switch_start("s1")
        self.do_p4switch_reboot("s1")
        self.do_p4switches_reboot()

    def do_printSwitches(self, line=""):
        """Print names of all switches."""
        for sw in self.mn.p4switches:
            print(sw.name)

    def do_pingset(self ,line=""):
        """Ping between the hosts in the set."""
        hosts_names = line.strip().split()
        hosts = [x for x in self.mn.hosts if x.name in hosts_names]
        self.mn.ping(hosts=hosts, timeout=1)

    def do_task(self, line=""):
        """
        Execute a task on the given host. The starting
        delay is taken with respect to the current time.

        For the details check the function parse_task_line
        in p4utils.utils.helper.
        """
        args, kwargs = parse_task_line(line)
        node = args[0]
        if self.getNode(node) is not None:
            self.net_api.addTask(*args, enableScheduler=False, **kwargs)
            if not self.net_api.hasScheduler(node):
                self.net_api.enableScheduler(node)
                self.net_api.start_scheduler(node)
            self.net_api.distribute_tasks()
        else:
            error('Node {} does not exist!\n'.format(node))
            return False

    def do_enable_scheduler(self, line=""):
        """
        Enable the TaskScheduler on a node.
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
                    error('Node {} has already a task scheduler running.\n'.format(node))
                    return False
        else:
            error('Node {} does not exist!\n'.format(node))
            return False
