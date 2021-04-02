#!/usr/bin/env python3
import os

import p4runtime_cli
import p4runtime_cli.api as api


class SimpleSwitchP4RuntimeAPI:

    def __init__(self, device_id,
                 grpc_port,
                 grpc_ip='0.0.0.0',
                 p4rt_path=None,
                 json_path=None,
                 **kwargs):
    
    self.device_id = device_id
    self.grpc_ip = grpc_ip
    self.p4rt_path = p4rt_path
    self.json_path = json_path
    
    try:
        # The client will always attempt to retrieve the configuration info from the server.
        # This works only if the switch has been configured via grpc at least once.
        self.client, self.contex = api.setup(
                                                device_id=self.device_id,
                                                grpc_addr=self.grpc_ip+':'+str(self.grpc_port)
                                            )
    except p4runtime_cli.p4runtime.P4RuntimeException:
        # If the client fails to retrieve the configuration information from the server,
        # it will establish the connection using the configuration files provided.
        if not os.path.isfile(self.p4rt_path):
            raise FileNotFoundError('No P4 runtime information file provided.')
        if not os.path.isfile(self.json_path):
            raise FileNotFoundError('No P4 compiled JSON file provided.')

        self.client, self.contex = api.setup(
                                                device_id=self.device_id,
                                                grpc_addr=self.grpc_ip+':'+self.grpc_port,
                                                config=api.FwdPipeConfig(self.p4rt_info, self.json_path)
                                            )

