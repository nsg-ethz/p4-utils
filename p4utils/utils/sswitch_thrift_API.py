#!/usr/bin/env python3
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

#
# Antonin Bas (antonin@barefootnetworks.com)
#
# Modified version of the sswitch_CLI.py from behavioural model
# Edgar Costa (cedgar@ethz.ch)

"""__ p4utils.utils.thrift_API.html

__ https://github.com/p4lang/behavioral-model/blob/main/targets/simple_switch/sswitch_CLI.py

This module provides the *Simple Switch Thrift API*. It builds
on the generic `Thrift API`__. It is a modified version of 
`sswitch_CLI.py`__ from behavioral model.
"""

from functools import wraps

from sswitch_runtime import SimpleSwitch
from sswitch_runtime.ttypes import *

import p4utils.utils.thrift_API as thrift_API


def handle_bad_input(f):
    """Handles bad input.

    Args:
        f (types.FunctionType): function or method to handle
    """
    @wraps(f)
    @thrift_API.handle_bad_input
    def handle(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except InvalidMirroringOperation as e:
            error = MirroringOperationErrorCode._VALUES_TO_NAMES[e.code]
            print("Invalid mirroring operation ({})".format(error))
    return handle


class SimpleSwitchThriftAPI(thrift_API.ThriftAPI):
    """ Simple Switch *Thrift* control plane API.
    
    Args:
        thrift_port (int): port to connect to
        thrift_ip (str)  : IP the *Thrift* server is listening on
        json_path (str)  : optional JSON compiled P4 file to push to the switch

    Attributes:
        sswitch_client: *Thrift* client instance to communicate with the switch
    """
    
    @staticmethod
    def get_thrift_services():
        """Get available *Thrift* services."""
        return [("simple_switch", SimpleSwitch.Client)]

    def __init__(self, thrift_port,
                 thrift_ip='localhost',
                 json_path=None):

        pre_type = thrift_API.PreType.SimplePreLAG

        super().__init__(thrift_port,
                         thrift_ip,
                         pre_type, 
                         json_path)

        self.sswitch_client = thrift_API.thrift_connect(thrift_ip,
                                                        thrift_port,
                                                        SimpleSwitchThriftAPI.get_thrift_services())[0]

    def parse_int(self, arg, name):
        """Tries to convert the argument to :py:class:`int`.

        Args:
            arg       : argument that can be converted to :py:class:`int`
            name (str): name of the argument

        Returns:
            int: integer value of the argument
        
        Raises:
            p4utils.utils.thrift_API.UIn_Error: if the argument cannot be transformed in
                                                an integer.
        """
        try:
            return int(arg)
        except:
            raise thrift_API.UIn_Error("Bad format for {}, expected integer".format(name))

    @handle_bad_input
    def set_queue_depth(self, queue_depth, egress_port=None, priority=None):
        """Sets depth of one / all egress queue(s).

        Args: 
            queue_depth (int): number of packets
            egress_port (int): optional *egress port*, otherwise all ports
                               are considered
            priority    (int): optional *priority*. Setting the depth of
                               a specific priority queue if enabled
        """

        depth = self.parse_int(queue_depth, "queue_depth")
        if egress_port and priority:
            priority = self.parse_int(priority, "priority")
            egress_port = self.parse_int(egress_port, "egress_port")
            self.sswitch_client.set_egress_priority_queue_depth(egress_port, priority, depth)
        elif egress_port:
            egress_port = self.parse_int(egress_port, "egress_port")
            self.sswitch_client.set_egress_queue_depth(egress_port, depth)
        else:
            self.sswitch_client.set_all_egress_queue_depths(depth)

    @handle_bad_input
    def set_queue_rate(self, rate, egress_port=None, priority=None):
        """Sets rate of one / all egress queue(s).
        
        Args:
            rate (int)       : rate (packets per seconds)
            egress_port (int): optional *egress port*, otherwise all ports
                               are considered
            priority    (int): optional *priority*. Setting the depth of
                               a specific priority queue if enabled                               
        """

        rate = self.parse_int(rate, "rate_pps")
        if egress_port and priority:
            priority = self.parse_int(priority, "priority")
            egress_port = self.parse_int(egress_port, "egress_port")
            self.sswitch_client.set_egress_priority_queue_rate(egress_port, priority, rate)
        elif egress_port:
            egress_port = self.parse_int(egress_port, "egress_port")
            self.sswitch_client.set_egress_queue_rate(egress_port, rate)
        else:
            self.sswitch_client.set_all_egress_queue_rates(rate)

    @handle_bad_input
    def mirroring_add(self, mirror_id, egress_port):
        """Adds mirroring mapping.
        
        Args:
            mirror_id (int)  : *mirror id* to use
            egress_port (int): *egress port* to associate with the mirror
        """
        mirror_id, egress_port = self.parse_int(mirror_id, "mirror_id"), self.parse_int(egress_port, "egress_port")
        config = MirroringSessionConfig(port=egress_port)
        self.sswitch_client.mirroring_session_add(mirror_id, config)

    @handle_bad_input
    def mirroring_add_mc(self, mirror_id, mgrp):
        """Adds mirroring session to multicast group.
        
        Args:
            mirror_id (int): *mirror id* to associate
            mgrp (int)     : *multicast group*
        """
        mirror_id, mgrp = self.parse_int(mirror_id, "mirror_id"), self.parse_int(mgrp, "mgrp")
        config = MirroringSessionConfig(mgid=mgrp)
        self.sswitch_client.mirroring_session_add(mirror_id, config)

    @handle_bad_input
    def mirroring_add_port_and_mgrp(self, mirror_id, egress_port, mgrp):
        """Adds mirroring session to multicast group.
        
        Args:
            mirror_id (int)  : *mirror id* to use
            egress_port (int): *egress port* to associate with the mirror
            mgrp (int)       : *multicast group*
        """
        mirror_id, egress_port, mgrp = self.parse_int(mirror_id, "mirror_id"), self.parse_int(egress_port, "egress_port"), self.parse_int(mgrp, "mgrp")
        config = MirroringSessionConfig(mgid=mgrp, port=egress_port)
        self.sswitch_client.mirroring_session_add(mirror_id, config)

    @handle_bad_input
    def mirroring_delete(self, mirror_id):
        """Deletes mirroring mapping.
        
        Args:
            mirror_id (int): *id* of the mirror to delete
        """
        mirror_id = self.parse_int(mirror_id, "mirror_id")
        self.sswitch_client.mirroring_session_delete(mirror_id)

    @handle_bad_input
    def mirroring_get(self, mirror_id):
        """Prints mirroring session information
        
        Args:
            mirror_id (int): *id* of the mirror to display
        """
        mirror_id = self.parse_int(mirror_id, "mirror_id")
        config = self.sswitch_client.mirroring_session_get(mirror_id)
        print(config)

    @handle_bad_input
    def get_time_elapsed(self):
        """Prints time elapsed (in microseconds) since the switch started."""
        print(self.sswitch_client.get_time_elapsed_us())

    @handle_bad_input
    def get_time_since_epoch(self):
        """Prints time elapsed (in microseconds) since the switch clock's epoch."""
        print(self.sswitch_client.get_time_since_epoch_us())


if __name__ == "__main__":
    controller = SimpleSwitchAPI(9090)
