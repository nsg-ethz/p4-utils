#!/usr/bin/env python3
import os
import enum

import p4runtime_cli
import p4runtime_cli.api as api
import p4runtime_cli.context as ctx

@enum.unique
class CounterType(enum.Enum):
    """
    Counter type according to P4 Runtime Specification.
    See  https://github.com/p4lang/p4runtime/blob/57bb925a30df02b5c492c2a16c29b0014b98fa7a/proto/p4/config/v1/p4info.proto#L278
    """
    unspecified = 0
    bytes = 1
    packets = 2
    both = 3

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

    ## Tables
    def parse_match_key(self, table_name, key_fields):
        match_keys_dict = {}
        for i in range(len(key_fields)):
            match_keys_dict[self.context.get_mf_name(table_name, i+1)] = key_fields[i]
        return match_keys_dict

    def parse_action_param(self, action_name, action_params):
        params_dict = {}
        for i in range(len(action_params)):
            params_dict[self.context.get_param_name(action_name, i+1)] = action_params[i]
        return params_dict

    def table_add(self, table_name, action_name, match_keys, action_params=[], prio=None):
        """
        Add entry to a match table.

        Args:
            table_name (string)             : name of the table
            action_name (string)            : action to execute on hit
            match_keys (list of strings)    : values to match
            action_params (list of strings) : parameters passed to action
            prio (int)                      : priority in ternary match
        
        Different kinds of matches:
            * For exact match: '<value>'
            * For ternary match: '<value>&&&<mask>'
            * For LPM match: '<value>/<mask>'
            * For range match: '<value>..<mask>'

        Notice:
            The priority field must be set to a non-zero value if the match key includes 
            a ternary match (i.e. in the case of PSA if the P4Info entry for the table 
            indicates that one or more of its match fields has an OPTIONAL, TERNARY or 
            RANGE match type) or to zero otherwise. A higher priority number indicates 
            that the entry must be given higher priority when performing a table lookup. 
            (see https://p4.org/p4runtime/spec/v1.3.0/P4Runtime-Spec.html#sec-table-entry)
        """
        print('Adding entry to: '+table_name)
        if not isinstance(match_keys, list):
            raise TypeError('match_keys is not a list.')
        if not isinstance(action_params, list):
            raise TypeError('action_params is not a list.')
        entry = api.TableEntry(self.client, self.context, table_name)(action=action_name)

        print('match:')
        if len(match_keys) == self.context.get_mf_len(table_name):
            entry.match.set(**self.parse_match_key(table_name, match_keys))
        else:
            raise Exception('Table "{}" has {} match keys, {} entered.'.format(table_name,
                                                                               self.context.get_mf_len(table_name),
                                                                               len(match_keys)))
        
        print('action: '+action_name)
        if len(action_params) == self.context.get_param_len(action_name):
            entry.action.set(**self.parse_action_param(action_name, action_params))
        else:
            raise Exception('Action "{}" takes {} params, {} entered.'.format(action_name,
                                                                              self.context.get_mf_len(action_name),
                                                                              len(action_params)))
        if prio:
            print('priority: {}'.format(prio))
            entry.priority = prio
        entry.insert()

    def table_set_default(self, table_name, action_name, action_params=[]):
        """
        Set default action for a match table.
        
        Args:
            table_name (string)             : name of the table
            action_name (string)            : action to execute on hit
            action_params (list of strings) : parameters passed to action

        Notice:
            When setting the default entry, the configurations for
            its direct resources will be reset to their defaults
            (see https://p4.org/p4runtime/spec/v1.3.0/P4Runtime-Spec.html#sec-direct-resources).
        """
        print('Adding default action to: '+table_name)
        if not isinstance(action_params, list):
            raise TypeError('action_params is not a list.')
        entry = api.TableEntry(self.client, self.context, table_name)(action=action_name, is_default=True)
        print('action: '+action_name)
        if len(action_params) == self.context.get_param_len(action_name):
            entry.action.set(**self.parse_action_param(action_name, action_params))
        else:
            raise Exception('Action "{}" takes {} params, {} entered.'.format(action_name,
                                                                              self.context.get_mf_len(action_name),
                                                                              len(action_params)))
        entry.modify()

    def table_reset_default(self, table_name):
        """
        Reset default action for a match table.
        
        Args:
            table_name (string)             : name of the table

        Notice:
            When resetting the default entry, the configurations for
            its direct resources will be reset to their defaults
            (see https://p4.org/p4runtime/spec/v1.3.0/P4Runtime-Spec.html#sec-default-entry).
        """
        print('Resetting default action of: '+table_name)
        entry = api.TableEntry(self.client, self.context, table_name)(is_default=True)
        entry.modify()

    def table_delete_match(self, table_name, match_keys, prio=None):
        """
        Delete an existing entry in a table.

        Args:
            table_name (string)             : name of the table
            match_keys (list of strings)    : values to match
            prio (int)                      : priority in ternary match
        """
        print('Deleting entry of: '+table_name)
        if not isinstance(match_keys, list):
            raise TypeError('match_keys is not a list.')
        entry = api.TableEntry(self.client, self.context, table_name)

        print('match:')
        if len(match_keys) == self.context.get_mf_len(table_name):
            entry.match.set(**self.parse_match_key(table_name, match_keys))
        else:
            raise Exception('Table "{}" has {} match keys, {} entered.'.format(table_name,
                                                                               self.context.get_mf_len(table_name),
                                                                               len(match_keys)))
        if prio:
            print('priority: {}'.format(prio))
            entry.priority = prio
        entry.delete()

    def table_modify_match(self, table_name, action_name, match_keys, action_params=[], prio=None):
        """
        Modify entry in a table.

        Args:
            table_name (string)             : name of the table
            action_name (string)            : action to execute on hit
            match_keys (list of strings)    : values to match
            action_params (list of strings) : parameters passed to action
            prio (int)                      : priority in ternary match

        Notice:
            When modifying the default entry, the configurations for
            its direct resources will be reset to their defaults
            (see https://p4.org/p4runtime/spec/v1.3.0/P4Runtime-Spec.html#sec-direct-resources).
        """
        print('Modifying entry of: '+table_name)
        if not isinstance(match_keys, list):
            raise TypeError('match_keys is not a list.')
        if not isinstance(action_params, list):
            raise TypeError('action_params is not a list.')
        entry = api.TableEntry(self.client, self.context, table_name)(action=action_name)

        print('match:')
        if len(match_keys) == self.context.get_mf_len(table_name):
            entry.match.set(**self.parse_match_key(table_name, match_keys))
        else:
            raise Exception('Table "{}" has {} match keys, {} entered.'.format(table_name,
                                                                             self.context.get_mf_len(table_name),
                                                                             len(match_keys)))

        print('action: '+action_name)
        if len(action_params) == self.context.get_param_len(action_name):
            entry.action.set(**self.parse_action_param(action_name, action_params))
        else:
            raise Exception('Action "{}" takes {} params, {} entered.'.format(action_name,
                                                                            self.context.get_mf_len(action_name),
                                                                            len(action_params)))
        if prio:
            print('priority: {}'.format(prio))
            entry.priority = prio
        entry.modify()

    def table_clear(self, table_name):
        """
        Clear all entries in a match table (direct or indirect), but not the default entry.
        
        Args:
            table_name (string)             : name of the table
        """
        print('Deleting all entries of: '+table_name)
        entry = api.TableEntry(self.client, self.context, table_name).read(function=lambda x: x.delete())

    ## DirectCounters
    def direct_counter_read(self, direct_counter_name, match_keys, prio=0):
        """
        Read direct counter values.

        Args:
            direct_counter_name (string): name of the direct counter
            match_keys (list of strings): values to match (used to identify the table
                                          entry to which the direct counter is attached)
            prio (int)                  : priority in ternary match (used to identify the table
                                          entry to which the direct counter is attached)

        Returns:
            byte_count (int)            : number of bytes counted
            packet_count (int)          : number of packets counted

        Notice:
            P4Runtime does not distinguish between the different PSA counter types, i.e. counters are
            always considered of PACKETS_AND_BYTES and both values are returned. It is user's responsability
            to use only the correct value (see https://p4.org/p4runtime/spec/v1.3.0/P4Runtime-Spec.html#sec-counterentry-directcounterentry).
        """
        print('Reading direct counter: "{}"'.format(direct_counter_name))
        if not isinstance(match_keys, list):
            raise TypeError('match_keys is not a list.')
        entry = api.DirectCounterEntry(self.client, self.context, direct_counter_name)
        table_name = entry._direct_table_name

        print('match:')
        if len(match_keys) == self.context.get_mf_len(table_name):
            entry.table_entry.match.set(**self.parse_match_key(table_name, match_keys))
        else:
            raise Exception('Table "{}" has {} match keys, {} entered.'.format(table_name,
                                                                               self.context.get_mf_len(table_name),
                                                                               len(match_keys)))
        if prio:
            print('priority: {}'.format(prio))
            entry.table_entry.priority = prio
        entry = list(entry.read())[0]
        return entry.byte_count, entry.packet_count

    def direct_counter_write(self, direct_counter_name, match_keys, prio=0, pkts=0, byts=0):
        """
        Write direct counter values. If no values are specified, the counter is reset.

        Args:
            direct_counter_name (string): name of the direct counter
            match_keys (list of strings): values to match (used to identify the table
                                          entry to which the direct counter is attached)
            prio (int)                  : priority in ternary match (used to identify the table
                                          entry to which the direct counter is attached)
            pkts (int)                  : number of packets to write (default: 0)
            byts (int)                  : number of bytes to write (default: 0)
        """
        print('Writing to direct counter: "{}"'.format(direct_counter_name))
        if not isinstance(match_keys, list):
            raise TypeError('match_keys is not a list.')
        entry = api.DirectCounterEntry(self.client, self.context, direct_counter_name)
        table_name = entry._direct_table_name

        print('match:')
        if len(match_keys) == self.context.get_mf_len(table_name):
            entry.table_entry.match.set(**self.parse_match_key(table_name, match_keys))
        else:
            raise Exception('Table "{}" has {} match keys, {} entered.'.format(table_name,
                                                                               self.context.get_mf_len(table_name),
                                                                               len(match_keys)))
        if prio:
            print('priority: {}'.format(prio))
            entry.table_entry.priority = prio
        
        direct_counter_type = entry._counter_type
        if direct_counter_type in [CounterType.packets.value, CounterType.both.value]:
            entry.packet_count = pkts
        if direct_counter_type in [CounterType.bytes.value, CounterType.both.value]:
            entry.byte_count = byts
        entry.modify()

    def direct_counter_reset(self, direct_counter_name):
        """
        Reset all the direct counters values.
        """
        pass
        
    ## DirectMeters