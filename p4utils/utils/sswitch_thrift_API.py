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
#

from functools import wraps

from sswitch_runtime import SimpleSwitch
from sswitch_runtime.ttypes import *

import p4utils.utils.thrift_API as thrift_API
from p4utils.utils.thrift_API import UIn_Error


def handle_bad_input(f):
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
    @staticmethod
    def get_thrift_services():
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
        try:
            return int(arg)
        except:
            raise thrift_API.UIn_Error("Bad format for {}, expected integer".format(name))

    @handle_bad_input
    def set_queue_depth(self, queue_depth, egress_port=None):
        "Set depth of one / all egress queue(s): set_queue_depth <nb_pkts> [<egress_port>]"

        depth = self.parse_int(queue_depth, "queue_depth")
        if egress_port:
            egress_port = self.parse_int(egress_port, "egress_port")
            self.sswitch_client.set_egress_queue_depth(egress_port, depth)
        else:
            self.sswitch_client.set_all_egress_queue_depths(depth)

    @handle_bad_input
    def set_queue_rate(self, rate, egress_port=None):
        "Set rate of one / all egress queue(s): set_queue_rate <rate_pps> [<egress_port>]"

        rate = self.parse_int(rate, "rate_pps")
        if egress_port:
            egress_port = self.parse_int(egress_port, "egress_port")
            self.sswitch_client.set_egress_queue_rate(egress_port, rate)
        else:
            self.sswitch_client.set_all_egress_queue_rates(rate)

    @handle_bad_input
    def mirroring_add(self, mirror_id, egress_port):
        "Add mirroring mapping: mirroring_add <mirror_id> <egress_port>"
        mirror_id, egress_port = self.parse_int(mirror_id, "mirror_id"), self.parse_int(egress_port, "egress_port")
        config = MirroringSessionConfig(port=egress_port)
        self.sswitch_client.mirroring_session_add(mirror_id, config)

    @handle_bad_input
    def mirroring_add_mc(self, mirror_id, mgrp):
        "Add mirroring session to multicast group: mirroring_add_mc <mirror_id> <mgrp>"
        mirror_id, mgrp = self.parse_int(mirror_id, "mirror_id"), self.parse_int(mgrp, "mgrp")
        config = MirroringSessionConfig(mgid=mgrp)
        self.sswitch_client.mirroring_session_add(mirror_id, config)

    @handle_bad_input
    def mirroring_add_port_and_mgrp(self, mirror_id, egress_port, mgrp):
        "Add mirroring session to multicast group: mirroring_add_mc <mirror_id> <mgrp>"
        mirror_id, egress_port, mgrp = self.parse_int(mirror_id, "mirror_id"), self.parse_int(egress_port, "egress_port"), self.parse_int(mgrp, "mgrp")
        config = MirroringSessionConfig(mgid=mgrp, port=egress_port)
        self.sswitch_client.mirroring_session_add(mirror_id, config)

    @handle_bad_input
    def mirroring_delete(self, mirror_id):
        "Delete mirroring mapping: mirroring_delete <mirror_id>"
        mirror_id = self.parse_int(mirror_id, "mirror_id")
        self.sswitch_client.mirroring_session_delete(mirror_id)

    @handle_bad_input
    def mirroring_get(self, mirror_id):
        "Display mirroring session: mirroring_get <mirror_id>"
        mirror_id = self.parse_int(mirror_id, "mirror_id")
        config = self.sswitch_client.mirroring_session_get(mirror_id)
        print(config)

    @handle_bad_input
    def get_time_elapsed(self):
        "Get time elapsed (in microseconds) since the switch started: get_time_elapsed"
        print(self.sswitch_client.get_time_elapsed_us())

    @handle_bad_input
    def get_time_since_epoch(self):
        "Get time elapsed (in microseconds) since the switch clock's epoch: get_time_since_epoch"
        print(self.sswitch_client.get_time_since_epoch_us())


if __name__ == "__main__":
    controller = SimpleSwitchAPI(9090)
