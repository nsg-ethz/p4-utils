#!/usr/bin/env python2

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
#

import p4utils.utils.runtime_API as runtime_API
from sswitch_runtime import SimpleSwitch

class SimpleSwitchAPI(runtime_API.RuntimeAPI):
    @staticmethod
    def get_thrift_services():
        return [("simple_switch", SimpleSwitch.Client)]

    def __init__(self, thrift_port, thrift_ip = 'localhost', json_path=None):

        pre_type = runtime_API.PreType.SimplePreLAG

        runtime_API.RuntimeAPI.__init__(self, thrift_port,
                                        thrift_ip, pre_type, json_path)

        self.sswitch_client = runtime_API.thrift_connect(
            thrift_ip, thrift_port, SimpleSwitchAPI.get_thrift_services()
        )

    def set_queue_depth(self, queue_depth, egress_port=None):
        "Set depth of one / all egress queue(s): set_queue_depth <nb_pkts> [<egress_port>]"

        depth = queue_depth
        if egress_port:
            self.sswitch_client.set_egress_queue_depth(egress_port, depth)
        else:
            self.sswitch_client.set_all_egress_queue_depths(depth)

    def set_queue_rate(self, rate, egress_port=None):
        "Set rate of one / all egress queue(s): set_queue_rate <rate_pps> [<egress_port>]"

        rate = int(rate)
        if egress_port:
            self.sswitch_client.set_egress_queue_rate(egress_port, rate)
        else:
            self.sswitch_client.set_all_egress_queue_rates(rate)

    def mirroring_add(self, mirror_id, egress_port):
        "Add mirroring mapping: mirroring_add <mirror_id> <egress_port>"
        mirror_id, egress_port = int(mirror_id), int(egress_port)
        self.sswitch_client.mirroring_mapping_add(mirror_id, egress_port)

    def mirroring_delete(self, mirror_id):
        "Delete mirroring mapping: mirroring_delete <mirror_id>"
        mirror_id = int(mirror_id)
        self.sswitch_client.mirroring_mapping_delete(mirror_id)

    def get_time_elapsed(self):
        "Get time elapsed (in microseconds) since the switch started: get_time_elapsed"
        print self.sswitch_client.get_time_elapsed_us()

    def get_time_since_epoch(self):
        "Get time elapsed (in microseconds) since the switch clock's epoch: get_time_since_epoch"
        print self.sswitch_client.get_time_since_epoch_us()


if __name__ == "__main__":
    from runtime_API import *
    controller = SimpleSwitchAPI(9090)