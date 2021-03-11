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

from sys import exit
from time import sleep
import os
import tempfile
import socket
from mininet.node import Switch, Host
from mininet.log import setLogLevel, info, error, debug
from mininet.moduledeps import pathCheck

from p4utils.utils.utils import check_listening_on_port

SWITCH_START_TIMEOUT = 10

def configureP4Switch(**switch_args):
    """ Helper class that is called by mininet to initialize the virtual P4 switches.
    The purpose is to ensure each switch's thrift server is using a unique port number.
    """


    class ConfiguredP4Switch(P4Switch):
            next_thrift_port = 9090

            def __init__(self, *opts, **kwargs):
                kwargs.update(switch_args)
                kwargs['thrift_port'] = ConfiguredP4Switch.next_thrift_port
                ConfiguredP4Switch.next_thrift_port += 1
                P4Switch.__init__(self, *opts, **kwargs)

            def describe(self):
                print("%s -> Thrift port: %d" % (self.name, self.thrift_port))


    class ConfiguredP4RuntimeSwitch(P4RuntimeSwitch, ConfiguredP4Switch):
                next_grpc_port = 9559

                def __init__(self, *opts, **kwargs):
                    kwargs.update(switch_args)
                    kwargs['grpc_port'] = ConfiguredP4RuntimeSwitch.next_grpc_port
                    kwargs['thrift_port'] = ConfiguredP4Switch.next_thrift_port
                    ConfiguredP4RuntimeSwitch.next_grpc_port += 1
                    ConfiguredP4Switch.next_thrift_port += 1
                    P4RuntimeSwitch.__init__(self, *opts, **kwargs)

                def describe(self):
                    ConfiguredP4Switch.describe(self)
                    print("%s -> gRPC port: %d" % (self.name, self.grpc_port))


    if "sw_path" in switch_args and 'grpc' in switch_args['sw_path']:
        return ConfiguredP4RuntimeSwitch
    else:
        return ConfiguredP4Switch


class P4Host(Host):
    """Virtual hosts with custom configuration to work with P4 switches"""
    def config(self, **params):
        r = super().config(**params)

        for off in ["rx", "tx", "sg"]:
            cmd = "/sbin/ethtool --offload %s %s off" % (self.defaultIntf().name, off)
            self.cmd(cmd)

        # disable IPv6
        self.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        self.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
        self.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")

        return r

    def describe(self, sw_addr=None, sw_mac=None):
        print("**********")
        print("Network configuration for: %s" % self.name)
        print("Default interface: %s\t%s\t%s" %(
            self.defaultIntf().name,
            self.defaultIntf().IP(),
            self.defaultIntf().MAC()
        ))
        if sw_addr is not None or sw_mac is not None:
            print("Default route to switch: %s (%s)" % (sw_addr, sw_mac))
        print("**********")


class P4Switch(Switch):
    """P4 virtual switch"""
    device_id = 1

    def __init__(self, name,
                 sw_path=None,
                 json_path=None,
                 log_file=None,
                 thrift_port=None,
                 pcap_dump=False,
                 pcap_dir = "",
                 log_console=False,
                 verbose=False,
                 device_id=None,
                 enable_debugger=False,
                 **kwargs):

        id = device_id if device_id else P4Switch.device_id

        super().__init__(name,
                         dpid=self.dpidToStr(id),
                         **kwargs)

        assert sw_path
        # make sure that the provided sw_path is valid
        pathCheck(sw_path)
            
        self.sw_path = sw_path
        self.json_path = json_path
        self.pcap_dir = pcap_dir
        self.verbose = verbose
        self.pcap_dump = pcap_dump
        self.enable_debugger = enable_debugger
        self.log_console = log_console
        self.log_file = log_file
        self.thrift_port = thrift_port
        self.nanomsg = "ipc:///tmp/bm-{}-log.ipc".format(self.device_id)
        self.simple_switch_pid = None

        # make sure that the provided JSON file exists
        if self.json_path and not os.path.isfile(self.json_path):
            error("Invalid JSON file.\n")
            exit(1)
        if self.log_file is None:
            self.log_file = "/tmp/p4s.{}.log".format(self.name)
        if self.thrift_listening():
            error('%s cannot bind port %d because it is bound by another process\n' % (self.name, self.thrift_port))
            exit(1)
        if device_id is not None:
            self.device_id = device_id
            P4Switch.device_id = max(P4Switch.device_id, device_id)
        else:
            self.device_id = P4Switch.device_id
            P4Switch.device_id += 1
       
    @classmethod
    def setup(cls):
        pass

    def dpidToStr(self, id):
        strDpid = str(id)
        if len(strDpid) < 16:
            return "0"*(16-len(strDpid)) + strDpid
        return strDpid

    def switch_started(self):
        """Check if the switch process has started."""
        return os.path.exists(os.path.join("/proc", str(self.simple_switch_pid)))

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
        args = [self.sw_path]
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
            args.append("--no-p4")
        if self.enable_debugger:
            args.append('--debugger')
        if self.log_console:
            args.append('--log-console')
        return args

    def start(self, controllers = None):
        """Start up a new P4 switch."""
        info("\nStarting P4 switch {}.\n".format(self.name))
        cmd = ' '.join(self.add_arguments())
        info(cmd + "\n")

        self.simple_switch_pid = None
        with tempfile.NamedTemporaryFile() as f:
            self.cmd(cmd + ' > ' + self.log_file + ' 2>&1 & echo $! >> ' + f.name)
            self.simple_switch_pid = int(f.read())
        debug("P4 switch {} PID is {}.\n".format(self.name, self.simple_switch_pid))
        sleep(1)
        if not all(self.switch_status().values()):
            error("P4 switch {} did not start correctly."
                  " Check the switch log file.\n".format(self.name))
            exit(1)
        info("P4 switch {} has been started.\n".format(self.name))

        # only do this for l3..
        #self.cmd('sysctl', '-w', 'net.ipv4.ip_forward=1')

    def stop_p4switch(self):
        """Just stops simple switch."""
        #kills simple_switch started in this shell with kill %
        info("Stopping P4 switch {}.\n".format(self.name))
        self.cmd('kill %' + self.sw_path)
        self.cmd('wait')

    def stop(self):
        """Terminate P4 switch."""
        self.cmd('kill %' + self.sw_path)
        self.cmd('wait')
        self.deleteIntfs()

    def attach(self, intf):
        """Connect a data port."""
        assert 0

    def detach(self, intf):
        """"Disconnect a data port."""
        assert 0


class P4RuntimeSwitch(P4Switch):
    "BMv2 switch with gRPC support"
    def __init__(self, *args,
                 grpc_port = None,
                 **kwargs):

        super().__init__(*args, **kwargs)
                         
        self.grpc_port = grpc_port
        if self.grpc_listening():
            error('%s cannot bind port %d because it is bound by another process\n' % (self.name, self.grpc_port))
            exit(1)

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
            args.append("-- --grpc-server-addr 0.0.0.0:" + str(self.grpc_port))
        return args
