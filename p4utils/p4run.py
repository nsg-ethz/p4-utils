#!/usr/bin/env python2
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
# Further work: Fabian Schleiss (fabian.schleiss@alumni.ethz.ch)
# Further work: Edgar Costa Molero (cedgar@ethz.ch)
#
import os
import sys
import argparse
from time import sleep
import importlib
from ipaddress import ip_interface

from p4utils import *
from p4utils.mininetlib.p4net import P4Mininet
from p4utils.mininetlib.p4_mininet import P4Switch, P4Host, P4RuntimeSwitch, configureP4Switch
from p4utils.utils.topology import Topology as DefaultTopoDB
from p4utils.mininetlib.cli import P4CLI
from p4utils.mininetlib.apptopo import AppTopoStrategies as DefaultTopo
from p4utils.mininetlib.appcontroller import AppController as DefaultController
from p4utils.utils.utils import run_command,compile_all_p4, load_conf, CompilationError, read_entries, add_entries, cleanup

#from mininet.link import TCLink
from p4utils.mininetlib.link import TCLink
from mininet.log import setLogLevel, info
from mininet.clean import sh



class AppRunner(object):
    """Class for running P4 applications.

    Attributes:
        log_dir (string): directory for mininet log files
        pcap_dump (bool): determines if we generate pcap files for interfaces
        quiet (bool): determines if we print script debug messages

        hosts (list<string>): list of mininet host names
        switches (dict<string, dict>): mininet host names and their associated properties
        links (list<dict>) : list of mininet link properties

        switch_json (string): json of the compiled p4 example
        bmv2_exe (string): name or path of the p4 switch binary

        conf (dict<string, dict>): parsed configuration from conf_file
        topo (Topo object): the mininet topology instance
        net (Mininet object): the mininet instance
    """

    def __init__(self, conf_file, log_dir, pcap_dir,
                 cli_enabled=True, quiet=False):
        """Initializes some attributes and reads the topology json.

        Args:
            conf_file (string): A json file which describes the mininet topology.
            switch_json (string): Path to a compiled p4 json to run in bmv2.
            log_dir (string): Path to a directory for storing logs.
            bmv2_exe (string): Path to the p4 behavioral model binary.
            cli_enabled (bool): Enable mininet CLI.
            pcap_dump (bool): Enable generation of pcap files for interfaces.
            quiet (bool): Disable script debug messages.
        """

        self.quiet = quiet
        self.logger('Reading configuration file.')
        self.conf_file = conf_file
        if not os.path.isfile(conf_file):
            raise Exception("Configuration %s is not in the directory!" % conf_file)
        self.conf = load_conf(conf_file)

        self.cli_enabled = cli_enabled
        self.pcap_dir = pcap_dir
        self.log_dir = log_dir
        self.bmv2_exe = str(self.conf.get('switch', DEFAULT_SWITCH))


        # Clean switches
        sh("killall %s" % self.bmv2_exe)

        # get configurations
        self.log_enabled = self.conf.get("enable_log", False)
        # Ensure that all the needed directories exist and are directories
        if self.log_enabled:
            if not os.path.isdir(self.log_dir):
                if os.path.exists(self.log_dir):
                    raise Exception("'%s' exists and is not a directory!" % self.log_dir)
                os.mkdir(self.log_dir)

        self.pcap_dump = self.conf.get("pcap_dump", False)
        if self.pcap_dump:
            if not os.path.isdir(self.pcap_dir):
                if os.path.exists(self.pcap_dir):
                    raise Exception("'%s' exists and is not a directory!" % self.pcap_dir)
                os.mkdir(self.pcap_dir)

        # load topology
        topology = self.conf.get('topology', False)
        if not topology:
            raise Exception("topology to create is not defined in %s" % self.conf)

        self.hosts = topology['hosts']
        self.switches = topology['switches']
        self.links = self.parse_links(topology['links'])

        os.environ['P4APP_LOGDIR'] = log_dir

        # Setting default builders
        self.app_topo = DefaultTopo
        self.app_controller = DefaultController
        self.app_topodb = DefaultTopoDB
        self.app_mininet = P4Mininet

        if self.conf.get('topo_module',None):
            self.app_topo = self.load_custom_object('topo_module')

        if self.conf.get('controller_module', None):
            self.app_controller = self.load_custom_object('controller_module')

        if self.conf.get('topodb_module', None):
            self.app_topodb = self.load_custom_object('topodb_module')

        if self.conf.get('mininet_module', None):
            self.app_mininet = self.load_custom_object('mininet_module')

    def load_custom_object(self, object_type):

        file_path = self.conf[object_type].get("file_path", ".")
        sys.path.insert(0, file_path)

        module_name = self.conf[object_type]["module_name"]
        object_name = self.conf[object_type]["object_name"]

        module = importlib.import_module(module_name)
        return getattr(module, object_name)


    def logger(self, *items):
        if not self.quiet:
            print ' '.join(items)

    def formatLatency(self, latency):
        """Helper method for formatting link latencies."""
        if isinstance(latency, (str, unicode)):
            return latency
        else:
            return str(latency) + "ms"

    def parse_links(self, unparsed_links):
        """Given a list of links descriptions of the form [node1, node2, latency, bandwidth, weight]
        with the latency and bandwidth being optional and weight, parses these descriptions
        into dictionaries and store them as self.links.

        Args:
            uparsed_links (array): unparsed links from topology json

        Returns:
            array of parsed link dictionaries
        """
        links = []

        default_delay = None
        default_bw = None
        default_loss = None
        default_queue_length = None
        default_link_weight = 1

        if self.conf['topology'].get('default_delay', None):
            default_delay = self.conf['topology'].get('default_delay', None)

        if self.conf['topology'].get('default_bw', None):
            default_bw = self.conf['topology'].get('default_bw', None)

        if self.conf['topology'].get('default_loss', None):
            default_loss = self.conf['topology'].get('default_loss', None)

        if self.conf['topology'].get('default_queue_length', None):
            default_queue_length = self.conf['topology'].get('default_queue_length', None)

        if self.conf['topology'].get('default_link_weight', None):
            default_link_weight = self.conf['topology'].get('default_link_weight', None)


        for link in unparsed_links:
            # make sure that the endpoints of each link are ordered alphabetically
            node_a, node_b, = link[0], link[1]
            #if node_a > node_b:
            #    node_a, node_b = node_b, node_a

            link_dict = {'node1': node_a,
                         'node2': node_b,
                         'delay': default_delay,
                         'bw': default_bw,
                         'loss': default_loss,
                         'queue_length': default_queue_length,
                         'weight': default_link_weight
                         }
            # parse extra parameters, check if they are not an empty element for
            # example when wanting to set weight but not latency

            if len(link) > 2:
                link_dict.update(link[2])

            # Hosts are not allowed to connect to another host.
            if node_a in self.hosts:
                assert node_b not in self.hosts, 'Hosts should be connected to switches: %s <-> %s link not possible' % (node_a, node_b)

            links.append(link_dict)
        return links


    def run_app(self):
        """Sets up the mininet instance, programs the switches, and starts the mininet CLI.

        This is the main method to run after initializing the object.
        """
        # Initialize mininet with the topology specified by the configuration

        self.create_network()
        self.net.start()
        sleep(1)

        # Some programming that must happen after the network has started
        self.program_hosts()
        self.program_switches()

        # Save mininet topology to a database
        self.save_topology()
        sleep(1)

        self.exec_scripts()

        # Start up the mininet CLI
        if self.cli_enabled or (self.conf.get('cli', False)):
            self.do_net_cli()

        # Stop right after the CLI is exited
        self.net.stop()

    def create_network(self):
        """Create the mininet network object, and store it as self.net.

        Side effects:
            - Mininet topology instance stored as self.topo
            - Mininet instance stored as self.net
        """
        self.logger("Building mininet topology.")
        #compile all p4 programs and give them to every different switch
        try:
            self.switch_to_json = compile_all_p4(self.conf)
        except CompilationError:
            self.logger("Compilation Error")
            sys.exit(0)

        self.topo = self.app_topo(self.hosts, self.switch_to_json, self.links, self.log_dir, self.conf)

        #TODO: this should not be for the entire net, we should support non p4 switches
        switchClass = configureP4Switch(sw_path=self.bmv2_exe,
                                        log_console=self.log_enabled,
                                        pcap_dump=self.pcap_dump, pcap_dir= self.pcap_dir)

        # start P4 Mininet
        self.net = self.app_mininet(topo=self.topo,
                             link=TCLink,
                             host=P4Host,
                             switch=switchClass,
                             controller=None)

    def exec_scripts(self):

        if isinstance(self.conf.get('exec_scripts', None), list):
            for script in self.conf.get('exec_scripts'):
                self.logger("Exec Script: {}".format(script["cmd"]))
                run_command(script["cmd"])

    def program_switches(self):
        """If any command files were provided for the switches, this method will start up the
        CLI on each switch and use the contents of the command files as input.

        Assumes:
            A mininet instance is stored as self.net and self.net.start() has been called.
        """

        #run controller
        controller = self.app_controller(self.conf, self.net, self.log_dir, self.log_enabled)
        controller.start()
        return controller

    def program_hosts(self):
        """Adds static ARP entries and default routes to each mininet host.

        Assumes:
            A mininet instance is stored as self.net and self.net.start() has been called.
        """
        topology = self.conf.get('topology')
        auto_arp_tables = topology.get('auto_arp_tables', True)
        auto_gw_arp = topology.get('auto_gw_arp', True)

        for host_name in self.topo.hosts():
            h = self.net.get(host_name)

            # Ensure each host's interface name is unique, or else
            # mininet cannot shutdown gracefully
            h_iface = h.intfs.values()[0]

            #if there is gateway assigned
            if auto_gw_arp:
                if 'defaultRoute' in h.params:
                    link = h_iface.link
                    sw_iface = link.intf1 if link.intf1 != h_iface else link.intf2
                    gw_ip = h.params['defaultRoute'].split()[-1]
                    h.cmd('arp -i %s -s %s %s' % (h_iface.name, gw_ip, sw_iface.mac))

            if auto_arp_tables:
                #set arp rules for all the hosts in the same subnet
                host_address = ip_interface(u"%s/%d" % (h.IP(), self.topo.hosts_info[host_name]["mask"]))
                for hosts_same_subnet in self.topo.hosts():
                    if hosts_same_subnet == host_name:
                        continue

                    #check if same subnet
                    other_host_address = ip_interface(unicode("%s/%d" % (self.topo.hosts_info[hosts_same_subnet]['ip'],
                                                        self.topo.hosts_info[hosts_same_subnet]["mask"])))

                    if host_address.network.compressed == other_host_address.network.compressed:
                            h.cmd('arp -i %s -s %s %s' % (h_iface.name, self.topo.hosts_info[hosts_same_subnet]['ip'],
                                                          self.topo.hosts_info[hosts_same_subnet]['mac']))

            #if the host is configured to use dhcp
            auto_ip = topology["hosts"][host_name]
            if auto_ip:
                h.cmd('dhclient -r %s' % h_iface.name)
                h.cmd('dhclient %s' % h_iface.name)


    def save_topology(self):
        """Saves mininet topology to database."""
        self.logger("Saving mininet topology to database.")
        self.app_topodb(net=self.net).save("./topology.db")

    def do_net_cli(self):
        """Starts up the mininet CLI and prints some helpful output.

        Assumes:
            A mininet instance is stored as self.net and self.net.start() has been called.
        """
        for switch in self.net.switches:
            if self.topo.isP4Switch(switch.name):
                switch.describe()
        for host in self.net.hosts:
            host.describe()
        self.logger("Starting mininet CLI")
        # Generate a message that will be printed by the Mininet CLI to make
        # interacting with the simple switch a little easier.
        print ''
        print '======================================================================'
        print 'Welcome to the P4 Utils Mininet CLI!'
        print '======================================================================'
        print 'Your P4 program is installed into the BMV2 software switch'
        print 'and your initial configuration is loaded. You can interact'
        print 'with the network using the mininet CLI below.'
        print ''
        print 'To inspect or change the switch configuration, connect to'
        print 'its CLI from your host operating system using this command:'
        print '  %s --thrift-port <switch thrift port>' % DEFAULT_CLI
        print ''
        print 'To view a switch log, run this command from your host OS:'
        print '  tail -f %s/<switchname>.log' % self.log_dir.replace("edgar", "p4")
        print ''
        print 'To view the switch output pcap, check the pcap files in \n %s:' % self.pcap_dir.replace("edgar", "p4")
        print ' for example run:  sudo tcpdump -xxx -r s1-eth1.pcap'
        print ''

        # Start CLI
        P4CLI(self.net, conf_file=self.conf_file, script=self.conf.get("cli_script", None))

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
    parser.add_argument('--quiet', help='Disable script debug messages.',
                        action='store_true', required=False, default=False)
    parser.add_argument('--clean', help='Cleans previous log files',
                        action='store_true', required=False, default=False)
    parser.add_argument('--clean-dir', help='Cleans previous log files and closes',
                        action='store_true', required=False, default=False)

    return parser.parse_args()


def main():

    args = get_args()

    #set logging level
    setLogLevel('info')

    #clean
    cleanup()

    #remove cli logs
    sh('find -type f -regex ".*cli_output.*" | xargs rm')

    if args.clean or args.clean_dir:
        sh("rm -rf %s" % args.pcap_dir)
        sh("rm -rf %s" % args.log_dir)
        sh('find -type f -regex ".*db" | xargs rm')
        sh('find -type f -regex ".*\(p4i\|p4rt\)" | xargs rm')

        #remove all the jsons that come from a p4
        out  = sh('find -type f -regex ".*p4"')
        p4_files = [x.split("/")[-1].strip() for x in out.split("\n") if x]
        for p4_file in p4_files:
            tmp = p4_file.replace("p4", "json")
            reg_str = ".*{}".format(tmp)
            sh('find -type f -regex {} | xargs rm -f'.format(reg_str))

        if args.clean_dir:
            return

    app = AppRunner(args.config, args.log_dir,
                    args.pcap_dir, args.cli, args.quiet)

    app.run_app()


if __name__ == '__main__':
    main()