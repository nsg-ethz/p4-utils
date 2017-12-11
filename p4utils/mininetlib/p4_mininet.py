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

class P4Host(Host):

    def config(self, **params):
        r = super(P4Host, self).config(**params)

        for off in ["rx", "tx", "sg"]:
            cmd = "/sbin/ethtool --offload %s %s off" % (self.defaultIntf().name, off)
            self.cmd(cmd)

        # disable IPv6
        self.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        self.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
        self.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")

        return r

    def describe(self, sw_addr=None, sw_mac=None):
        print "**********"
        print "Network configuration for: %s" % self.name
        print "Default interface: %s\t%s\t%s" %(
            self.defaultIntf().name,
            self.defaultIntf().IP(),
            self.defaultIntf().MAC()
        )
        if sw_addr is not None or sw_mac is not None:
            print "Default route to switch: %s (%s)" % (sw_addr, sw_mac)
        print "**********"


class P4Switch(Switch):
    """P4 virtual switch"""
    device_id = 0

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

        Switch.__init__(self, name, **kwargs)
        assert sw_path
        assert json_path

        # make sure that the provided sw_path is valid
        pathCheck(sw_path)
        # make sure that the provided JSON file exists
        if not os.path.isfile(json_path):
            error("Invalid JSON file.\n")
            exit(1)
        self.sw_path = sw_path
        self.json_path = json_path
        self.pcap_dir = pcap_dir
        self.verbose = verbose
        self.log_file = log_file
        if self.log_file is None:
            self.log_file = "/tmp/p4s.{}.log".format(self.name)
        self.output = open(self.log_file, 'w')
        self.thrift_port = thrift_port
        if check_listening_on_port(self.thrift_port):
            error('%s cannot bind port %d because it is bound by another process\n' % (self.name, self.thrift_port))
            exit(1)
        self.pcap_dump = pcap_dump
        self.enable_debugger = enable_debugger
        self.log_console = log_console
        if device_id is not None:
            self.device_id = device_id
            P4Switch.device_id = max(P4Switch.device_id, device_id)
        else:
            self.device_id = P4Switch.device_id
            P4Switch.device_id += 1
        self.nanomsg = "ipc:///tmp/bm-{}-log.ipc".format(self.device_id)

        self.simple_switch_pid = None

    @classmethod
    def setup(cls):
        pass

    def check_switch_started(self):
        """Check if switch has started properly.

        While the process is running (pid exists), we check if the Thrift
        server has been started. If the Thrift server is ready, we assume that
        the switch was started successfully. This is only reliable if the Thrift
        server is started at the end of the init process.
        """
        while True:
            if not os.path.exists(os.path.join("/proc", str(self.simple_switch_pid))):
                return False
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(("localhost", self.thrift_port))
            if result == 0:
                return  True

    def start(self, controllers = None):
        """Start up a new P4 switch."""
        info("Starting P4 switch {}.\n".format(self.name))
        args = [self.sw_path]
        for port, intf in self.intfs.items():
            if not intf.IP():
                args.extend(['-i', str(port) + "@" + intf.name])
        if self.pcap_dump:
            if self.pcap_dir:
                args.append("--pcap="+self.pcap_dir)
            else:
                args.append("--pcap")
                
        if self.thrift_port:
            args.extend(['--thrift-port', str(self.thrift_port)])
        if self.nanomsg:
            args.extend(['--nanolog', self.nanomsg])
        args.extend(['--device-id', str(self.device_id)])

        args.append(self.json_path)
        if self.enable_debugger:
            args.append("--debugger")
        if self.log_console:
            args.append("--log-console")
        info(' '.join(args) + "\n")

        self.simple_switch_pid = None
        with tempfile.NamedTemporaryFile() as f:
            self.cmd(' '.join(args) + ' >' + self.log_file + ' 2>&1 & echo $! >> ' + f.name)
            self.simple_switch_pid = int(f.read())
        debug("P4 switch {} PID is {}.\n".format(self.name, self.simple_switch_pid))
        sleep(1)
        if not self.check_switch_started():
            error("P4 switch {} did not start correctly."
                  "Check the switch log file.\n".format(self.name))
            exit(1)
        info("P4 switch {} has been started.\n".format(self.name))

    def stop_p4switch(self):
        """Just stops simple switch."""
        #kills simple_switch started in this shell with kill %
        info("Stopping P4 switch {}.\n".format(self.name))
        self.cmd('kill %' + self.sw_path)
        self.cmd('wait')

    def stop(self):
        """Terminate P4 switch."""
        self.output.flush()
        self.cmd('kill %' + self.sw_path)
        self.cmd('wait')
        self.deleteIntfs()

    def attach(self, intf):
        """Connect a data port."""
        assert 0

    def detach(self, intf):
        """"Disconnect a data port."""
        assert 0
