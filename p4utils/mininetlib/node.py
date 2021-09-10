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

import os
import signal
import tempfile
from psutil import pid_exists
from mininet.log import debug, info, output, warning, error
from mininet.node import Node, Host, Switch
from mininet.moduledeps import pathCheck

from p4utils.utils.helper import *


SWITCH_START_TIMEOUT = 10
SWITCH_STOP_TIMEOUT = 10


class P4Host(Host):
    """Virtual hosts with custom configuration to work with P4 switches."""

    def config(self, **params):
        """Configure host."""

        r = super().config(**params)

        for off in ['rx', 'tx', 'sg']:
            cmd = '/sbin/ethtool --offload {} {} off'.format(self.defaultIntf().name, off)
            self.cmd(cmd)

        # disable IPv6
        self.cmd('sysctl -w net.ipv6.conf.all.disable_ipv6=1')
        self.cmd('sysctl -w net.ipv6.conf.default.disable_ipv6=1')
        self.cmd('sysctl -w net.ipv6.conf.lo.disable_ipv6=1')

        return r

    def describe(self, sw_addr=None, sw_mac=None):
        """Describe host."""

        print('**********')
        print('Network configuration for: {}'.format(self.name))
        print('Default interface: {}\t{}\t{}'.format(
            self.defaultIntf().name,
            self.defaultIntf().IP(),
            self.defaultIntf().MAC()
        ))
        if sw_addr is not None or sw_mac is not None:
            print('Default route to switch: {} ({})'.format(sw_addr, sw_mac))
        print('**********')


class P4Switch(Switch):
    """P4 virtual switch"""

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
                 **kwargs):

        if isinstance(device_id, int):
            self.device_id = device_id
        else:
            raise TypeError('device_id is not an integer.')

        kwargs.update(dpid=dpidToStr(self.device_id))
        
        super().__init__(name, **kwargs)  

        self.set_binary(sw_bin)
        self.set_json(json_path)        
        self.pcap_dir = pcap_dir
        self.pcap_dump = pcap_dump
        self.enable_debugger = enable_debugger
        self.log_enabled = log_enabled
        self.log_dir = log_dir
        self.thrift_port = thrift_port
        self.nanomsg = 'ipc:///tmp/bm-{}-log.ipc'.format(self.device_id)
        self.simple_switch_pid = None

        if self.log_enabled:
            # Make sure that the provided log path is not pointing to a file
            # and, if necessary, create an empty log dir
            if not os.path.isdir(self.log_dir):
                if os.path.exists(self.log_dir):
                    raise NotADirectoryError("'{}' exists and is not a directory.".format(self.log_dir))
                else:
                    os.mkdir(self.log_dir)

        if self.pcap_dump:
            # Make sure that the provided pcap path is not pointing to a file
            # and, if necessary, create an empty pcap dir
            if not os.path.isdir(self.pcap_dir):
                if os.path.exists(self.pcap_dir):
                    raise NotADirectoryError("'{}' exists and is not a directory.".format(self.pcap_dir))
                else:
                    os.mkdir(self.pcap_dir)

        if self.thrift_listening():
            raise ConnectionRefusedError('{} cannot bind port {} because it is bound by another process.'.format(self.name, self.thrift_port))

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

    def switch_started(self):
        """Checks if the switch process has started."""
        return pid_exists(self.simple_switch_pid)

    def thrift_listening(self):
        """Checks if a thrift process listens on the thrift port."""
        return check_listening_on_port(self.thrift_port)

    def switch_status(self):
        """Checks if all the switch processes have started correctly."""
        return self.switch_started() and self.thrift_listening()

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

    def start(self, controllers=None):
        """Starts a new P4 switch."""
        info('Starting P4 switch {}.\n'.format(self.name))
        cmd = ' '.join(self.add_arguments())
        info(cmd + "\n")

        self.simple_switch_pid = None
        with tempfile.NamedTemporaryFile() as f:
            if self.log_enabled:
                self.cmd(cmd + ' > ' + self.log_dir + '/p4s.{}.log'.format(self.name) + ' 2>&1 & echo $! >> ' + f.name)
            else:
                self.cmd(cmd + '> /dev/null 2>&1 & echo $! >> ' + f.name)
            self.simple_switch_pid = int(f.read())
        debug('P4 switch {} PID is {}.\n'.format(self.name, self.simple_switch_pid))
        if not wait_condition(self.switch_status, True, timeout=SWITCH_START_TIMEOUT):
            raise ChildProcessError('P4 switch {} did not start correctly. Check the switch log file.'.format(self.name))
        info('P4 switch {} has been started.\n'.format(self.name))

    def stop_p4switch(self):
        """Stops the simple switch binary without deleting the interfaces."""
        info('Stopping P4 switch {}.\n'.format(self.name))
        os.kill(self.simple_switch_pid, signal.SIGKILL)
        if not wait_condition(self.switch_started, False, timeout=SWITCH_STOP_TIMEOUT):
            raise ChildProcessError('P4 switch {} did not stop after requesting it.'.format(self.name))

    def stop(self, deleteIntfs=True):
        """Terminates the P4 switch node."""
        os.kill(self.simple_switch_pid, signal.SIGKILL)
        super().stop(deleteIntfs)

    def attach(self, intf):
        """Connects a data port."""
        assert 0

    def detach(self, intf):
        """"Disconnects a data port."""
        assert 0

    def describe(self):
        """Describes P4Switch."""
        print('{} -> Thrift port: {}'.format(self.name, self.thrift_port))


class P4RuntimeSwitch(P4Switch):
    """BMv2 switch with gRPC support"""

    def __init__(self, *args,
                 sw_bin='simple_switch_grpc',
                 grpc_port=None,
                 **kwargs):

        self.grpc_port = grpc_port
        if self.grpc_listening():
            raise ConnectionRefusedError('{} cannot bind port {} because it is bound by another process.'.format(self.name, self.grpc_port))

        super().__init__(*args, sw_bin=sw_bin, **kwargs)

    def grpc_listening(self):
        """Checks if a grpc process listens on the grpc port."""
        return check_listening_on_port(self.grpc_port)

    def switch_status(self):
        """Checks if all the switch processes have started correctly."""
        return super().switch_status() and self.grpc_listening()

    def add_arguments(self):
        """Adds arguments to the simple switch process"""
        args = super().add_arguments()
        if self.grpc_port:
            args.append('-- --grpc-server-addr 0.0.0.0:' + str(self.grpc_port))
        return args

    def describe(self):
        """Describes P4RuntimeSwitch."""
        super().describe()
        print('{} -> gRPC port: {}'.format(self.name, self.grpc_port))

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
                raise NotADirectoryError("'{}' exists and is not a directory.".format(self.conf_dir))
            else:
                os.mkdir(self.conf_dir)

        if self.int_conf is not None:
            # Make sure that the provided ffr conf is pointing to a file
            if not os.path.isfile(self.int_conf):
                if os.path.exists(self.int_conf):
                    raise IsADirectoryError("'{}' exists and is a directory.".format(self.int_conf))
                else:
                    raise FileNotFoundError("'{}' does not exist.".format(self.int_conf))  

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
        if not os.path.isfile(self.bin_dir + "/" + "zebra"):
            error("Binaries path {} does not contain daemons!".format(self.bin_dir))
            exit(0)

        if len(self.daemons.keys()) == 0:
            error('Nothing to start in router {}'.format(self.name))

        # Integrated configuration
        if self.int_conf is not None:
            for daemon in self.daemons.keys():
                if daemon == 'zebra':
                    self.start_daemon(daemon, '-d',
                                      u='root',
                                      g='root',
                                      N=self.name,
                                      M='fpm',
                                      i='/tmp/{}-{}.pid'.format(self.name, daemon),
                                      log='file:/tmp/{}-{}.log'.format(self.name, daemon))
                else:
                    self.start_daemon(daemon, '-d',
                                      u='root',
                                      g='root',
                                      N=self.name,
                                      i='/tmp/{}-{}.pid'.format(self.name, daemon),
                                      log='file:/tmp/{}-{}.log'.format(self.name, daemon))
            # Integrated configuration
            self.cmd('vtysh -N "{}" -f "{}"'.format(self.name, self.int_conf))
        # Per daemon configuration
        else:
            for daemon in self.daemons.keys():
                if daemon == 'zebra':
                    self.start_daemon(daemon, '-d',
                                      f=os.path.join(self.conf_dir, self.name, daemon)+'.conf',
                                      u='root',
                                      g='root',
                                      N=self.name,
                                      M='fpm',
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

    def stop(self):
        """Terminates FRRouter."""
        for daemon, value in self.daemons.items():
            # Kill daemon
            os.kill(value['pid'], signal.SIGKILL)
            # Remove pid, out and log files
            os.system('rm -f "/tmp/{name}-{daemon}.pid" '
                      '"/tmp/{name}-{daemon}.out" '
                      '"/tmp/{name}-{daemon}.log"'.format(name=self.name, daemon=daemon))
        # Remove socket directory
        os.system('rm -rf /var/run/{}'.format(self.name))
        super().stop()

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
