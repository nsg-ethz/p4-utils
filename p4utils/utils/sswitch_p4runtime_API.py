#!/usr/bin/env python3

"""__ p4utils.utils.p4runtime_API.html

This module provides a *P4Runtime API* for the *Simple Switch* target. It builds
on the generic `P4Runtime API`__. The methods listed here were designed to be as
close as possible (in the naming and in the signature) to those used in the 
:py:class:`p4utils.utils.thrift_API.ThriftAPI`, so that passing to one method to the
other is easier for the user.
"""

import os
import enum
from functools import wraps

import p4utils
import p4utils.utils.p4runtime_API.api as api


@enum.unique
class CounterType(enum.Enum):
    """Counter type according to *P4 Runtime Specification*. See `here`__ for details.

    __ https://github.com/p4lang/p4runtime/blob/57bb925a30df02b5c492c2a16c29b0014b98fa7a/proto/p4/config/v1/p4info.proto#L278
    """
    unspecified = 0
    bytes = 1
    packets = 2
    both = 3


def handle_bad_input(f):
    """Handles bad input.

    Args:
        f (func): function or method to handle
    
    Returns:
        bool: **True** if the function was correctly executed, and **False** otherwise.
    """
    @wraps(f)
    def handle(*args, **kwargs):
        try:
            f(*args, **kwargs)
            return True
        except Exception as e:
            print(e)
            return False
    return handle


class SimpleSwitchP4RuntimeAPI:
    """For a better documentation of the primitives and the assumptions used,
    please take a look at:

    - __ p4utils.utils.p4runtime_API.html
    
      `P4Runtime API subpackage`__

    - __ https://p4.org/p4runtime/spec/v1.3.0/P4Runtime-Spec.html

      `P4Runtime specification`__
    
    Args:
        device_id (int): switch *id*
        grpc_port (int): the port the switch gRPC server is listening on
        grpc_ip (int)  : the IP the switch gRPC server is listening on
        p4rt_path (str): path to the P4Runtime Info file
        json_path (str): path to the P4 JSON compiled file
    
    Raises:
        FileNotFoundError: if ``p4rt_path`` or ``json_path`` are not specified, or invalid and
                           the client cannot retrieve the relevant informations from the
                           P4Runtime server.

    Attributes:
        client (:py:class:`p4utils.utils.p4runtime_API.p4runtime.P4RuntimeClient`)  : P4Runtime client instance.
        context (:py:class:`p4utils.utils.p4runtime_API.context.Context`)           : P4Runtime context containing the information about all the P4 objects.
    """
    def __init__(self, device_id,
                 grpc_port,
                 grpc_ip='0.0.0.0',
                 p4rt_path=None,
                 json_path=None):
    
        self.device_id = device_id
        self.grpc_port = grpc_port
        self.grpc_ip = grpc_ip
        self.p4rt_path = p4rt_path
        self.json_path = json_path
        
        try:
            # The client will always attempt to retrieve the configuration info from the server.
            # This works only if the switch has been configured via grpc at least once to avoid
            # unwanted overwrites of the current configuration.
            self.client, self.context = api.setup(device_id=self.device_id,
                                                  grpc_addr=self.grpc_ip+':'+str(self.grpc_port))

        except p4utils.utils.p4runtime_API.p4runtime.P4RuntimeException:
            # If the client fails to retrieve the configuration information from the server,
            # it will establish the connection using the configuration files provided.
            if not os.path.isfile(self.p4rt_path):
                raise FileNotFoundError('No P4 runtime information file provided.')
            if not os.path.isfile(self.json_path):
                raise FileNotFoundError('No P4 compiled JSON file provided.')

            self.client, self.context = api.setup(device_id=self.device_id,
                                                  grpc_addr=self.grpc_ip+':'+str(self.grpc_port),
                                                  config=api.FwdPipeConfig(self.p4rt_path, self.json_path))

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

    def reset_state(self):
        """Resets the gRPC server of switch by establishing a new ``ForwardingPipelineConfig``.

        __ https://github.com/p4lang/p4runtime/blob/e9c0d196c4c2acd6f1bd3439f5b30b423ef90c95/proto/p4/v1/p4runtime.proto#L668
            
        For further details about this method, please check `this`__. Indeed, 
        this method sends to the server a ``SetForwardingPipelineConfigRequest`` with
        action ``VERIFY_AND_COMMIT``.

        This method is buggy, please read the following warnings.

        Warning:
            Due to some bug in the implementation of the gRPC server, this command
            does not fully erase all the forwarding state of the switch, but only resets the
            server.

        Note:
            - It is recommended to use :py:meth:`p4utils.utils.thrift_API.ThriftAPI.reset_state()` 
              to reset the forwarding states. Moreover, if you only use
              the :py:class:`p4utils.utils.thrift_API.ThriftAPI` to reset the switch, 
              the gRPC server will not be reset.
            
            - To do things properly, both methods need to be called 
              (the one from :py:class:`p4utils.utils.thrift_API.ThriftAPI` and the one from 
              :py:class:`SimpleSwitchP4RuntimeAPI`).
        """
        if not os.path.isfile(self.p4rt_path):
            raise FileNotFoundError('No P4 runtime information file provided.')
        if not os.path.isfile(self.json_path):
            raise FileNotFoundError('No P4 compiled JSON file provided.')

        # Disconnect
        self.teardown()

        # Reconnect
        self.client, self.context = api.setup(device_id=self.device_id,
                                              grpc_addr=self.grpc_ip+':'+str(self.grpc_port),
                                              config=api.FwdPipeConfig(self.p4rt_path, self.json_path))

    def teardown(self):
        """Tears down gRPC connection with the switch server."""
        api.teardown(self.client)
    
    def get_digest_list(self, timeout=None):
        """Retrieves ``DigestList`` and send back acknowledgment.

        Args:
            timeout (int): time to wait for packet

        Returns:
            ``DigestList`` Protobuf Message or **None** if the timeout has expired and 
            no packet has been received.
        
        Note:
            __ https://github.com/p4lang/p4runtime/blob/45d1c7ce2aad5dae819e8bba2cd72640af189cfe/proto/p4/v1/p4runtime.proto#L543

            See `here`__ for further details. If ``timeout`` is set to **None**, the
            function will wait indefinitely.
        """
        return self.client.get_digest_list(timeout)

    ## Tables
    @handle_bad_input
    def table_add(self, table_name, action_name, match_keys, action_params=[], prio=0, rates=None, pkts=None, byts=None):
        """Adds entry to a match table.

        Args:
            table_name (str)    : name of the table
            action_name (str)   : action to execute on hit
            match_keys (list)   : values to match (each value is a :py:class:`str`)
            action_params (list): parameters passed to action (each parameter is a :py:class:`str`)
            prio (int)          : priority in ternary match
            rates (list)        : ``[(cir, cburst), (pir, pburst)]`` (if **None**, the meter
                                  is set to its default behavior, i.e. marks
                                  all packets as **GREEN**)
            pkts (int)          : number of packets to write (if **None**, the count
                                  is not changed)
            byts (int)          : number of bytes to write (if **None**, the count
                                  is not changed)
        
        There are different kinds of matches:

        - For *exact* match: ``<value>``
        - For *ternary* match: ``<value>&&&<mask>``
        - For *LPM* match: ``<value>/<mask>``
        - For *range* match: ``<start>..<end>``

        There are three types of *counters*:

        - **BYTES**, only the field ``byts`` is written and the value of ``pkts`` is ignored.
        - **PACKETS**, only the field ``pkts`` is written and the value of ``byts`` is ignored.
        - **PACKETS_AND_BYTES**, both ``byts`` and ``pkts`` are written.

        There are two types of *meters*:

        - **BYTES**, ``rates`` must be expressed in number of bytes per second.
        - **PACKETS**, ``rates`` must be expressed in number of packets per second.

        Note:
            - The ``rates`` field only applies if there is a direct meter attached
              to the table.
            - The ``pkts`` and ``byts`` fields only apply if there is a direct counter
              attached to the table.
            - The ``prio`` field must be set to a non-zero value if the match key includes 
              a ternary match or to zero otherwise.
            - __ https://p4.org/p4runtime/spec/v1.3.0/P4Runtime-Spec.html#sec-table-entry

              A higher ``prio`` number indicates that the entry must be given higher
              priority when performing a table lookup (see `here`__ for details).
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

        # DirectMeter
        if rates:
            if entry._direct_meter:
                if isinstance(rates, list):
                    if len(rates) == 2:
                        if not isinstance(rates[0], tuple):
                            raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
                        if not isinstance(rates[1], tuple):
                            raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
                        # Set rates
                        entry.meter_config.cir = rates[0][0]
                        entry.meter_config.cburst = rates[0][1]
                        entry.meter_config.pir = rates[1][0]
                        entry.meter_config.pburst = rates[1][1]
                    else:
                        raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
                else:
                    raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
            else:
                raise Exception('table {} has no direct meter attached.'.format(table_name))

        # DirectCounter
        if pkts:
            if entry._direct_counter:
                direct_counter_type = entry._direct_counter.spec.unit
                if direct_counter_type in [CounterType.packets.value, CounterType.both.value]:
                    entry.counter_data.packet_count = pkts
            else:
                raise Exception('table {} has no direct counter attached.'.format(table_name))

        if byts:
            if entry._direct_counter:
                direct_counter_type = entry._direct_counter.spec.unit
                if direct_counter_type in [CounterType.bytes.value, CounterType.both.value]:
                    entry.counter_data.byte_count = byts
            else:
                raise Exception('table {} has no direct counter attached.'.format(table_name))

        entry.insert()

    @handle_bad_input
    def table_set_default(self, table_name, action_name, action_params=[]):
        """Sets default action for a match table.
        
        Args:
            table_name (str)             : name of the table
            action_name (str)            : action to execute on hit
            action_params (list)         : parameters passed to action 
                                           (each parameter is a :py:class:`str`)

        Note:
            __ https://p4.org/p4runtime/spec/v1.3.0/P4Runtime-Spec.html#sec-direct-resources
            
            When setting the default entry, the configurations for
            its direct resources will be reset to their defaults, according to `this`__.
            
        Warning:
            For the current implementation, the specification is not followed and
            direct resources are not reset when modifying a table entry.
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

    @handle_bad_input
    def table_reset_default(self, table_name):
        """Resets default action for a match table.
        
        Args:
            table_name (str): name of the table

        Note:
            __ https://p4.org/p4runtime/spec/v1.3.0/P4Runtime-Spec.html#sec-default-entry

            When resetting the default entry, the configurations for
            its direct resources will be reset to their defaults (see `here`__).
        """
        print('Resetting default action of: '+table_name)
        entry = api.TableEntry(self.client, self.context, table_name)(is_default=True)
        entry.modify()

    @handle_bad_input
    def table_delete_match(self, table_name, match_keys, prio=None):
        """Deletes an existing entry in a table.

        Args:
            table_name (str)  : name of the table
            match_keys (list) : values to match (each value is a :py:class:`str`)
            prio (int)        : priority in ternary match
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

    @handle_bad_input
    def table_modify_match(self, table_name, action_name, match_keys, action_params=[], prio=0, rates=None, pkts=None, byts=None):
        """Modifies entry in a table.

        Args:
            table_name (str)     : name of the table
            action_name (str)    : action to execute on hit
            match_keys (list)    : values to match (each value is a :py:class:`str`)
            action_params (list) : parameters passed to action (each parameter is a :py:class:`str`)
            prio (int)           : priority in ternary match
            rates (list)         : ``[(cir, cburst), (pir, pburst)]`` (if **None**, the meter
                                   is set to its default behavior, i.e. marks
                                   all packets as **GREEN**)
            pkts (int)           : number of packets to write (if **None**, the count
                                   is not changed)
            byts (int)           : number of bytes to write (if **None**, the count
                                   is not changed)

        There are three types of *counters*:

        - **BYTES**, only the field ``byts`` is written and the value of ``pkts`` is ignored.
        - **PACKETS**, only the field ``pkts`` is written and the value of ``byts`` is ignored.
        - **PACKETS_AND_BYTES**, both ``byts`` and ``pkts`` are written.

        There are two types of *meters*:

        - **BYTES**, ``rates`` must be expressed in number of bytes per second.
        - **PACKETS**, ``rates`` must be expressed in number of packets per second.

        Note:
            - The ``rates`` field only applies if there is a direct meter attached
              to the table.
            - The ``pkts`` and ``byts`` fields only apply if there is a direct counter
              attached to the table.
            - __ https://p4.org/p4runtime/spec/v1.3.0/P4Runtime-Spec.html#sec-direct-resources

              When modifying the default entry, the configurations for its direct
              resources will be reset to their defaults, according to `this`__.
            - The ``prio`` field must be set to a non-zero value if the match key includes 
              a ternary match or to zero otherwise.
            - __ https://p4.org/p4runtime/spec/v1.3.0/P4Runtime-Spec.html#sec-table-entry

              A higher ``prio`` number indicates that the entry must be given higher
              priority when performing a table lookup (see `here`__ for details).
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

        # DirectMeter
        if rates:
            if entry._direct_meter:
                if isinstance(rates, list):
                    if len(rates) == 2:
                        if not isinstance(rates[0], tuple):
                            raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
                        if not isinstance(rates[1], tuple):
                            raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
                        # Set rates
                        entry.meter_config.cir = rates[0][0]
                        entry.meter_config.cburst = rates[0][1]
                        entry.meter_config.pir = rates[1][0]
                        entry.meter_config.pburst = rates[1][1]
                    else:
                        raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
                else:
                    raise Exception('rates is not in the specified format [(cir, cburst), (pir, pburst)].')
            else:
                raise Exception('table {} has no direct meter attached.'.format(table_name))

        # DirectCounter
        if pkts:
            if entry._direct_counter:
                direct_counter_type = entry._direct_counter.spec.unit
                if direct_counter_type in [CounterType.packets.value, CounterType.both.value]:
                    entry.counter_data.packet_count = pkts
            else:
                raise Exception('table {} has no direct counter attached.'.format(table_name))

        if byts:
            if entry._direct_counter:
                direct_counter_type = entry._direct_counter.spec.unit
                if direct_counter_type in [CounterType.bytes.value, CounterType.both.value]:
                    entry.counter_data.byte_count = byts
            else:
                raise Exception('table {} has no direct counter attached.'.format(table_name))

        entry.modify()

    @handle_bad_input
    def table_clear(self, table_name):
        """Clears all entries in a match table (direct or indirect), 
        but not the default entry.
        
        Args:
            table_name (str): name of the table
        """
        print('Deleting all entries of: '+table_name)
        entry = api.TableEntry(self.client, self.context, table_name).read(function=lambda x: x.delete())

    ## DirectCounters
    @handle_bad_input
    def direct_counter_read(self, direct_counter_name, match_keys, prio=0):
        """Reads direct counter values.

        Args:
            direct_counter_name (str)   : name of the direct counter
            match_keys (list)           : values to match (each value is a :py:class:`str`) used
                                          to identify the entry
            prio (int)                  : priority in ternary match (used to identify the table
                                          entry to which the direct counter is attached)

        Returns:
            tuple: ``(byte_count, packet_count)`` where:

            - ``byte_count`` is the number of bytes counted;
            - ``packet_count`` is the number of packets counted.

        Note:
            __ https://p4.org/p4runtime/spec/v1.3.0/P4Runtime-Spec.html#sec-counterentry-directcounterentry

            P4Runtime does not distinguish between the different counter types, i.e. counters are
            always considered of **PACKETS_AND_BYTES** and both values are returned. It is user's responsability
            to use only the correct value (see `here`__).
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
        entry = next(entry.read())
        return entry.byte_count, entry.packet_count

    @handle_bad_input
    def direct_counter_write(self, direct_counter_name, match_keys, prio=0, pkts=0, byts=0):
        """Writes direct counter values. If no values are specified, the counter is reset.

        Args:
            direct_counter_name (str)   : name of the direct counter
            match_keys (list)           : values to match (each value is a :py:class:`str`) used
                                          to identify the entry
            prio (int)                  : priority in ternary match (used to identify the table
                                          entry to which the direct counter is attached)
            pkts (int)                  : number of packets to write (default: 0)
            byts (int)                  : number of bytes to write (default: 0)

        Note:
            There are three types of counters:

            - **BYTES**, only the field ``byts`` is written and the value of ``pkts`` is ignored.
            - **PACKETS**, only the field ``pkts`` is written and the value of ``byts`` is ignored.
            - **PACKETS_AND_BYTES**, both ``byts`` and ``pkts`` are written.
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

    @handle_bad_input
    def direct_counter_reset(self, direct_counter_name):
        """Resets all the direct counters values.

        Args:
            direct_counter_name (str): name of the direct counter
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
    @handle_bad_input
    def direct_meter_array_set_rates(self, direct_meter_name, rates):
        """Configures rates for an entire direct meter array.

        Args:
            direct_meter_name (str): name of the direct meter
            rates (list)           : ``[(cir, cburst), (pir, pburst)]``

        Note:
            ``cir`` and ``pir`` use units/second, ``cbursts`` and ``pburst`` use units 
            where units is bytes or packets, depending on the meter type.
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

    @handle_bad_input
    def direct_meter_set_rates(self, direct_meter_name, match_keys, prio=0, rates=None):
        """Configures rates for a single direct meter entry.

        Args:
            direct_meter_name (str)     : name of the direct meter
            match_keys (list)           : values to match (each value is a :py:class:`str`)
                                          used to identify the entry
            prio (int)                  : priority in ternary match (used to identify the table
                                          entry to which the direct meter is attached)
            rates (list)                : ``[(cir, cburst), (pir, pburst)]`` (default: None, i.e.
                                          all packets are marked as green)
        
        Note:
            ``cir`` and ``pir`` use units/second, ``cbursts`` and ``pburst`` use units 
            where units is bytes or packets, depending on the meter type.
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

    @handle_bad_input
    def direct_meter_get_rates(self, direct_meter_name, match_keys, prio=0):
        """Retrieves rates for a direct meter.

        Args:
            direct_meter_name (str): name of the direct meter
            match_keys (list)      : values to match (each value is a :py:class:`str`)
                                     used to identify the entry
            prio (int)             : priority in ternary match (used to identify the table
        
        Return:
            list: ``[(cir, cburst), (pir, pburst)]`` if meter is configured, **None** otherwise

        Note:
            ``cir`` and ``pir`` use units/second, ``cbursts`` and ``pburst`` use units 
            where units is bytes or packets, depending on the meter type.
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

        entry = next(entry.read())

        return [(entry.cir, entry.cburst), (entry.pir, entry.pburst)]

    ## Counters
    @handle_bad_input
    def counter_read(self, counter_name, index):
        """Reads counter value.

        Args:
            counter_name (str): name of the counter
            index (int)       : index of the counter to read (first element is at ``0``)

        Returns:
            tuple: ``(byte_count, packet_count)`` where:

            - ``byte_count`` is the number of bytes counted;
            - ``packet_count`` is the number of bytes counted.

        Note:
            __ https://p4.org/p4runtime/spec/v1.3.0/P4Runtime-Spec.html#sec-counterentry-directcounterentry

            P4Runtime does not distinguish between the different counter types, i.e. counters are
            always considered of **PACKETS_AND_BYTES** and both values are returned. It is user's responsability
            to use only the correct value (see `here`__).
        """
        print('Reading counter: "{}"'.format(counter_name))
        entry = api.CounterEntry(self.client, self.context, counter_name)

        print('index: {}'.format(index))
        entry.index = index
        
        entry = next(entry.read())
        return entry.byte_count, entry.packet_count

    @handle_bad_input
    def counter_write(self, counter_name, index, pkts=0, byts=0):
        """Writes counter values. If no values are specified, the counter is reset.

        Args:
            counter_name (str): name of the counter
            index (int)       : index of the counter to write (first element is at ``0``)
            pkts (int)        : number of packets to write (default: ``0``)
            byts (int)        : number of bytes to write (default: ``0``)
        
        There are three types of counters:

        - **BYTES**, only the field ``byts`` is written and the value of ``pkts`` is ignored.
        - **PACKETS**, only the field ``pkts`` is written and the value of ``byts`` is ignored.
        - **PACKETS_AND_BYTES**, both ``byts`` and ``pkts`` are written.
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

    @handle_bad_input
    def counter_reset(self, counter_name):
        """Resets all the counters values.

        Args:
            counter_name (str): name of the counter
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
    @handle_bad_input
    def meter_array_set_rates(self, meter_name, rates):
        """Configures rates for an entire meter array.

        Args:
            meter_name (str): name of the meter
            rates (list)    : ``[(cir, cburst), (pir, pburst)]``

        Note:
            ``cir`` and ``pir`` use units/second, ``cbursts`` and ``pburst`` use units 
            where units is bytes or packets, depending on the meter type.
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

    @handle_bad_input
    def meter_set_rates(self, meter_name, index, rates):
        """Configures rates for a single  meter entry.

        Args:
            meter_name (str): name of the meter
            rates (list)    : ``[(cir, cburst), (pir, pburst)]`` (default: **None**, i.e.
                              all packets are marked as **GREEN**)
            index (int)     : index of the meter to set (first element is at ``0``)
        
        Note:
            ``cir`` and ``pir`` use units/second, ``cbursts`` and ``pburst`` use units 
            where units is bytes or packets, depending on the meter type.
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

    @handle_bad_input
    def meter_get_rates(self, meter_name, index):
        """Retrieves rates for a meter.

        Args:
            meter_name (str): name of the meter
            index (int)     : index of the meter to read (first element is at ``0``)
        
        Return:
            list: ``[(cir, cburst), (pir, pburst)]`` if meter is configured, **None** otherwise.

        Note:
            ``cir`` and ``pir`` use units/second, ``cbursts`` and ``pburst`` use units 
            where units is bytes or packets, depending on the meter type.
        """
        print('Reading rates of meter: "{}"'.format(meter_name))
        entry = api.MeterEntry(self.client, self.context, meter_name)
        
        print('index: {}'.format(index))
        entry.index = index

        entry = next(entry.read())

        return [(entry.cir, entry.cburst), (entry.pir, entry.pburst)]

    ## MulticastGroups
    @handle_bad_input
    def mc_mgrp_create(self, mgrp, ports=[], instances=None):
        """Creates multicast group.

        Args:
            mgrp (int)      : multicast group *id*
            ports (list)    : list of port numbers to add to the multicast group
                              (each port number is a :py:class:`int`)
            instances (list): list of instances of the corresponding ports
                              (each instance is a :py:class:`int`)

        A replica is logically a tuple ``(port, instance)`` which has to be unique 
        within the same multicast group. Instances can be explicitly assigned to ports by 
        passing the list instances to this function. If the list instances is not
        specified, then the instance number is set to ``0`` for all the replicas by default.

        Note:
            ``mgrp`` must be larger than ``0``. If ``ports`` is an empty list, 
            then the packets are not multicasted to any port.
        """
        print('Creating multicast group: {}'.format(mgrp))
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
                    entry.add(ports[i], instances[i])
        else:
            for i in range(len(ports)):
                entry.add(ports[i])

        entry.insert()
    
    @handle_bad_input
    def mc_mgrp_destroy(self, mgrp):
        """Destroys multicast group.

        Args:
            mgrp (int): multicast group *id*

        Note:
            ``mgrp`` must be larger than ``0``.
        """
        print('Destroying multicast group: {}'.format(mgrp))
        entry = api.MulticastGroupEntry(self.client, self.context, mgrp)
        entry.delete()

    @handle_bad_input
    def mc_set_replicas(self, mgrp, ports=[], instances=None):
        """Sets replicas for multicast group.

        Args:
            mgrp (int)      : multicast group *id*
            ports (list)    : list of port numbers to add to the multicast group
                              (each port number is a :py:class:`int`)
            instances (list): list of instances of the corresponding ports
                              (each instance is a :py:class:`int`)

        A replica is logically a tuple ``(port, instance)`` which has to be unique 
        within the same multicast group. Instances can be explicitly assigned to ports by 
        passing the list instances to this function. If the list instances is not
        specified, then the instance number is set to ``0`` for all the replicas by default.

        Note:
            ``mgrp`` must be larger than ``0``. If ``ports`` is an empty list,
            then the packets are not multicasted to any port.
        """
        print('Setting replicas of multicast group: {}'.format(mgrp))
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
                    entry.add(ports[i], instances[i])
        else:
            for i in range(len(ports)):
                entry.add(ports[i])

        entry.modify()

    @handle_bad_input
    def mc_get_replicas(self, mgrp):
        """Gets replicas which belog to a multicast group.

        Args:
            mgrp (int): multicast group *id*
        
        Returns:
            tuple: ``(ports, instances)`` where:

            - ``ports`` is a list of port numbers of the multicast group;
            - ``instances`` is list of instances of the corresponding ports.

        A replica is logically a tuple ``(port, instance)`` which has to be unique 
        within the same multicast group. Instances can be explicitly assigned to ports by 
        passing the list instances to this function. If the list instances is not
        specified, then the instance number is set to ``0`` for all the replicas by default.

        Note:
            ``mgrp`` must be greater than ``0``.
        """
        ports = []
        instances = []

        # Read MulticastGroup entries
        print('Reading replicas of multicast group: {}'.format(mgrp))
        entry = api.MulticastGroupEntry(self.client, self.context, mgrp)
        entry = entry.read()

        # Get replicas
        replicas = entry.replicas
        
        for replica in replicas:
            ports.append(replica.port)
            instances.append(replica.instance)

        return ports, instances

    ## CloseSession
    @handle_bad_input
    def cs_create(self, session_id, ports=[], instances=None, cos=0, packet_length=0):
        """Adds a packet cloning session.

        __ https://p4.org/p4-spec/docs/PSA-v1.1.0.html#sec-after-ingress

        Args:
            session_id (int)    : clone session *id*
            ports (list)        : list of port numbers to add to the clone session 
                                  (each port number is :py:class:`int`)
            instances (list)    : list of instances of the corresponding ports
                                  (each instance is :py:class:`int`)
            cos (int)           : Class of Service (see `here`__)
            packet_lentgth (int): maximal packet length in bytes (after which, packets are truncated)

        A replica is logically a tuple ``(port, instance)`` which has to be unique 
        within the same multicast group. Instances can be explicitly assigned to ports by 
        passing the list instances to this function. If the list instances is not
        specified, then the instance number is set to ``0`` for all the replicas by default.

        Note:
            By default, ``packet_length`` is set to ``0`` i.e. no truncation happens and 
            ``cos`` is set to ``0`` (normal packet classification). If ``ports`` is
            an empty list, then the packets are not cloned to any port.
        """
        print('Creating clone session: {}'.format(session_id))
        entry = api.CloneSessionEntry(self.client, self.context, session_id)

        if not isinstance(ports, list):
            raise TypeError('ports is not a list.')
        elif instances:
            if not isinstance(instances, list):
                raise TypeError('instances is not a list.')
            elif len(instances) != len(ports):
                raise Exception('instances and ports have different lengths.')
            else:
                for i in range(len(ports)):
                    entry.add(ports[i], instances[i])
        else:
            for i in range(len(ports)):
                entry.add(ports[i])

        entry.cos = cos
        entry.packet_length_bytes = packet_length

        entry.insert()

    @handle_bad_input
    def cs_destroy(self, session_id):
        """Removes a packet cloning session.

        Args:
            session_id (int): clone session *id*
        """
        print('Removing clone session: {}'.format(session_id))
        entry = api.CloneSessionEntry(self.client, self.context, session_id)
        entry.delete()

    @handle_bad_input
    def cs_set_replicas(self, session_id, ports=[], instances=None, cos=0, packet_length=0):
        """Configures a packet cloning session.

        __ https://p4.org/p4-spec/docs/PSA-v1.1.0.html#sec-after-ingress

        Args:
            session_id (int)    : clone session *id*
            ports (list)        : list of port numbers to add to the clone session
                                  (each port number is :py:class:`int`)
            instances (list)    : list of instances of the corresponding ports
                                  (each instance is :py:class:`int`)
            cos (int)           : Class of Service (see `here`__)
            packet_lentgth (int): maximal packet length in bytes (after which, packets are truncated)

        A replica is logically a tuple ``(port, instance)`` which has to be unique 
        within the same multicast group. Instances can be explicitly assigned to ports by 
        passing the list instances to this function. If the list instances is not
        specified, then the instance number is set to ``0`` for all the replicas by default.

        Note:
            By default, the ``packet_length`` is set to ``0`` i.e. no truncation happens and 
            ``cos`` is set to ``0`` (normal packet classification). If ``ports`` is an empty 
            list, then the packets are not cloned to any port.
        """
        print('Setting replicas of clone session: {}'.format(session_id))
        entry = api.CloneSessionEntry(self.client, self.context, session_id)

        if not isinstance(ports, list):
            raise TypeError('ports is not a list.')
        elif instances:
            if not isinstance(instances, list):
                raise TypeError('instances is not a list.')
            elif len(instances) != len(ports):
                raise Exception('instances and ports have different lengths.')
            else:
                for i in range(len(ports)):
                    entry.add(ports[i], instances[i])
        else:
            for i in range(len(ports)):
                entry.add(ports[i])

        entry.cos = cos
        entry.packet_length_bytes = packet_length

        entry.modify()

    @handle_bad_input
    def cd_get_replicas(self, session_id):
        """Gets replicas which belog to a clone session.

        Args:
            session_id (int): clone session id
        
        Returns:
            tuple: ``(ports, instances)`` where:

            - ``ports`` is a list of port numbers of the clone session;
            - ``instances`` is a list of instances of the corresponding ports.

        A replica is logically a tuple ``(port, instance)`` which has to be unique 
        within the same multicast group.
        """
        ports = []
        instances = []

        # Read MulticastGroup entries
        print('Reading replicas of clone session: {}'.format(session_id))
        entry = api.CloneSessionEntry(self.client, self.context, session_id)
        entry = entry.read()

        # Get replicas
        replicas = entry.replicas
        
        for replica in replicas:
            ports.append(replica.port)
            instances.append(replica.instance)

        return ports, instances

    ## Digests
    @handle_bad_input
    def digest_enable(self, digest_name, max_timeout_ns=0, max_list_size=1, ack_timeout_ns=0):
        """Enables and configure the digests generation of the switch.

        Args:
            digest_name (str)   : name of the digest (the name is shown in the P4 runtime information file
                                  generated by the compiler)
            max_timeout_ns (int): the maximum server buffering delay in nanoseconds for an outstanding digest message
            max_list_size (int) : the maximum digest list size (in number of digest messages) sent by the server
                                  to the client as a single ``DigestList`` Protobuf message
            ack_timeout_ns (int): the timeout in nanoseconds that a server must wait for a digest list acknowledgement 
                                  from the client before new digest messages can be generated for the same learned data

        By default, ``max_timeout_ns`` is set to ``0``, i.e. the server should generate a ``DigestList`` 
        message for every digest message generated by the data plane.

        By default, ``max_list_size`` is set to ``1``, i.e. the server should generate a ``DigestList`` 
        message for every digest message generated by the data plane.

        By default, ``ack_timeout_ns`` is set to ``0``, i.e. the cache of digests not yet acknowledged must 
        always be an empty set.

        Note:
            P4Runtime only supports named digests, i.e. those declared in P4 with the following syntax:
            ``digest<named_struct_type>(1, {struct_field_1, struct_field_2, ...})`` where ``named_struct_type`` must 
            be explicited and previously defined. The name of the digest for the configuration's sake 
            is the name of the struct type (i.e. ``named_struct_type``).            
        """
        print('Enabling digest: {}'.format(digest_name))
        entry = api.DigestEntry(self.client, self.context, digest_name)

        entry.max_timeout_ns = max_timeout_ns
        entry.max_list_size = max_list_size
        entry.ack_timeout_ns = ack_timeout_ns

        entry.insert()

    @handle_bad_input
    def digest_set_conf(self, digest_name, max_timeout_ns=0, max_list_size=1, ack_timeout_ns=0):
        """Configures the digests generation of the switch.

        Args:
            digest_name (str)   : name of the digest (the name is shown in the P4 runtime information file
                                  generated by the compiler)
            max_timeout_ns (int): the maximum server buffering delay in nanoseconds for an outstanding digest message
            max_list_size (int) : the maximum digest list size (in number of digest messages) sent by the server
                                  to the client as a single ``DigestList`` Protobuf message
            ack_timeout_ns (int): the timeout in nanoseconds that a server must wait for a digest list acknowledgement 
                                  from the client before new digest messages can be generated for the same learned data

        By default, ``max_timeout_ns`` is set to ``0``, i.e. the server should generate a ``DigestList`` 
        message for every digest message generated by the data plane.

        By default, ``max_list_size`` is set to ``1``, i.e. the server should generate a ``DigestList`` 
        message for every digest message generated by the data plane.

        By default, ``ack_timeout_ns`` is set to ``0``, i.e. the cache of digests not yet acknowledged must 
        always be an empty set.

        Note:
            P4Runtime only supports named digests, i.e. those declared in P4 with the following syntax:
            ``digest<named_struct_type>(1, {struct_field_1, struct_field_2, ...})`` where ``named_struct_type`` must 
            be explicited and previously defined. The name of the digest for the configuration's sake 
            is the name of the struct type (i.e. ``named_struct_type``).
        """
        print('Configuring digest: {}'.format(digest_name))
        entry = api.DigestEntry(self.client, self.context, digest_name)

        entry.max_timeout_ns = max_timeout_ns
        entry.max_list_size = max_list_size
        entry.ack_timeout_ns = ack_timeout_ns

        entry.modify()

    @handle_bad_input
    def digest_get_conf(self, digest_name):
        """Enables and configure the digests generation of the switch.

        Args:
            digest_name (str): name of the digest (the name is shown in the P4 runtime information file
                                  generated by the compiler)

        Returns:
            tuple: ``(max_timeout_ns, max_list_size, ack_timeout_ns)`` where:
                   
            - ``max_timeout_ns`` is the maximum server buffering delay in nanoseconds for an outstanding digest message;
            - ``max_list_size`` is the maximum digest list size (in number of digest messages) sent by the server
              to the client as a single DigestList Protobuf message;
            - ``ack_timeout_ns`` is the timeout in nanoseconds that a server must wait for a digest list acknowledgement
              from the client before new digest messages can be generated for the same learned data.

        Note:
            P4Runtime only supports named digests, i.e. those declared in P4 with the following syntax:
            ``digest<named_struct_type>(1, {struct_field_1, struct_field_2, ...})`` where ``named_struct_type`` must 
            be explicited and previously defined. The name of the digest for the configuration's sake 
            is the name of the struct type (i.e. ``named_struct_type``).
        """
        print('Enabling digest: {}'.format(digest_name))
        entry = api.DigestEntry(self.client, self.context, digest_name)
        entry = next(entry.read())

        max_timeout_ns = entry.max_timeout_ns
        max_list_size = entry.max_list_size
        ack_timeout_ns = entry.ack_timeout_ns

        return max_timeout_ns, max_list_size, ack_timeout_ns