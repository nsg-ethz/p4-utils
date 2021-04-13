#!/usr/bin/env python3
import os
import enum

import p4utils.utils.p4runtime_API
import p4utils.utils.p4runtime_API.api as api
import p4utils.utils.p4runtime_API.context as ctx

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
    """
    For a better documentation of the primitives and the assumptions used,
    please take a look at:
    - P4Runtime Client repository
    - P4 Runtime Specification (https://p4.org/p4runtime/spec/v1.3.0/P4Runtime-Spec.html)
    """
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
        except p4utils.utils.p4runtime_API.p4runtime.P4RuntimeException:
            # If the client fails to retrieve the configuration information from the server,
            # it will establish the connection using the configuration files provided.
            if not os.path.isfile(self.p4rt_path):
                raise FileNotFoundError('No P4 runtime information file provided.')
            if not os.path.isfile(self.json_path):
                raise FileNotFoundError('No P4 compiled JSON file provided.')

            self.client, self.context = api.setup(
                                                    device_id=self.device_id,
                                                    grpc_addr=self.grpc_ip+':'+str(self.grpc_port),
                                                    config=api.FwdPipeConfig(self.p4rt_path, self.json_path)
                                                 )

    ## Utils
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

    ## Tables
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
            raise Exception('table "{}" has {} match keys, {} entered.'.format(table_name,
                                                                               self.context.get_mf_len(table_name),
                                                                               len(match_keys)))
        
        print('action: '+action_name)
        if len(action_params) == self.context.get_param_len(action_name):
            entry.action.set(**self.parse_action_param(action_name, action_params))
        else:
            raise Exception('action "{}" takes {} params, {} entered.'.format(action_name,
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
            raise Exception('action "{}" takes {} params, {} entered.'.format(action_name,
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
            raise Exception('table "{}" has {} match keys, {} entered.'.format(table_name,
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
            raise Exception('table "{}" has {} match keys, {} entered.'.format(table_name,
                                                                             self.context.get_mf_len(table_name),
                                                                             len(match_keys)))

        print('action: '+action_name)
        if len(action_params) == self.context.get_param_len(action_name):
            entry.action.set(**self.parse_action_param(action_name, action_params))
        else:
            raise Exception('action "{}" takes {} params, {} entered.'.format(action_name,
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
            raise Exception('table "{}" has {} match keys, {} entered.'.format(table_name,
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
            raise Exception('counter "{}" has {} match keys, {} entered.'.format(table_name,
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

        Args:
            direct_counter_name (string): name of the direct counter
        """
        print('Resetting direct counter: "{}"'.format(direct_counter_name))
        entries = api.DirectCounterEntry(self.client, self.context, direct_counter_name).read()
        for entry in entries:
            direct_counter_type = entry._counter_type
            if direct_counter_type in [CounterType.packets.value, CounterType.both.value]:
                entry.packet_count = 0
            if direct_counter_type in [CounterType.bytes.value, CounterType.both.value]:
                entry.byte_count = 0
            entry.modify()
        
    ## DirectMeters
    def direct_meter_array_set_rates(self, direct_meter_name, rates):
        """
        Configure rates for an entire direct meter array.

        Args:
            direct_meter_name (string): name of the direct meter
            rates (list)              : [(cir, cburst), (pir, pburst)]

        Notice:
            cir and pir use units/second, cbursts and pburst use units where units is bytes or packets,
            depending on the meter type.
        """
        print('Setting direct meter array: "{}"'.format(direct_meter_name))
        entries = api.DirectMeterEntry(self.client, self.context, direct_meter_name).read()
        
        if isinstance(rates, list):
            if len(rates) == 2:
                if not isinstance(rates[0], tuple):
                    raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
                if not isinstance(rates[1], tuple):
                    raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
                # Set rates
                for entry in entries:
                    entry.cir = rates[0][0]
                    entry.cburst = rates[0][1]
                    entry.pir = rates[1][0]
                    entry.pburst = rates[1][1]
                    entry.modify()
            else:
                raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
        else:
            raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')        

    def direct_meter_set_rates(self, direct_meter_name, match_keys, prio=0, rates=None):
        """
        Configure rates for a single direct meter entry.

        Args:
            direct_meter_name (string)  : name of the direct meter
            match_keys (list of strings): values to match (used to identify the table
                                          entry to which the direct meter is attached)
            prio (int)                  : priority in ternary match (used to identify the table
                                          entry to which the direct meter is attached)
            rates (list)                : [(cir, cburst), (pir, pburst)] (default: None, i.e.
                                          all packets are marked as green)
        
        Notice:
            cir and pir use units/second, cbursts and pburst use units where units is bytes or packets,
            depending on the meter type.
        """
        print('Setting direct meter: "{}"'.format(direct_meter_name))
        if not isinstance(match_keys, list):
            raise TypeError('match_keys is not a list.')
        entry = api.DirectMeterEntry(self.client, self.context, direct_meter_name)
        table_name = entry._direct_table_name

        print('match:')
        if len(match_keys) == self.context.get_mf_len(table_name):
            entry.table_entry.match.set(**self.parse_match_key(table_name, match_keys))
        else:
            raise Exception('meter "{}" has {} match keys, {} entered.'.format(direct_meter_name,
                                                                               self.context.get_mf_len(table_name),
                                                                               len(match_keys)))
        if prio:
            print('priority: {}'.format(prio))
            entry.table_entry.priority = prio

        if isinstance(rates, list):
            if len(rates) == 2:
                if not isinstance(rates[0], tuple):
                    raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
                if not isinstance(rates[1], tuple):
                    raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
                # Set rates
                entry.cir = rates[0][0]
                entry.cburst = rates[0][1]
                entry.pir = rates[1][0]
                entry.pburst = rates[1][1]
            else:
                raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
        else:
            raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')

        entry.modify()

    def direct_meter_get_rates(self, direct_meter_name, match_keys, prio=0):
        """
        Retrieve rates for a direct meter.

        Args:
            direct_meter_name (string)    : name of the direct meter
            match_keys (list of strings)  : values to match (used to identify the table
                                            entry to which the direct meter is attached)
            prio (int)                    : priority in ternary match (used to identify the table
        
        Return:
            [(cir, cburst), (pir, pburst)] if meter is configured, None if meter is not configured

        Notice:
            cir and pir use units/second, cbursts and pburst use units where units is bytes or packets,
            depending on the meter type.
        """
        print('Reading rates of direct meter: "{}"'.format(direct_meter_name))
        if not isinstance(match_keys, list):
            raise TypeError('match_keys is not a list.')
        entry = api.DirectMeterEntry(self.client, self.context, direct_meter_name)
        table_name = entry._direct_table_name

        print('match:')
        if len(match_keys) == self.context.get_mf_len(table_name):
            entry.table_entry.match.set(**self.parse_match_key(table_name, match_keys))
        else:
            raise Exception('meter "{}" has {} match keys, {} entered.'.format(direct_meter_name,
                                                                               self.context.get_mf_len(table_name),
                                                                               len(match_keys)))
        if prio:
            print('priority: {}'.format(prio))
            entry.table_entry.priority = prio

        entry = list(entry.read())[0]

        return [(entry.cir, entry.cburst), (entry.pir, entry.pburst)]

    ## Counters
    def counter_read(self, counter_name, index):
        """
        Read counter value.

        Args:
            counter_name (string): name of the counter
            index (int)          : index of the counter to read (first element is at 0)

        Returns:
            byte_count (int)            : number of bytes counted
            packet_count (int)          : number of packets counted

        Notice:
            P4Runtime does not distinguish between the different PSA counter types, i.e. counters are
            always considered of PACKETS_AND_BYTES and both values are returned. It is user's responsability
            to use only the correct value (see https://p4.org/p4runtime/spec/v1.3.0/P4Runtime-Spec.html#sec-counterentry-directcounterentry).
        """
        print('Reading counter: "{}"'.format(counter_name))
        entry = api.CounterEntry(self.client, self.context, counter_name)

        print('index: {}'.format(index))
        entry.index = index
        
        entry = list(entry.read())[0]
        return entry.byte_count, entry.packet_count

    def counter_write(self, counter_name, index, pkts=0, byts=0):
        """
        Write counter values. If no values are specified, the counter is reset.

        Args:
            counter_name (string): name of the counter
            index (int)          : index of the counter to write (first element is at 0)
            pkts (int)           : number of packets to write (default: 0)
            byts (int)           : number of bytes to write (default: 0)
        """
        print('Writing to counter: "{}"'.format(counter_name))
        entry = api.CounterEntry(self.client, self.context, counter_name)

        print('index: {}'.format(index))
        entry.index = index

        counter_type = entry._counter_type
        if counter_type in [CounterType.packets.value, CounterType.both.value]:
            entry.packet_count = pkts
        if counter_type in [CounterType.bytes.value, CounterType.both.value]:
            entry.byte_count = byts
        entry.modify()

    def counter_reset(self, counter_name):
        """
        Reset all the counters values.

        Args:
            counter_name (string): name of the counter
        """
        print('Resetting counter: "{}"'.format(counter_name))
        entries = api.CounterEntry(self.client, self.context, counter_name).read()

        for entry in entries:
            counter_type = entry._counter_type
            if counter_type in [CounterType.packets.value, CounterType.both.value]:
                entry.packet_count = 0
            if counter_type in [CounterType.bytes.value, CounterType.both.value]:
                entry.byte_count = 0
            entry.modify()

    ## Meters
    def meter_array_set_rates(self, meter_name, rates):
        """
        Configure rates for an entire meter array.

        Args:
            meter_name (string): name of the meter
            rates (list)       : [(cir, cburst), (pir, pburst)]

        Notice:
            cir and pir use units/second, cbursts and pburst use units where units is bytes or packets,
            depending on the meter type.
        """
        print('Setting meter array: "{}"'.format(meter_name))
        entries = api.MeterEntry(self.client, self.context, meter_name).read()

        if isinstance(rates, list):
            if len(rates) == 2:
                if not isinstance(rates[0], tuple):
                    raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
                if not isinstance(rates[1], tuple):
                    raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
                # Set rates
                for entry in entries:
                    entry.cir = rates[0][0]
                    entry.cburst = rates[0][1]
                    entry.pir = rates[1][0]
                    entry.pburst = rates[1][1]
                    entry.modify()
            else:
                raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
        else:
            raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')        

    def meter_set_rates(self, meter_name, index, rates):
        """
        Configure rates for a single  meter entry.

        Args:
            meter_name (string): name of the meter
            rates (list)       : [(cir, cburst), (pir, pburst)] (default: None, i.e.
                                 all packets are marked as green)
            index (int)        : index of the meter to set (first element is at 0)
        
        Notice:
            cir and pir use units/second, cbursts and pburst use units where units is bytes or packets,
            depending on the meter type.
        """
        print('Setting meter: "{}"'.format(meter_name))
        entry = api.MeterEntry(self.client, self.context, meter_name)

        print('index: {}'.format(index))
        entry.index = index

        if isinstance(rates, list):
            if len(rates) == 2:
                if not isinstance(rates[0], tuple):
                    raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
                if not isinstance(rates[1], tuple):
                    raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
                # Set rates
                entry.cir = rates[0][0]
                entry.cburst = rates[0][1]
                entry.pir = rates[1][0]
                entry.pburst = rates[1][1]
            else:
                raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
        else:
            raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')

        entry.modify()

    def meter_get_rates(self, meter_name, index):
        """
        Retrieve rates for a meter.

        Args:
            meter_name (string): name of the meter
            index (int)        : index of the meter to read (first element is at 0)
        
        Return:
            [(cir, cburst), (pir, pburst)] if meter is configured, None if meter is not configured

        Notice:
            cir and pir use units/second, cbursts and pburst use units where units is bytes or packets,
            depending on the meter type.
        """
        print('Reading rates of meter: "{}"'.format(meter_name))
        entry = api.MeterEntry(self.client, self.context, meter_name)
        
        print('index: {}'.format(index))
        entry.index = index

        entry = list(entry.read())[0]

        return [(entry.cir, entry.cburst), (entry.pir, entry.pburst)]

    ## MulticastGroups
    def mc_mgrp_create(self, mgrp):
        """
        Create multicast group.

        Args:
            mgrp (int): multicast group id

        Notice:
            mgrp must be greater than 0.
        """
        print('Creating multicast group: {}'.format(mgrp))
        entry = api.MulticastGroupEntry(self.client, self.context, mgrp)
        entry.insert()
    
    def mc_mgrp_destroy(self, mgrp):
        """
        Destroy multicast group.

        Args:
            mgrp (int): multicast group id

        Notice:
            mgrp must be greater than 0.
        """
        print('Destroying multicast group: {}'.format(mgrp))
        entry = api.MulticastGroupEntry(self.client, self.context, mgrp)
        entry.delete()

    def mc_set_replicas(self, mgrp, ports, instances=None):
        """
        Set replicas for multicast group.

        Args:
            mgrp (int)             : multicast group id
            ports (list of int)    : list of port numbers to add to the multicast group
            instances (list of int): list of instances of the corresponding ports

        Notice:
            mgrp must be greater than 0.
            A replica is a tuple (port, instance) which has to be unique within the 
            same multicast group. Instances can be explicitly assigned to ports by 
            passing the list instances to this function. If the list instances is not
            specified, then the instance number is set to 0 for all the replicas.
        """
        print('Adding replicas to multicast group: {}'.format(mgrp))
        entry = api.MulticastGroupEntry(self.client, self.context, mgrp)
        
        if not isinstance(ports, list):
            raise TypeError('ports is not a list.')
        elif instances:
            if not isinstance(instances, list):
                raise TypeError('instances is not a list.')
            elif len(instances) != len(ports):
                raise Exception('instances and ports have different lengths.')
            else:
                for i in range(len(ports)):
                    entry = entry.add(ports[i], instances[i])
        else:
            for i in range(len(ports)):
                entry = entry.add(ports[i])

        entry.modify()
