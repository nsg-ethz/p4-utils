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
import tempfile
import socket
from time import sleep
from mininet.log import debug, info, warning
from mininet.clean import sh
from mininet.node import Switch, Host, Node
from mininet.moduledeps import pathCheck

from mininet.util import ( quietRun, errRun, errFail, moveIntf, isShellBuiltin,
                           numCores, retry, mountCgroups, BaseString, decode,
                           encode, getincrementaldecoder, Python3, which )

from mininet.link import Link, Intf

from p4utils.utils.helper import *

SWITCH_START_TIMEOUT = 10


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
    device_id = 1
    sw_bin='simple_switch'

    @classmethod
    def setup(cls):
        pass

    @classmethod
    def set_binary(self, sw_bin):
        """Set class default binary"""
        # Make sure that the provided sw_bin is valid
        pathCheck(sw_bin)
        P4Switch.sw_bin = sw_bin

    @classmethod
    def stop_all(self):
        sh('killall {}'.format(self.sw_bin))

    def __init__(self, name,
                 sw_bin=None,  
                 json_path=None,
                 thrift_port=None,
                 pcap_dump=False,
                 pcap_dir=None,
                 log_enabled=False,
                 log_dir='/tmp',
                 device_id=None,
                 enable_debugger=False,
                 **kwargs):

        id = device_id if device_id else P4Switch.device_id

        super().__init__(name,
                         dpid=self.dpidToStr(id),
                         **kwargs)  

        # If a non default binary is given, use it
        if sw_bin is not None:
            self.set_binary(sw_bin)

        self.set_json(json_path)

        if device_id is not None:
            self.device_id = device_id
            P4Switch.device_id = max(P4Switch.device_id, device_id)
        else:
            self.device_id = P4Switch.device_id
            P4Switch.device_id += 1
        
        self.pcap_dir = pcap_dir
        self.pcap_dump = pcap_dump
        self.enable_debugger = enable_debugger
        self.log_enabled = log_enabled
        self.log_dir = log_dir
        self.thrift_port = thrift_port
        self.nanomsg = 'ipc:///tmp/bm-{}-log.ipc'.format(self.device_id)
        self.simple_switch_pid = None

        if self.log_enabled:
            # make sure that the provided log path is not pointing to a file
            # and, if necessary, create an empty log dir
            if not os.path.isdir(self.log_dir):
                if os.path.exists(self.log_dir):
                    raise NotADirectoryError("'{}' exists and is not a directory.".format(self.log_dir))
                else:
                    os.mkdir(self.log_dir)

        if self.thrift_listening():
            raise ConnectionRefusedError('{} cannot bind port {} because it is bound by another process.'.format(self.name, self.thrift_port))

    def set_json(self, json_path):
        """Set the compiled P4 JSON file."""
        # make sure that the provided JSON file exists if it is not None
        if json_path and not os.path.isfile(json_path):
            raise FileNotFoundError('Invalid JSON file.')
        else:
            self.json_path = json_path

    def dpidToStr(self, id):
        strDpid = str(id)
        if len(strDpid) < 16:
            return '0'*(16-len(strDpid)) + strDpid
        return strDpid

    def switch_started(self):
        """Check if the switch process has started."""
        return os.path.exists(os.path.join('/proc', str(self.simple_switch_pid)))

    def thrift_listening(self):
        """Check if a thrift process listens on the thrift port."""
        return check_listening_on_port(self.thrift_port)

    def switch_status(self):
        """Check if all the switch processes have started correctly."""
        status = {'switch': self.switch_started(),
                  'thrift': self.thrift_listening()}
        if status['switch']:
            for _ in range(SWITCH_START_TIMEOUT * 2):
                if status['thrift']:
                    break
                else:
                    status['thrift'] = self.thrift_listening()
                sleep(0.5)
        return status

    def add_arguments(self):
        """Add arguments to the simple switch process"""
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
        """Start up a new P4 switch."""
        info('Starting P4 switch {}.\n'.format(self.name))
        cmd = ' '.join(self.add_arguments())
        info(cmd + "\n")

        self.simple_switch_pid = None
        with tempfile.NamedTemporaryFile() as f:
            self.cmd(cmd + ' > ' + self.log_dir + '/p4s.{}.log'.format(self.name) + ' 2>&1 & echo $! >> ' + f.name)
            self.simple_switch_pid = int(f.read())
        debug('P4 switch {} PID is {}.\n'.format(self.name, self.simple_switch_pid))
        sleep(1)
        if not all(self.switch_status().values()):
            raise ChildProcessError('P4 switch {} did not start correctly. Check the switch log file.'.format(self.name))
        info('P4 switch {} has been started.\n'.format(self.name))

        # only do this for l3..
        #self.cmd('sysctl', '-w', 'net.ipv4.ip_forward=1')

    def stop_p4switch(self):
        """Just stops simple switch without deleting interfaces."""
        info('Stopping P4 switch {}.\n'.format(self.name))
        self.cmd('kill %' + self.sw_bin)
        self.cmd('wait')

    def stop(self):
        """Terminate P4 switch."""
        self.cmd('kill %' + self.sw_bin)
        self.cmd('wait')
        self.deleteIntfs()

    def attach(self, intf):
        """Connect a data port."""
        assert 0

    def detach(self, intf):
        """"Disconnect a data port."""
        assert 0

    def describe(self):
        """Describe P4Switch."""
        print('{} -> Thrift port: {}'.format(self.name, self.thrift_port))


class P4RuntimeSwitch(P4Switch):
    "BMv2 switch with gRPC support"
    sw_bin = 'simple_switch_grpc'

    @classmethod
    def set_binary(self, sw_bin):
        """Set class default binary"""
        # Make sure that the provided sw_bin is valid
        pathCheck(sw_bin)
        P4RuntimeSwitch.sw_bin = sw_bin

    def __init__(self, *args,
                 sw_bin=None,
                 grpc_port=None,
                 **kwargs):

        self.grpc_port = grpc_port
        if self.grpc_listening():
            raise ConnectionRefusedError('{} cannot bind port {} because it is bound by another process.'.format(self.name, self.grpc_port))

        # If a non default binary is given, use it
        if sw_bin is not None:
            self.set_binary(sw_bin)

        super().__init__(*args, **kwargs)

    def grpc_listening(self):
        """Check if a grpc process listens on the grpc port."""
        return check_listening_on_port(self.grpc_port)

    def switch_status(self):
        """Check if all the switch processes have started correctly."""
        status = {'switch': self.switch_started(),
                  'thrift': self.thrift_listening(),
                  'grpc': self.grpc_listening()}
        if status['switch']:
            for _ in range(SWITCH_START_TIMEOUT*2):
                if status['thrift'] and status['grpc']:
                    break
                else:
                    status['thrift'] = self.thrift_listening()
                    status['grpc'] = self.grpc_listening()
                sleep(0.5)
        return status

    def add_arguments(self):
        """Add arguments to the simple switch process"""
        args = super().add_arguments()
        if self.grpc_port:
            args.append('-- --grpc-server-addr 0.0.0.0:' + str(self.grpc_port))
        return args

    def describe(self):
        """Describe P4RuntimeSwitch."""
        super().describe()
        print('{} -> gRPC port: {}'.format(self.name, self.grpc_port))


class Router( Switch ):

    """Router definition built on Mininet switch"""

    ID = 0 
    FRR_DIR = "/usr/local/sbin"
    VTY_SOCKET_PATH = "/var/run/"

    def __init__(self, name, daemons=None, conf_path=None, **kwargs):

        kwargs['inNamespace'] = True 
        super().__init__(name, **kwargs)

        Router.ID += 1
        self.switch_id = Router.ID

        self.daemons = daemons
        self.conf_path = conf_path

    @classmethod
    def stop_all(self):
        debug('Stop all FRR deamons')
        Router.clean()

    @classmethod 
    def clean(self):
        """Clean up files from previous run.
        """
        os.system("rm -f /tmp/r*.log /tmp/r*.pid /tmp/r*.out")
        os.system("rm -f /tmp/h*.log /tmp/h*.pid /tmp/h*.out")
        os.system("mn -c >/dev/null 2>&1")
        os.system("killall -9 {} > /dev/null 2>&1"
                    .format(' '.join(os.listdir(Router.FRR_DIR)))) 

    def defaultIntf(self, event=None):
        if hasattr(self, "controlIntf") and self.controlIntf:
            return self.controlIntf

        return self.defaultIntf(self)


    def start(self):
        #pass
        self.program_router()

    def stop(self):
        super().stop()
        os.system("killall -9 {}".format(' '.join(self.daemons.keys())))  
        os.system(" rm -rf {}/{}".format(Router.VTY_SOCKET_PATH, self.name))

    def start_daemon(self, daemon, conf_dir, extra_params):
       """Start FRR on a given router"""

       cmd = (("{bin_dir}/{daemon}"
           " -f {conf_dir}/{node_name}.conf"
           " -d"
           " {options}"
           " --vty_socket {vty_path}/{node_name}/"
           " -i /tmp/{node_name}-{daemon}.pid"
           " > /tmp/{node_name}-{daemon}.out 2>&1")
           .format(bin_dir=Router.FRR_DIR,
                   daemon=daemon,
                   options=" ".join(extra_params),
                   conf_dir=conf_dir,
                   node_name=self.name,
                   vty_path=Router.VTY_SOCKET_PATH))
       #print(cmd)
       self.cmd(cmd)
       self.waitOutput()

    # Method to run FRR daemons on the routers
    def program_router(self):

        if not os.path.isfile(Router.FRR_DIR + "/" + "zebra"):
            print("Binaries path {} does not contain daemons!".format(Router.FRR_DIR))
            exit(0)

        if not self.daemons:
            print("Nothing to start in Router")

        os.system("mkdir -p {}/{}".format(Router.VTY_SOCKET_PATH, self.name))

        for daemon in self.daemons:
            options = [" -u root"]
            if daemon=="zebra":
                options  += ["-M fpm"]

            path = daemon
            _conf_dir = os.path.join(self.conf_path, path)
            #print(_conf_dir)
            self.start_daemon(daemon, _conf_dir, options)

        if self.name.startswith('r'):
            # Enable IP forwarding
            self.cmd("sysctl -w net.ipv4.ip_forward=1")
            self.waitOutput()        