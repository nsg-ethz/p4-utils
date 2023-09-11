# Copyright 2013-present Barefoot Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""__ https://github.com/mininet/mininet/blob/master/mininet/node.py

This module is an extension of `mininet.node`__ with customized nodes.
"""

import os
import json
import signal
import tempfile
from psutil import pid_exists
from mininet.node import Node, Host, Switch
from mininet.moduledeps import pathCheck

from p4utils.utils.helper import *
from p4utils.mininetlib.log import debug, info, output, warning, error, critical


SWITCH_START_TIMEOUT = 10
SWITCH_STOP_TIMEOUT = 10


class P4Host(Host):
    """Virtual hosts with custom configuration to work with P4 switches."""

    def __init__(self, *args,
                 log_enabled=False,
                 log_dir='/tmp',
                 **kwargs):

        self.log_enabled = log_enabled
        self.log_dir = log_dir

        super().__init__(*args, **kwargs)

        if self.log_enabled:
            # Make sure that the provided log path is not pointing to a file
            # and, if necessary, create an empty log dir
            if not os.path.isdir(self.log_dir):
                if os.path.exists(self.log_dir):
                    raise NotADirectoryError(
                        "'{}' exists and is not a directory.".format(
                            self.log_dir))
                else:
                    os.mkdir(self.log_dir)

    def config(self, **params):
        """Configures host."""

        r = super().config(**params)

        for off in ['rx', 'tx', 'sg']:
            cmd = '/sbin/ethtool --offload {} {} off'.format(
                self.defaultIntf().name, off)
            self.cmd(cmd)

        # disable IPv6
        self.cmd('sysctl -w net.ipv6.conf.all.disable_ipv6=1')
        self.cmd('sysctl -w net.ipv6.conf.default.disable_ipv6=1')
        self.cmd('sysctl -w net.ipv6.conf.lo.disable_ipv6=1')

        return r

    def describe(self, sw_addr=None, sw_mac=None):
        """Describes host."""

        output('**********\n')
        output('Network configuration for: {}\n'.format(self.name))
        output('Default interface: {}\t{}\t{}\n'.format(
               self.defaultIntf().name,
               self.defaultIntf().IP(),
               self.defaultIntf().MAC()
               ))
        if sw_addr is not None or sw_mac is not None:
            output('Default route to switch: {} ({})\n'.format(sw_addr, sw_mac))
        output('**********\n')


class P4Switch(Switch):
    """P4 virtual switch.

    Args:
        name (str)            : name of the switch
        device_id (int)       : switch unique id
        sw_bin (str)          : switch binary to execute
        json_path (str)       : path to the P4 compiled JSON configuration
        thrift_port (int)     : *Thrift* server's port
        pcap_dump (bool)      : whether to save ``.pcap`` logs to disk
        pcap_dir (str)        : ``.pcap`` files path
        log_enabled (bool)    : whether to save logs to disk
        log_dir (srt)         : log path
        enable_debugger (bool): whether to enable debugger
    """

    def __init__(self, name,
                 device_id,
                 sw_bin='simple_switch',
                 json_path=None,
                 thrift_port=None,
                 pcap_dump=False,
                 pcap_dir=None,
                 log_enabled=False,
                 log_dir='/tmp',
                 enable_debugger=False,
                 priority_queues_num=1,
                 **kwargs):

        if isinstance(device_id, int):
            self.device_id = device_id
        else:
            raise TypeError('device_id is not an integer.')

        kwargs.update(dpid=dpidToStr(self.device_id))

        super().__init__(name, **kwargs)

        self.set_binary(sw_bin)
        self.set_json(json_path)
        self.priority_queues_num = priority_queues_num
        self.pcap_dir = pcap_dir
        self.pcap_dump = pcap_dump
        self.enable_debugger = enable_debugger
        self.log_enabled = log_enabled
        self.log_dir = log_dir
        self.thrift_port = thrift_port
        self.nanomsg = 'ipc:///tmp/bm-{}-log.ipc'.format(self.device_id)
        self.switch_pid = None

        if self.log_enabled:
            # Make sure that the provided log path is not pointing to a file
            # and, if necessary, create an empty log dir
            if not os.path.isdir(self.log_dir):
                if os.path.exists(self.log_dir):
                    raise NotADirectoryError(
                        "'{}' exists and is not a directory.".format(
                            self.log_dir))
                else:
                    os.mkdir(self.log_dir)

        if self.pcap_dump:
            # Make sure that the provided pcap path is not pointing to a file
            # and, if necessary, create an empty pcap dir
            if not os.path.isdir(self.pcap_dir):
                if os.path.exists(self.pcap_dir):
                    raise NotADirectoryError(
                        "'{}' exists and is not a directory.".format(
                            self.pcap_dir))
                else:
                    os.mkdir(self.pcap_dir)

        if self.thrift_listening():
            raise ConnectionRefusedError(
                '{} cannot bind port {} because it is bound by another process.'.
                format(self.name, self.thrift_port))

    def set_binary(self, sw_bin):
        """Sets switch default binary"""
        # Make sure that the provided sw_bin is valid
        pathCheck(sw_bin)
        self.sw_bin = sw_bin

    def set_json(self, json_path):
        """Sets the compiled P4 JSON file."""
        # Make sure that the provided JSON file exists if it is not None
        if json_path and not os.path.isfile(json_path):
            raise FileNotFoundError('Invalid JSON file.')
        else:
            self.json_path = json_path

    def switch_running(self):
        """Checks if the switch process is running."""
        if self.switch_pid is not None:
            return pid_exists(self.switch_pid)
        else:
            return False

    def thrift_listening(self):
        """Checks if a thrift process listens on the thrift port."""
        return check_listening_on_port(self.thrift_port)

    def switch_status(self):
        """Checks if all the switch processes have started correctly."""
        return self.switch_running() and self.thrift_listening()

    def add_arguments(self):
        """Adds arguments to the simple switch process"""
        args = [self.sw_bin]
        for port, intf in list(self.intfs.items()):
            if not intf.IP():
                args.extend(['-i', str(port) + '@' + intf.name])
        if self.pcap_dump:
            if self.pcap_dir:
                args.append('--pcap=' + self.pcap_dir)
            else:
                args.append('--pcap')
        if self.thrift_port:
            args.extend(['--thrift-port', str(self.thrift_port)])
        if self.nanomsg:
            args.extend(['--nanolog', self.nanomsg])
        args.extend(['--device-id', str(self.device_id)])
        if self.json_path:
            args.append(self.json_path)
        else:
            args.append('--no-p4')
        if self.enable_debugger:
            args.append('--debugger')
        if self.log_enabled:
            args.append('--log-console')
        return args
    
    def add_target_arguments(self):
        """Adds switch target options"""
        args = []
        if self.priority_queues_num and int(self.priority_queues_num) > 1:
            args.extend(['--priority-queues', str(self.priority_queues_num)])
        return args

    def start(self, controllers=None):
        """Starts a new P4 switch."""
        info('Starting P4 switch {}.\n'.format(self.name))
        # general switch arguments
        cmd = ' '.join(self.add_arguments())
        # add target specific arguments
        # adds separator
        _target_arguments = self.add_target_arguments()
        if _target_arguments:
            cmd += " -- "
            cmd += ' '.join(self.add_target_arguments())
        #cmd = cmd + "--priority-queues 8"

        info(cmd + "\n")

        with tempfile.NamedTemporaryFile() as f:
            if self.log_enabled:
                self.cmd(cmd + ' > ' + self.log_dir + '/p4s.{}.log'.format(
                    self.name) + ' 2>&1 & echo $! >> ' + f.name)
            else:
                self.cmd(cmd + ' > /dev/null 2>&1 & echo $! >> ' + f.name)
            self.switch_pid = int(f.read())

        debug('P4 switch {} PID is {}.\n'.format(self.name, self.switch_pid))
        if not wait_condition(self.switch_status, True,
                              timeout=SWITCH_START_TIMEOUT):
            raise ChildProcessError(
                'P4 switch {} did not start correctly. Check the switch log file.'.format(self.name))
        info('P4 switch {} has been started.\n'.format(self.name))

    def stop(self, deleteIntfs=True):
        """Stops the P4 switch."""
        if not deleteIntfs:
            info('Stopping P4 switch {}.\n'.format(self.name))
        if self.switch_running():
            os.kill(self.switch_pid, signal.SIGKILL)
            if not wait_condition(self.switch_running, False,
                                  timeout=SWITCH_STOP_TIMEOUT):
                raise ChildProcessError(
                    'P4 switch {} did not stop after requesting it.'.format(
                        self.name))
            self.switch_pid = None
        super().stop(deleteIntfs)

    def describe(self):
        """Describes P4Switch."""
        output('{} -> Thrift port: {}\n'.format(self.name, self.thrift_port))


class P4RuntimeSwitch(P4Switch):
    """BMv2 switch with gRPC support.

    Args:
        name (str)            : name of the switch
        device_id (int)       : switch unique id
        sw_bin (str)          : switch binary to execute
        json_path (str)       : path to the P4 compiled JSON configuration
        thrift_port (int)     : *Thrift* server's port
        grpc_port (int)       : *P4Runtime* gRPC server's port
        pcap_dump (bool)      : whether to save ``.pcap`` logs to disk
        pcap_dir (str)        : ``.pcap`` files path
        log_enabled (bool)    : whether to save logs to disk
        log_dir (srt)         : log path
        enable_debugger (bool): whether to enable debugger
    """

    def __init__(self, *args,
                 sw_bin='simple_switch_grpc',
                 grpc_port=None,
                 **kwargs):

        self.grpc_port = grpc_port
        if self.grpc_listening():
            raise ConnectionRefusedError(
                '{} cannot bind port {} because it is bound by another process.'.
                format(self.name, self.grpc_port))

        super().__init__(*args, sw_bin=sw_bin, **kwargs)

    def grpc_listening(self):
        """Checks if a grpc process listens on the grpc port."""
        return check_listening_on_port(self.grpc_port)

    def switch_status(self):
        """Checks if all the switch processes have started correctly."""
        return super().switch_status() and self.grpc_listening()

    def add_target_arguments(self):
        """Adds arguments to the simple switch process"""
        args = super().add_target_arguments()
        if self.grpc_port:
            args.append('--grpc-server-addr 0.0.0.0:' + str(self.grpc_port))
        return args

    def describe(self):
        """Describes P4RuntimeSwitch."""
        super().describe()
        output('{} -> gRPC port: {}\n'.format(self.name, self.grpc_port))


class FRRouter(Node):
    """FRRouter built as Mininet node.

    Args:
        name (str)    : name of the router
        bin_dir (str) : directory that contains the daemons binaries
        int_conf (str): path to the router integrated configuration file 
        conf_dir (str): path to the directory which contains the folder with
                        the configuration files for all the daemons (the folder
                        is named after the router)
        zebra (bool)  : enable Zebra daemon
        bgpd (bool)   : enable BGP protocol
        ospfd (bool)  : enable OSPFv2 (for IPv4) protocol
        ospf6d (bool) : enable OSPFv3 (for IPv6) protocol
        ripd (bool)   : enable RIP protocol
        ripngd (bool) : enable RIPng protocol
        isisd (bool)  : enable IS-IS protocol
        pimd (bool)   : enable PIM protocol
        ldpd (bool)   : enable LPD protocol
        nhrpd (bool)  : enable NHRP protocol
        eigrpd (bool) : enable EIGRP protocol
        babeld (bool) : enable Babel protocol
        sharpd (bool) : enable SHARP daemon
        staticd (bool): enable STATIC daemon
        pbrd (bool)   : enable Policy Based Routing
        bfdd (bool)   : enable Bidirectional Forwarding Detection
        fabricd (bool): enable OpenFabric protocol

    Warning:
        Only the following daemons and protocols are enabled by default:

        - ``zebra``
        - ``ospfd``
        - ``bgpd``
        - ``staticd``

    Note:
        If ``int_conf`` is set, the content ``conf_dir`` is not considered except for 
        ``vtysh.conf`` which is always taken into account.  
        If ``conf_dir`` is not specified, then it is assumed to be ``./routers``, and the
        folder which contains the configuration files is then ``./routers/<name>``.
    """

    DAEMONS = [
        'zebra',
        'bgpd',
        'ospfd',
        'ospf6d',
        'ripd',
        'ripngd',
        'isisd',
        'pimd',
        'ldpd',
        'nhrpd',
        'eigrpd',
        'babeld',
        'sharpd',
        'staticd',
        'pbrd',
        'bfdd',
        'fabricd'
    ]

    def __init__(self, name,
                 bin_dir='/usr/local/sbin',
                 int_conf=None,
                 conf_dir='./routers',
                 **kwargs):

        super().__init__(name, **kwargs)

        self.bin_dir = bin_dir
        self.conf_dir = conf_dir
        self.int_conf = int_conf

        # Make sure that the provided conf dir exists and is a directory,
        # if not, create a new one
        if not os.path.isdir(self.conf_dir):
            if os.path.exists(self.conf_dir):
                raise NotADirectoryError(
                    "'{}' exists and is not a directory.".format(
                        self.conf_dir))
            else:
                os.mkdir(self.conf_dir)

        if self.int_conf is not None:
            # Make sure that the provided ffr conf is pointing to a file
            if not os.path.isfile(self.int_conf):
                if os.path.exists(self.int_conf):
                    raise IsADirectoryError(
                        "'{}' exists and is a directory.".format(
                            self.int_conf))
                else:
                    raise FileNotFoundError(
                        "'{}' does not exist.".format(self.int_conf))

        # Default daemons
        kwargs.setdefault('zebra', True)
        kwargs.setdefault('bgpd', True)
        kwargs.setdefault('ospfd', True)
        kwargs.setdefault('staticd', True)

        # Parse daemons
        self.daemons = {}
        for key, value in kwargs.items():
            if key in FRRouter.DAEMONS and value:
                self.daemons.setdefault(key, {})

    def start(self):
        """Starts the FRRouter node."""
        # Enable IPv4 forwarding
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
        # Enable MPLS forwarding
        self.cmd('modprobe mpls_router')
        self.cmd('modprobe mpls_iptunnel')

        # Enable MPLS Label processing on all interfaces
        for intf_name in self.nameToIntf.keys():
            self.cmd('sysctl -w net.mpls.conf.{}.input=1'.format(intf_name))
        self.cmd('sysctl -w net.mpls.platform_labels=100000')

        # Enable reverse path loose mode filtering
        self.cmd('sysctl -w net.ipv4.conf.all.rp_filter=2')

        # Check binaries
        if not os.path.isfile(self.bin_dir + '/' + 'zebra'):
            raise FileNotFoundError(
                'binary path {} does not contain daemons!'.format(
                    self.bin_dir))

        if len(self.daemons.keys()) == 0:
            warning('Nothing to start in router {}\n'.format(self.name))

        # Integrated configuration
        if self.int_conf is not None:
            for daemon in self.daemons.keys():
                if daemon == 'zebra':
                    self.start_daemon(
                        daemon, '-d', u='root', g='root', N=self.name, M='fpm',
                        i='/tmp/{}-{}.pid'.format(self.name, daemon),
                        log='file:/tmp/{}-{}.log'.format(self.name, daemon))
                else:
                    self.start_daemon(
                        daemon, '-d', u='root', g='root', N=self.name,
                        i='/tmp/{}-{}.pid'.format(self.name, daemon),
                        log='file:/tmp/{}-{}.log'.format(self.name, daemon))
            # Integrated configuration
            self.cmd('vtysh -N "{}" -f "{}"'.format(self.name, self.int_conf))
        # Per daemon configuration
        else:
            for daemon in self.daemons.keys():
                if daemon == 'zebra':
                    self.start_daemon(
                        daemon, '-d', f=os.path.join(
                            self.conf_dir, self.name, daemon) + '.conf',
                        u='root', g='root', N=self.name, M='fpm',
                        i='/tmp/{}-{}.pid'.format(self.name, daemon),
                        log='file:/tmp/{}-{}.log'.format(self.name, daemon))
                else:
                    self.start_daemon(daemon, '-d',
                                      f=os.path.join(self.conf_dir, self.name, daemon)+'.conf',
                                      u='root',
                                      g='root',
                                      N=self.name,
                                      i='/tmp/{}-{}.pid'.format(self.name, daemon),
                                      log='file:/tmp/{}-{}.log'.format(self.name, daemon))

    def stop(self, deleteIntfs=False):
        """Stops FRRouter."""
        for daemon, value in self.daemons.items():
            # Kill daemon
            os.kill(value['pid'], signal.SIGKILL)
            # Remove pid, out and log files
            os.system(
                'rm -f "/tmp/{name}-{daemon}.pid" '
                '"/tmp/{name}-{daemon}.out" '
                '"/tmp/{name}-{daemon}.log"'.format(
                    name=self.name, daemon=daemon))
        # Remove socket directory
        os.system('rm -rf /var/run/{}'.format(self.name))
        super().stop(deleteIntfs)

    def start_daemon(self, daemon, *args, **kwargs):
        """Starts a daemon on the router."""
        # Get PID file
        pid_file = kwargs.get('i')
        if pid_file is None:
            pid_file = kwargs.get('pid_file')
            if pid_file is None:
                raise Exception('PID file not specified!')

        # Construct command
        cmd = os.path.join(self.bin_dir, daemon)

        for arg in args:
            cmd += ' "{}"'.format(arg)

        for key, value in kwargs.items():
            if len(key) == 1:
                cmd += ' -{} "{}"'.format(key, value)
            else:
                cmd += ' --{} "{}"'.format(key, value)

        cmd += ' --log-level debugging'

        cmd += ' > "/tmp/{}-{}.out" 2>&1'.format(self.name, daemon)
        debug(cmd+'\n')

        # Execute command
        self.cmd(cmd)

        # Retrieve PID
        with open(pid_file, 'r') as f:
            self.daemons[daemon].update(pid=int(f.read()))


class Tofino(Switch):
    """Tofino-model switch.

    Args:
        name (str)            : name of the switch
        device_id (int)       : switch unique id
        p4_src (str)          : P4 source
        sde (str)             : Tofino SDE path (``$SDE``)
        sde_install (str)     : Tofino SDE install path (``$SDE_INSTALL``)
        cli_port (int)        : switch client port
        dr_port_base (int)    : port base for driver connection
        log_dir (srt)         : log path
    """

    def __init__(self, name,
                 device_id,
                 p4_src,
                 sde,
                 sde_install,
                 cli_port=8000,
                 dr_port_base=8001,  # It uses ports from dr_port_base to dr_port_base+3
                 log_dir='/tmp',
                 **kwargs):

        if isinstance(device_id, int):
            self.device_id = device_id
        else:
            raise TypeError('device_id is not an integer.')

        kwargs.update(dpid=dpidToStr(self.device_id),
                      inNamespace=True)

        super().__init__(name, **kwargs)

        if not self.inNamespace:
            raise Exception('tofino-model cannot run in main namespace.')

        self.p4_name, _ = os.path.splitext(os.path.basename(p4_src))
        self.sde = os.path.realpath(sde)
        self.sde_install = os.path.realpath(sde_install)
        self.cli_port = cli_port
        self.dr_port_base = dr_port_base
        self.log_dir = os.path.realpath(log_dir)
        self.ports_file = '/tmp/ports_{}.json'.format(self.name)

        self.switch_pid = None
        self.driver_pid = None

        # Make sure that the provided log path is not pointing to a file
        # and, if necessary, create an empty log dir
        if not os.path.isdir(self.log_dir):
            if os.path.exists(self.log_dir):
                raise NotADirectoryError(
                    "'{}' exists and is not a directory.".format(
                        self.log_dir))
            else:
                os.mkdir(self.log_dir)

        if not os.path.isdir(os.path.join(self.log_dir, self.name)):
            if os.path.exists(os.path.join(self.log_dir, self.name)):
                raise NotADirectoryError(
                    "'{}' exists and is not a directory.".format(
                        os.path.join(self.log_dir, self.name)))
            else:
                os.mkdir(os.path.join(self.log_dir, self.name))

    def switch_running(self):
        """Checks if the switch processes have started."""
        return self.bin_running() and self.driver_running()

    def driver_running(self):
        """Checks if the switch driver process has started."""
        if self.driver_pid is not None:
            return pid_exists(self.driver_pid)
        else:
            return False

    def bin_running(self):
        """Checks if the switch binary process has started."""
        if self.switch_pid is not None:
            return pid_exists(self.switch_pid)
        else:
            return False

    def add_ports(self):
        """Adds ports to the switch ports configuration file."""
        # Configure switch ports
        ports_conf = {
            'PortToIf': []
        }
        for port, intf in list(self.intfs.items()):
            if not intf.IP():
                ports_conf['PortToIf'].append({
                    'device_port': port,
                    'if': intf.name
                })
        with open(self.ports_file, 'w') as f:
            json.dump(ports_conf, f)

    def add_tofino_args(self):
        """Adds arguments for tofino-model."""
        args = [os.path.join(self.sde, 'run_tofino_model.sh')]
        # run_tofino_model.sh params
        args.append('-p {}'.format(self.p4_name))
        args.append('-f {}'.format(self.ports_file))
        args.append('--')
        # tofino-model params
        args.append('--cli-port {}'.format(self.cli_port))
        args.append('-t {}'.format(self.dr_port_base))
        return args

    def add_driver_args(self):
        """Adds arguments for bf_switchd."""
        args = [os.path.join(self.sde, 'run_switchd.sh')]
        # run_switchd.sh params
        args.append('-p {}'.format(self.p4_name))
        # bf_switchd params
        args.append('--')
        args.append('--background')
        args.append('--tcp-port-base {}'.format(self.dr_port_base))
        return args

    def start(self, controllers=None):
        """Starts a new P4 switch."""
        info('Starting P4 switch {}.\n'.format(self.name))

        # Set environmental variables
        self.cmd('export SDE={}'.format(self.sde))
        self.cmd('export SDE_INSTALL={}'.format(self.sde_install))

        # Change directory
        self.cmd('cd {}'.format(os.path.join(self.log_dir, self.name)))

        # Add ports to switch
        self.add_ports()

        # Start tofino-model
        cmd = ' '.join(self.add_tofino_args())
        info(cmd + "\n")

        with tempfile.NamedTemporaryFile() as f:
            self.cmd(cmd + ' > tofino.log 2>&1 & echo $! >> ' + f.name)
            self.switch_pid = int(f.read())

        debug('P4 switch {} PID is {}.\n'.format(self.name, self.switch_pid))
        if not wait_condition(self.bin_running, True,
                              timeout=SWITCH_START_TIMEOUT):
            raise ChildProcessError(
                'Tofino switch {} did not start correctly. Check the switch log file.'.format(self.name))

        # Start switch driver
        cmd = ' '.join(self.add_driver_args())
        info(cmd + "\n")

        with tempfile.NamedTemporaryFile() as f:
            self.cmd(cmd + ' > driver.log 2>&1 & echo $! >> ' + f.name)
            self.driver_pid = int(f.read())

        debug('P4 switch {} driver PID is {}.\n'.format(
            self.name, self.driver_pid))
        if not wait_condition(self.driver_running, True,
                              timeout=SWITCH_START_TIMEOUT):
            raise ChildProcessError(
                'Tofino switch {} driver did not start correctly. Check the switch log file.'.format(self.name))

        info('P4 switch {} has been started.\n'.format(self.name))

        # Reset directory
        self.cmd('cd {}'.format(os.getcwd()))

    def stop(self, deleteIntfs=True):
        """Stops the P4 switch."""
        if not deleteIntfs:
            info('Stopping P4 switch {}.\n'.format(self.name))
        if self.bin_running():
            kill_proc_tree(self.switch_pid)
            self.switch_pid = None
        if self.driver_running():
            kill_proc_tree(self.driver_pid)
            self.driver_pid = None
        super().stop(deleteIntfs)

    def config(self, **params):
        """Configures Tofino."""

        r = super().config(**params)

        # Disable IPv6 on loopback interface
        self.cmd('sysctl -w net.ipv6.conf.lo.disable_ipv6=1')

        return r

    def describe(self):
        """Describes P4Switch."""
        pass
