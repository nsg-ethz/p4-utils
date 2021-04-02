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
        self.grpc_port = grpc_port
        self.grpc_ip = grpc_ip
        self.p4rt_path = p4rt_path
        self.json_path = json_path
        
        try:
            # The client will always attempt to retrieve the configuration info from the server.
            # This works only if the switch has been configured via grpc at least once to avoid
            # unwanted overwrites of the current configuration.
            self.client, self.context = api.setup(
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

            self.client, self.context = api.setup(
                                                    device_id=self.device_id,
                                                    grpc_addr=self.grpc_ip+':'+str(self.grpc_port),
                                                    config=api.FwdPipeConfig(self.p4rt_path, self.json_path),
                                                    election_id=(1,0)
                                                 )


    def parse_match_key(self, table_name, key_fields):
        match_keys_dict = {}
        for i in range(len(key_fields)):
            match_keys_dict[self.context.get_mf_name(table_name, i+1)] = str(key_fields[i])
        return match_keys_dict

    
    def parse_action_param(self, action_name, action_params):
        params_dict = {}
        for i in range(len(action_params)):
            params_dict[self.context.get_param_name(action_name, i+1)] = str(action_params[i])
        return params_dict


    def table_add(self, table_name, action_name, match_keys, action_params=[], prio=None):
        entry = api.TableEntry(self.client, self.context, table_name)(action=action_name)
        if len(match_keys) == self.context.get_mf_len(table_name):
            entry.match.set(**self.parse_match_key(table_name, match_keys))
        else:
            raise Exception('Table {} has {} match keys, {} entered.'.format(table_name,
                                                                             self.context.get_mf_len(table_name),
                                                                             len(match_keys)))
        if len(action_params) == self.context.get_param_len(action_name):
            entry.action.set(**self.parse_action_param(action_name, action_params))
        else:
            raise Exception('Action {} has {} params, {} entered.'.format(action_name,
                                                                          self.context.get_mf_len(action_name),
                                                                          len(action_params)))
        entry.insert()

        
