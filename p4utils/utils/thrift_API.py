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
#
# Modified version of the runtime_CLI.py from behavioural model
# Edgar Costa (cedgar@ethz.ch)

from collections import Counter
import os
import sys
import struct
import json
from functools import wraps
import bmpy_utils as utils


from bm_runtime.standard import Standard
from bm_runtime.standard.ttypes import *
try:
    from bm_runtime.simple_pre import SimplePre
except:
    pass
try:
    from bm_runtime.simple_pre_lag import SimplePreLAG
except:
    pass


def enum(type_name, *sequential, **named):
    enums = dict(list(zip(sequential, list(range(len(sequential))))), **named)
    reverse = dict((value, key) for key, value in enums.items())

    @staticmethod
    def to_str(x):
        return reverse[x]
    enums['to_str'] = to_str

    @staticmethod
    def from_str(x):
        return enums[x]

    enums['from_str'] = from_str
    return type(type_name, (), enums)


PreType = enum('PreType', 'none', 'SimplePre', 'SimplePreLAG')
MeterType = enum('MeterType', 'packets', 'bytes')
TableType = enum('TableType', 'simple', 'indirect', 'indirect_ws')
ResType = enum('ResType', 'table', 'action_prof', 'action', 'meter_array',
               'counter_array', 'register_array', 'parse_vset')


def bytes_to_string(byte_array):
    form = 'B' * len(byte_array)
    return struct.pack(form, *byte_array)

def table_error_name(x):
    return TableOperationErrorCode._VALUES_TO_NAMES[x]


class MatchType:
    EXACT = 0
    LPM = 1
    TERNARY = 2
    VALID = 3
    RANGE = 4

    @staticmethod
    def to_str(x):
        return {0: "exact", 1: "lpm", 2: "ternary", 3: "valid", 4: "range"}[x]

    @staticmethod
    def from_str(x):
        return {"exact": 0, "lpm": 1, "ternary": 2, "valid": 3, "range": 4}[x]


class Table:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.match_type_ = None
        self.actions = {}
        self.key = []
        self.default_action = None
        self.type_ = None
        self.support_timeout = False
        self.action_prof = None

    def num_key_fields(self):
        return len(self.key)

    def key_str(self):
        return ",\t".join([name + "(" + MatchType.to_str(t) + ", " + str(bw) + ")" for name, t, bw in self.key])

    def table_str(self):
        ap_str = "implementation={}".format(
            "None" if not self.action_prof else self.action_prof.name)
        return "{0:30} [{1}, mk={2}]".format(self.name, ap_str, self.key_str())

    def get_action(self, action_name, suffix_lookup_map):
        key = ResType.action, action_name
        action = suffix_lookup_map.get(key, None)
        if action is None or action.name not in self.actions:
            return None
        return action


class ActionProf:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.with_selection = False
        self.actions = {}
        self.ref_cnt = 0

    def action_prof_str(self):
        return "{0:30} [{1}]".format(self.name, self.with_selection)

    def get_action(self, action_name, suffix_lookup_map):
        key = ResType.action, action_name
        action = suffix_lookup_map.get(key, None)
        if action is None or action.name not in self.actions:
            return None
        return action


class Action:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.runtime_data = []

    def num_params(self):
        return len(self.runtime_data)

    def runtime_data_str(self):
        return ",\t".join([name + "(" + str(bw) + ")" for name, bw in self.runtime_data])

    def action_str(self):
        return "{0:30} [{1}]".format(self.name, self.runtime_data_str())


class MeterArray:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.type_ = None
        self.is_direct = None
        self.size = None
        self.binding = None
        self.rate_count = None

    def meter_str(self):
        return "{0:30} [{1}, {2}]".format(self.name, self.size,
                                          MeterType.to_str(self.type_))


class CounterArray:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.is_direct = None
        self.size = None
        self.binding = None

    def counter_str(self):
        return "{0:30} [{1}]".format(self.name, self.size)


class RegisterArray:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.width = None
        self.size = None

    def register_str(self):
        return "{0:30} [{1}]".format(self.name, self.size)


class ParseVSet:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.bitwidth = None

    def parse_vset_str(self):
        return "{0:30} [compressed bitwidth:{1}]".format(
            self.name, self.bitwidth)


class SwitchInfo(object):

    def __init__(self):

        self.tables = {}
        self.action_profs = {}
        self.actions = {}
        self.meter_arrays = {}
        self.counter_arrays = {}
        self.register_arrays = {}
        self.custom_crc_calcs = {}
        self.parse_vsets = {}

        # maps (object type, unique suffix) to object
        self.suffix_lookup_map = {}

    def reset_config(self):
        self.tables.clear()
        self.action_profs.clear()
        self.actions.clear()
        self.meter_arrays.clear()
        self.counter_arrays.clear()
        self.register_arrays.clear()
        self.custom_crc_calcs.clear()
        self.suffix_lookup_map.clear()
        self.parse_vsets.clear()

    def load_json_config(self, standard_client=None, json_path=None):
        def read_conf():
            if json_path:
                if standard_client is not None:
                    utils.check_JSON_md5(standard_client, json_path)
                with open(json_path, 'r') as f:
                    return f.read()
            else:
                assert(standard_client is not None)
                try:
                    json_cfg = standard_client.bm_get_config()
                except:
                    sys.exit(1)
                return json_cfg

        self.load_json_str(read_conf())

    def load_json_str(self, json_str, architecture_spec=None):
        def get_header_type(header_name, j_headers):
            for h in j_headers:
                if h["name"] == header_name:
                    return h["header_type"]
            assert(0)

        def get_field_bitwidth(header_type, field_name, j_header_types):
            for h in j_header_types:
                if h["name"] != header_type: continue
                for t in h["fields"]:
                    # t can have a third element (field signedness)
                    f, bw = t[0], t[1]
                    if f == field_name:
                        return bw
            assert(0)

        self.reset_config()
        json_ = json.loads(json_str)

        def get_json_key(key):
            return json_.get(key, [])

        for j_action in get_json_key("actions"):
            action = Action(j_action["name"], j_action["id"])
            for j_param in j_action["runtime_data"]:
                action.runtime_data += [(j_param["name"], j_param["bitwidth"])]

            self.actions[j_action["name"]] = action

        for j_pipeline in get_json_key("pipelines"):
            if "action_profiles" in j_pipeline:  # new JSON format
                for j_aprof in j_pipeline["action_profiles"]:
                    action_prof = ActionProf(j_aprof["name"], j_aprof["id"])
                    action_prof.with_selection = "selector" in j_aprof
                    self.action_profs[j_aprof["name"]] = action_prof

            for j_table in j_pipeline["tables"]:
                table = Table(j_table["name"], j_table["id"])
                table.match_type = MatchType.from_str(j_table["match_type"])
                table.type_ = TableType.from_str(j_table["type"])
                table.support_timeout = j_table["support_timeout"]
                for action in j_table["actions"]:
                    table.actions[action] = self.actions[action]

                if table.type_ in {TableType.indirect, TableType.indirect_ws}:
                    if "action_profile" in j_table:
                        action_prof = self.action_profs[j_table["action_profile"]]
                    else:  # for backward compatibility
                        assert("act_prof_name" in j_table)
                        action_prof = ActionProf(j_table["act_prof_name"],
                                                 table.id_)
                        action_prof.with_selection = "selector" in j_table

                    action_prof.actions.update(table.actions)
                    action_prof.ref_cnt += 1
                    self.action_profs[j_table["act_prof_name"]] = action_prof
                    table.action_prof = action_prof

                for j_key in j_table["key"]:
                    target = j_key["target"]
                    match_type = MatchType.from_str(j_key["match_type"])
                    if match_type == MatchType.VALID:
                        field_name = target + "_valid"
                        bitwidth = 1
                    elif target[1] == "$valid$":
                        field_name = target[0] + "_valid"
                        bitwidth = 1
                    else:
                        field_name = ".".join(target)
                        header_type = get_header_type(target[0],
                                                      json_["headers"])
                        bitwidth = get_field_bitwidth(header_type, target[1],
                                                      json_["header_types"])
                    table.key += [(field_name, match_type, bitwidth)]

                    self.tables[j_table["name"]] = table

        for j_meter in get_json_key("meter_arrays"):
            meter_array = MeterArray(j_meter["name"], j_meter["id"])
            if "is_direct" in j_meter and j_meter["is_direct"]:
                meter_array.is_direct = True
                meter_array.binding = j_meter["binding"]
            else:
                meter_array.is_direct = False
                meter_array.size = j_meter["size"]
            meter_array.type_ = MeterType.from_str(j_meter["type"])
            meter_array.rate_count = j_meter["rate_count"]

            self.meter_arrays[j_meter["name"]] = meter_array


        for j_counter in get_json_key("counter_arrays"):
            counter_array = CounterArray(j_counter["name"], j_counter["id"])
            counter_array.is_direct = j_counter["is_direct"]
            if counter_array.is_direct:
                counter_array.binding = j_counter["binding"]
            else:
                counter_array.size = j_counter["size"]

            self.counter_arrays[j_counter["name"]] = counter_array

        for j_register in get_json_key("register_arrays"):
            register_array = RegisterArray(j_register["name"], j_register["id"])
            register_array.size = j_register["size"]
            register_array.width = j_register["bitwidth"]

            self.register_arrays[j_register["name"]] = register_array

        for j_calc in get_json_key("calculations"):
            calc_name = j_calc["name"]
            if j_calc["algo"] == "crc16_custom":
                self.custom_crc_calcs[calc_name] = 16
            elif j_calc["algo"] == "crc32_custom":
                self.custom_crc_calcs[calc_name] = 32

        for j_parse_vset in get_json_key("parse_vsets"):
            parse_vset = ParseVSet(j_parse_vset["name"], j_parse_vset["id"])
            parse_vset.bitwidth = j_parse_vset["compressed_bitwidth"]

            self.parse_vsets[j_parse_vset["name"]] = parse_vset

        if architecture_spec is not None:
            # call architecture specific json parsing code
            architecture_spec(json_)

        # Builds a dictionary mapping (object type, unique suffix) to the object
        # (Table, Action, etc...). In P4_16 the object name is the fully-qualified
        # name, which can be quite long, which is why we accept unique suffixes as
        # valid identifiers.
        # Auto-complete does not support suffixes, only the fully-qualified names,
        # but that can be changed in the future if needed.
        suffix_count = Counter()
        for res_type, res_dict in [
                (ResType.table, self.tables), (ResType.action_prof, self.action_profs),
                (ResType.action, self.actions), (ResType.meter_array, self.meter_arrays),
                (ResType.counter_array, self.counter_arrays),
                (ResType.register_array, self.register_arrays),
                (ResType.parse_vset, self.parse_vsets)]:
            for name, res in res_dict.items():
                suffix = None
                for s in reversed(name.split('.')):
                    suffix = s if suffix is None else s + '.' + suffix
                    key = (res_type, suffix)
                    self.suffix_lookup_map[key] = res
                    suffix_count[key] += 1
        #checks if a table is repeated, in that case it removes the only suffix entries
        for key, c in suffix_count.items():
            if c > 1:
                del self.suffix_lookup_map[key]


class UIn_Error(Exception):
    def __init__(self, info=""):
        self.info = info

    def __str__(self):
        return self.info


class UIn_ResourceError(UIn_Error):
    def __init__(self, res_type, name):
        self.res_type = res_type
        self.name = name

    def __str__(self):
        return "Invalid {} name ({})".format(self.res_type, self.name)


class UIn_MatchKeyError(UIn_Error):
    def __init__(self, info=""):
        self.info = info

    def __str__(self):
        return self.info


class UIn_RuntimeDataError(UIn_Error):
    def __init__(self, info=""):
        self.info = info

    def __str__(self):
        return self.info


class CLI_FormatExploreError(Exception):
    def __init__(self):
        pass


class UIn_BadParamError(UIn_Error):
    def __init__(self, info=""):
        self.info = info

    def __str__(self):
        return self.info


class UIn_BadIPv4Error(UIn_Error):
    def __init__(self):
        pass


class UIn_BadIPv6Error(UIn_Error):
    def __init__(self):
        pass


class UIn_BadMacError(UIn_Error):
    def __init__(self):
        pass


def ipv4Addr_to_bytes(addr):
    if not '.' in addr:
        raise CLI_FormatExploreError()
    s = addr.split('.')
    if len(s) != 4:
        raise UIn_BadIPv4Error()
    try:
        return [int(b) for b in s]
    except:
        raise UIn_BadIPv4Error()


def macAddr_to_bytes(addr):
    if not ':' in addr:
        raise CLI_FormatExploreError()
    s = addr.split(':')
    if len(s) != 6:
        raise UIn_BadMacError()
    try:
        return [int(b, 16) for b in s]
    except:
        raise UIn_BadMacError()


def ipv6Addr_to_bytes(addr):
    from ipaddr import IPv6Address
    if not ':' in addr:
        raise CLI_FormatExploreError()
    try:
        ip = IPv6Address(addr)
    except:
        raise UIn_BadIPv6Error()
    try:
        return [ord(b) for b in ip.packed]
    except:
        raise UIn_BadIPv6Error()


def int_to_bytes(i, num):
    byte_array = []
    while i > 0:
        byte_array.append(i % 256)
        i = i // 256
        num -= 1
    if num < 0:
        raise UIn_BadParamError("Parameter is too large")
    while num > 0:
        byte_array.append(0)
        num -= 1
    byte_array.reverse()
    return byte_array


def parse_param(input_str, bitwidth):
    if bitwidth == 32:
        try:
            return ipv4Addr_to_bytes(input_str)
        except CLI_FormatExploreError:
            pass
        except UIn_BadIPv4Error:
            raise UIn_BadParamError("Invalid IPv4 address")
    elif bitwidth == 48:
        try:
            return macAddr_to_bytes(input_str)
        except CLI_FormatExploreError:
            pass
        except UIn_BadMacError:
            raise UIn_BadParamError("Invalid MAC address")
    elif bitwidth == 128:
        try:
            return ipv6Addr_to_bytes(input_str)
        except CLI_FormatExploreError:
            pass
        except UIn_BadIPv6Error:
            raise UIn_BadParamError("Invalid IPv6 address")
    try:
        input_ = int(input_str, 0)
    except:
        raise UIn_BadParamError(
            "Invalid input, could not cast to integer, try in hex with 0x prefix"
        )
    try:
        return int_to_bytes(input_, (bitwidth + 7) // 8)
    except UIn_BadParamError:
        raise


def parse_runtime_data(action, params):
    def parse_param_(field, bw):
        try:
            return parse_param(field, bw)
        except UIn_BadParamError as e:
            raise UIn_RuntimeDataError(
                "Error while parsing {} - {}".format(field, e)
            )

    bitwidths = [bw for(_, bw) in action.runtime_data]
    byte_array = []
    for input_str, bitwidth in zip(params, bitwidths):
        byte_array += [bytes_to_string(parse_param_(input_str, bitwidth))]
    return byte_array


_match_types_mapping = {
    MatchType.EXACT: BmMatchParamType.EXACT,
    MatchType.LPM: BmMatchParamType.LPM,
    MatchType.TERNARY: BmMatchParamType.TERNARY,
    MatchType.VALID: BmMatchParamType.VALID,
    MatchType.RANGE: BmMatchParamType.RANGE,
}


def parse_match_key(table, key_fields):

    def parse_param_(field, bw):
        try:
            return parse_param(field, bw)
        except UIn_BadParamError as e:
            raise UIn_MatchKeyError(
                "Error while parsing {} - {}".format(field, e)
            )

    params = []
    match_types = [t for (_, t, _) in table.key]
    bitwidths = [bw for (_, _, bw) in table.key]
    for idx, field in enumerate(key_fields):
        param_type = _match_types_mapping[match_types[idx]]
        bw = bitwidths[idx]
        if param_type == BmMatchParamType.EXACT:
            key = bytes_to_string(parse_param_(field, bw))
            param = BmMatchParam(type=param_type,
                                 exact=BmMatchParamExact(key))
        elif param_type == BmMatchParamType.LPM:
            try:
                prefix, length = field.split("/")
            except ValueError:
                raise UIn_MatchKeyError(
                    "Invalid LPM value {}, use '/' to separate prefix "
                    "and length".format(field))
            key = bytes_to_string(parse_param_(prefix, bw))
            param = BmMatchParam(type=param_type,
                                 lpm=BmMatchParamLPM(key, int(length)))
        elif param_type == BmMatchParamType.TERNARY:
            try:
                key, mask = field.split("&&&")
            except ValueError:
                raise UIn_MatchKeyError(
                    "Invalid ternary value {}, use '&&&' to separate key and "
                    "mask".format(field))
            key = bytes_to_string(parse_param_(key, bw))
            mask = bytes_to_string(parse_param_(mask, bw))
            if len(mask) != len(key):
                raise UIn_MatchKeyError(
                    "Key and mask have different lengths in expression {}".forma(field)
                )
            param = BmMatchParam(type=param_type,
                                 ternary=BmMatchParamTernary(key, mask))
        elif param_type == BmMatchParamType.VALID:
            key = bool(int(field))
            param = BmMatchParam(type=param_type,
                                 valid=BmMatchParamValid(key))
        elif param_type == BmMatchParamType.RANGE:
            try:
                start, end = field.split("->")
            except ValueError:
                raise UIn_MatchKeyError(
                    "Invalid range value {}, use '->' to separate range start "
                    "and range end".format(field))
            start = bytes_to_string(parse_param_(start, bw))
            end = bytes_to_string(parse_param_(end, bw))
            if len(start) != len(end):
                raise UIn_MatchKeyError(
                    "start and end have different lengths in expression {}".format(field)
                )
            if start > end:
                raise UIn_MatchKeyError(
                    "start is less than end in expression {}".format(field)
                )
            param = BmMatchParam(type=param_type,
                                 range=BmMatchParamRange(start, end))
        else:
            assert(0)
        params.append(param)
    return params


def printable_byte_str(s):
    return ":".join([format(c, "02x") for c in s])


def BmMatchParam_to_str(self):
    return BmMatchParamType._VALUES_TO_NAMES[self.type] + "-" +\
        (self.exact.to_str() if self.exact else "") +\
        (self.lpm.to_str() if self.lpm else "") +\
        (self.ternary.to_str() if self.ternary else "") +\
        (self.valid.to_str() if self.valid else "") +\
        (self.range.to_str() if self.range else "")


def BmMatchParamExact_to_str(self):
    return printable_byte_str(self.key)


def BmMatchParamLPM_to_str(self):
    return printable_byte_str(self.key) + "/" + str(self.prefix_length)


def BmMatchParamTernary_to_str(self):
    return printable_byte_str(self.key) + " &&& " + printable_byte_str(self.mask)


def BmMatchParamValid_to_str(self):
    return ""


def BmMatchParamRange_to_str(self):
    return printable_byte_str(self.start) + " -> " + printable_byte_str(self.end_)


BmMatchParam.to_str = BmMatchParam_to_str
BmMatchParamExact.to_str = BmMatchParamExact_to_str
BmMatchParamLPM.to_str = BmMatchParamLPM_to_str
BmMatchParamTernary.to_str = BmMatchParamTernary_to_str
BmMatchParamValid.to_str = BmMatchParamValid_to_str
BmMatchParamRange.to_str = BmMatchParamRange_to_str


def parse_pvs_value(input_str, bitwidth):
    try:
        input_ = int(input_str, 0)
    except:
        raise UIn_BadParamError(
            "Invalid input, could not cast to integer, try in hex with 0x prefix"
        )
    max_v = (1 << bitwidth) - 1
    # bmv2 does not perform this check when receiving the value (and does not
    # truncate values which are too large), so we perform this check
    # client-side.
    if input_ > max_v:
        raise UIn_BadParamError(
            "Input is too large, it should fit within {} bits".format(bitwidth))
    try:
        v = int_to_bytes(input_, (bitwidth + 7) / 8)
    except UIn_BadParamError:
        # should not happen because of check above
        raise
    return bytes_to_string(v)

# services is [(service_name, client_class), ...]


def thrift_connect(thrift_ip, thrift_port, services):
    return utils.thrift_connect(thrift_ip, thrift_port, services)


def handle_bad_input(f):
    @wraps(f)
    def handle(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except UIn_MatchKeyError as e:
            print("Invalid match key:", e)
        except UIn_RuntimeDataError as e:
            print("Invalid runtime data:", e)
        except UIn_Error as e:
            print("Error:", e)
        except InvalidTableOperation as e:
            error = TableOperationErrorCode._VALUES_TO_NAMES[e.code]
            print("Invalid table operation ({})".format(error))
        except InvalidCounterOperation as e:
            error = CounterOperationErrorCode._VALUES_TO_NAMES[e.code]
            print("Invalid counter operation ({})".format(error))
        except InvalidMeterOperation as e:
            error = MeterOperationErrorCode._VALUES_TO_NAMES[e.code]
            print("Invalid meter operation ({})".format(error))
        except InvalidRegisterOperation as e:
            error = RegisterOperationErrorCode._VALUES_TO_NAMES[e.code]
            print("Invalid register operation ({})".format(error))
        except InvalidLearnOperation as e:
            error = LearnOperationErrorCode._VALUES_TO_NAMES[e.code]
            print("Invalid learn operation ({})".format(error))
        except InvalidSwapOperation as e:
            error = SwapOperationErrorCode._VALUES_TO_NAMES[e.code]
            print("Invalid swap operation ({})".format(error))
        except InvalidDevMgrOperation as e:
            error = DevMgrErrorCode._VALUES_TO_NAMES[e.code]
            print("Invalid device manager operation ({})".format(error))
        except InvalidCrcOperation as e:
            error = CrcErrorCode._VALUES_TO_NAMES[e.code]
            print("Invalid crc operation ({})".format(error))
        except InvalidParseVSetOperation as e:
            error = ParseVSetOperationErrorCode._VALUES_TO_NAMES[e.code]
            print("Invalid parser value set operation ({})".format(error))
    return handle


def handle_bad_input_mc(f):
    @wraps(f)
    def handle(*args, **kwargs):
        pre_type = args[0].pre_type
        if pre_type == PreType.none:
            return handle_bad_input(f)(*args, **kwargs)
        EType = {
            PreType.SimplePre: SimplePre.InvalidMcOperation,
            PreType.SimplePreLAG: SimplePreLAG.InvalidMcOperation
        }[pre_type]
        Codes = {
            PreType.SimplePre: SimplePre.McOperationErrorCode,
            PreType.SimplePreLAG: SimplePreLAG.McOperationErrorCode
        }[pre_type]
        try:
            return handle_bad_input(f)(*args, **kwargs)
        except EType as e:
            error = Codes._VALUES_TO_NAMES[e.code]
            print("Invalid PRE operation ({})".format(error))
    return handle


def deprecated_act_prof(substitute, with_selection=False,
                        strictly_deprecated=True):
    # need two levels here because our decorator takes arguments
    def deprecated_act_prof_(f):
        # not sure if this is the right place for it, if I want it to play nice
        # with @wraps
        if strictly_deprecated:
            f.__doc__ = "[DEPRECATED!] " + f.__doc__
            f.__doc__ += "\nUse '{}' instead".format(substitute)

        @wraps(f)
        def wrapper(obj, line):
            substitute_fn = getattr(obj, "do_" + substitute)
            args = line.split()
            obj.at_least_n_args(args, 1)
            table_name = args[0]
            table = obj.get_res("table", table_name, ResType.table)
            if with_selection:
                obj.check_indirect_ws(table)
            else:
                obj.check_indirect(table)
            assert(table.action_prof is not None)
            assert(table.action_prof.ref_cnt > 0)
            if strictly_deprecated and table.action_prof.ref_cnt > 1:
                raise UIn_Error(
                    "Legacy command does not work with shared action profiles")
            args[0] = table.action_prof.name
            if strictly_deprecated:
                # writing to stderr in case someone is parsing stdout
                sys.stderr.write(
                    "This is a deprecated command, use '{}' instead\n".format(
                        substitute))
            return substitute_fn(" ".join(args))
        # we add the handle_bad_input decorator "programatically"
        return handle_bad_input(wrapper)
    return deprecated_act_prof_

# thrift does not support unsigned integers


def hex_to_i16(h):
    if type(h) != int:
        h = int(h, 0)
    if (h > 0xFFFF):
        raise UIn_Error("Integer cannot fit within 16 bits")
    if (h > 0x7FFF):
        h -= 0x10000
    return h


def i16_to_hex(h):
    if type(h) != int:
        h = int(h)
    if (h & 0x8000):
        h += 0x10000
    return h


def hex_to_i32(h):
    if type(h) != int:
        h = int(h, 0)
    if (h > 0xFFFFFFFF):
        raise UIn_Error("Integer cannot fit within 32 bits")
    if (h > 0x7FFFFFFF):
        h -= 0x100000000
    return h


def i32_to_hex(h):
    if type(h) != int:
        h = int(h)
    if (h & 0x80000000):
        h += 0x100000000
    return h


def parse_bool(s):
    if s == "true" or s == "True" or s == True:
        return True
    if s == "false" or s  == "False" or s == False:
        return False
    try:
        s = int(s, 0)
        return bool(s)
    except:
        pass
    raise UIn_Error("Invalid bool parameter")


def hexstr(v):
    return "".join([format(c, "02x") for c in v])


class ThriftAPI(object):

    @staticmethod
    def get_thrift_services(pre_type):

        services = [("standard", Standard.Client)]

        if pre_type == PreType.SimplePre:
            services += [("simple_pre", SimplePre.Client)]
        elif pre_type == PreType.SimplePreLAG:
            services += [("simple_pre_lag", SimplePreLAG.Client)]
        else:
            services += [(None, None)]

        return services

    def __init__(self, thrift_port, thrift_ip, pre_type, json_path=None):

        if isinstance(pre_type, str):
            pre_type = PreType.from_str(pre_type)

        standard_client, mc_client = thrift_connect(thrift_ip,
                                                    thrift_port,
                                                    ThriftAPI.get_thrift_services(pre_type))

        # Controller to Switch Info
        self.switch_info = SwitchInfo()
        self.switch_info.load_json_config(standard_client, json_path)

        self.client = standard_client
        self.mc_client = mc_client
        self.pre_type = pre_type

        # TODO: have a look at this
        self.table_entries_match_to_handle = self.create_match_to_handle_dict()
        self.load_table_entries_match_to_handle()
        #self.table_multiple_names = self.load_table_to_all_names()

    def create_match_to_handle_dict(self):

        d = {}
        for table_name in self.get_tables():
            d[table_name] = {}
        return d

    def shell(self, line):
        "Run a shell command"
        output = os.popen(line).read()
        print(output)

    def get_res(self, type_name, name, res_type):
        key = res_type, name
        if key not in self.switch_info.suffix_lookup_map:
            raise UIn_ResourceError(type_name, name)
        return self.switch_info.suffix_lookup_map[key]

    def parse_runtime_data(self, action, action_params):
        if len(action_params) != action.num_params():
            raise UIn_Error(
                "Action {} needs {} parameters".format(action.name, action.num_params())
            )

        return parse_runtime_data(action, action_params)

    @handle_bad_input
    def show_tables(self):
        "List tables defined in the P4 program: show_tables"
        for table_name in sorted(self.switch_info.tables):
            print(self.switch_info.TABLES[table_name].table_str())

    @handle_bad_input
    def show_actions(self):
        "List actions defined in the P4 program: show_actions"
        for action_name in sorted(self.switch_info.actions):
            print(self.switch_info.actions[action_name].action_str())

    @handle_bad_input
    def table_show_actions(self, table_name):
        "List one table's actions as per the P4 program: table_show_actions <table_name>"

        table = self.get_res("table", table_name, ResType.table)
        for action_name in sorted(table.actions):
            print(self.switch_info.actions[action_name].action_str())

    @handle_bad_input
    def table_info(self, table_name):
        "Show info about a table: table_info <table_name>"
        table = self.get_res("table", table_name, ResType.table)
        print(table.table_str())
        print("*" * 80)
        for action_name in sorted(table.actions):
            print(self.switch_info.actions[action_name].action_str())

    # for debugging
    def print_set_default(self, table_name, action_name, runtime_data):
        print("Setting default action of", table_name)
        print("{0:20} {1}".format("action:", action_name))
        print("{0:20} {1}".format(
            "runtime data:",
            "\t".join(printable_byte_str(d) for d in runtime_data)
        ))

    @handle_bad_input
    def table_set_default(self, table_name, action_name, action_params):
        "Set default action for a match table: table_set_default <table name> <action name> <action parameters>"

        table = self.get_res("table", table_name, ResType.table)
        action = table.get_action(action_name, self.switch_info.suffix_lookup_map)
        if action is None:
            raise UIn_Error(
                "Table {} has no action {}".format(table_name, action_name)
            )

        runtime_data = self.parse_runtime_data(action, action_params)

        self.print_set_default(table_name, action_name, runtime_data)

        self.client.bm_mt_set_default_action(0, table.name, action.name, runtime_data)

    @handle_bad_input
    def table_reset_default(self, table_name):
        "Reset default entry for a match table: table_reset_default <table name>"

        table = self.get_res("table", table_name, ResType.table)
        self.client.bm_mt_reset_default_entry(0, table.name)

    # for debugging
    def print_table_add(self, match_key, action_name, runtime_data):
        print("{0:20} {1}".format(
            "match key:",
            "\t".join(d.to_str() for d in match_key)
        ))
        print("{0:20} {1}".format("action:", action_name))
        print("{0:20} {1}".format(
            "runtime data:",
            "\t".join(printable_byte_str(d) for d in runtime_data)
        ))

    @handle_bad_input
    def table_num_entries(self, table_name):
        "Return the number of entries in a match table (direct or indirect): table_num_entries <table name>"

        table = self.get_res("table", table_name, ResType.table)
        return self.client.bm_mt_get_num_entries(0, table.name)

    @handle_bad_input
    def table_clear(self, table_name):
        "Clear all entries in a match table (direct or indirect), but not the default entry: table_clear <table name>"

        table = self.get_res("table", table_name, ResType.table)
        self.client.bm_mt_clear_entries(0, table.name, False)

    def load_table_to_all_names(self):

        d = {}
        for table_name in self.get_tables():
            #check if short name exists
            short_table_name = table_name.split(".")[-1]
            key = ResType.table, short_table_name
            if key in self.switch_info.suffix_lookup_map:
                d[table_name] = [table_name, short_table_name]

            else:
                d[table_name] = [table_name]

        return d

    @handle_bad_input
    def table_add(self, table_name, action_name, match_keys, action_params=[], prio=None):
        "Add entry to a match table: table_add <table name> <action name> <match fields> => <action parameters> [priority]"

        #print table_name, action_name, match_keys, action_params
        #import ipdb; ipdb.set_trace()

        table = self.get_res("table", table_name, ResType.table)
        action = table.get_action(action_name, self.switch_info.suffix_lookup_map)
        if action is None:
            raise UIn_Error(
                "Table {} has no action {}".format(table_name, action_name)
            )

        if table.match_type in {MatchType.TERNARY, MatchType.RANGE}:
            try:
                priority = int(prio)
            except:
                raise UIn_Error(
                    "Table is ternary, but could not extract a valid priority from args"
                )
        else:
            priority = 0

        if len(match_keys) != table.num_key_fields():
            raise UIn_Error(
                "Table {} needs {} key fields".format(table_name, table.num_key_fields())
            )

        runtime_data = self.parse_runtime_data(action, action_params)
        match_keys = parse_match_key(table, match_keys)

        print("Adding entry to", MatchType.to_str(table.match_type), "match table", table_name)

        # disable, maybe a verbose CLI option?
        self.print_table_add(match_keys, action_name, runtime_data)

        entry_handle = self.client.bm_mt_add_entry(
            0, table.name, match_keys, action.name, runtime_data,
            BmAddEntryOptions(priority=priority)
        )

        #save handle
        #for sub_table_name in self.table_multiple_names[table.name]:
        try:
            entry_handle = int(entry_handle)
            self.table_entries_match_to_handle[table.name] = {str(match_keys) : entry_handle}
        except:
            print("Could not add entry with handle {}".format(entry_handle))
            return entry_handle

        print("Entry has been added with handle", entry_handle)
        print()
        return entry_handle

    @handle_bad_input
    def table_set_timeout(self, table_name, entry_handle, timeout_ms):
        "Set a timeout in ms for a given entry; the table has to support timeouts: table_set_timeout <table_name> <entry handle> <timeout (ms)>"

        table = self.get_res("table", table_name, ResType.table)
        if not table.support_timeout:
            raise UIn_Error(
                "Table {} does not support entry timeouts".format(table_name))

        try:
            entry_handle = int(entry_handle)
        except:
            raise UIn_Error("Bad format for entry handle")

        try:
            timeout_ms = int(timeout_ms)
        except:
            raise UIn_Error("Bad format for timeout")

        print("Setting a", timeout_ms, "ms timeout for entry", entry_handle)

        self.client.bm_mt_set_entry_ttl(0, table.name, entry_handle, timeout_ms)

    def get_handle_from_match(self, table_name, match_keys, pop=False):

        table = self.get_res("table", table_name, ResType.table)
        match_keys = list(map(str, match_keys))
        key = tuple(parse_match_key(table, match_keys))

        entry_handle = self.table_entries_match_to_handle[table.name].get(key, None)
        if entry_handle is not None and pop:
            del self.table_entries_match_to_handle[table.name][key]

        return entry_handle

    @handle_bad_input
    def table_modify(self, table_name, action_name, entry_handle, action_parameters = []):
        "Add entry to a match table: table_modify <table name> <action name> <entry handle> [action parameters]"

        table = self.get_res("table", table_name, ResType.table)
        action = table.get_action(action_name, self.switch_info.suffix_lookup_map)
        if action is None:
            raise UIn_Error(
                "Table {} has no action {}".format(table_name, action_name)
            )

        try:
            entry_handle = int(entry_handle)
        except:
            raise UIn_Error("Bad format for entry handle")

        action_params = action_parameters
        runtime_data = self.parse_runtime_data(action, action_params)

        print("Modifying entry", entry_handle, "for", MatchType.to_str(table.match_type), "match table", table_name)

        #does not return anything
        self.client.bm_mt_modify_entry(
            0, table.name, entry_handle, action.name, runtime_data
        )

        return entry_handle

    def table_modify_match(self, table_name, action_name, match_keys, action_parameters = []):

        entry_handle = self.get_handle_from_match(table_name, match_keys)
        if entry_handle is not None:
            self.table_modify(table_name, action_name, entry_handle, action_parameters)
        else:
            raise UIn_Error(
                "Table {} has no match {}".format(table_name, match_keys)
            )
        return entry_handle

    @handle_bad_input
    def table_delete(self, table_name, entry_handle, quiet=False):
        "Delete entry from a match table: table_delete <table name> <entry handle>"

        #TODO: delete handle

        table = self.get_res("table", table_name, ResType.table)
        try:
            entry_handle = int(entry_handle)
        except:
            raise UIn_Error("Bad format for entry handle " + str(entry_handle))

        if not quiet:
            print("Deleting entry", entry_handle, "from", table_name)

        self.client.bm_mt_delete_entry(0, table.name, entry_handle)

    def table_delete_match(self, table_name, match_keys):

        entry_handle = self.get_handle_from_match(table_name, match_keys, pop=True)
        print("trying to delete entry with handle ", entry_handle)
        if entry_handle is not None:
            self.table_delete(table_name, entry_handle)
        else:
            raise UIn_Error(
                "Table {} has no match {}".format(table_name, match_keys)
            )

    def check_indirect(self, table):
        if table.type_ not in {TableType.indirect, TableType.indirect_ws}:
            raise UIn_Error("Cannot run this command on non-indirect table")

    def check_indirect_ws(self, table):
        if table.type_ != TableType.indirect_ws:
            raise UIn_Error(
                "Cannot run this command on non-indirect table,"\
                " or on indirect table with no selector")

    def check_act_prof_ws(self, act_prof):
        if not act_prof.with_selection:
            raise UIn_Error(
                "Cannot run this command on an action profile without selector")

    @handle_bad_input
    def act_prof_create_member(self, act_prof_name, action_name, action_params):
        "Add a member to an action profile: act_prof_create_member <action profile name> <action_name> [action parameters]"

        act_prof = self.get_res("action profile", act_prof_name,
                                ResType.action_prof)

        action = act_prof.get_action(action_name, self.switch_info.suffix_lookup_map)
        if action is None:
            raise UIn_Error("Action profile '{}' has no action '{}'".format(
                act_prof_name, action_name))


        runtime_data = self.parse_runtime_data(action, action_params)
        mbr_handle = self.client.bm_mt_act_prof_add_member(
            0, act_prof.name, action.name, runtime_data)
        print("Member has been created with handle", mbr_handle)

        return mbr_handle

    @handle_bad_input
    def act_prof_delete_member(self, act_prof_name, mbr_handle):
        "Delete a member in an action profile: act_prof_delete_member <action profile name> <member handle>"


        act_prof = self.get_res("action profile", act_prof_name,
                                ResType.action_prof)
        try:
            mbr_handle = int(mbr_handle)
        except:
            raise UIn_Error("Bad format for member handle")

        self.client.bm_mt_act_prof_delete_member(0, act_prof.name, mbr_handle)

    @handle_bad_input
    def act_prof_modify_member(self, act_prof_name, action_name, mbr_handle, action_params):
        "Modify member in an action profile: act_prof_modify_member <action profile name> <action_name> <member_handle> [action parameters]"

        act_prof = self.get_res("action profile", act_prof_name,
                                ResType.action_prof)

        action = act_prof.get_action(action_name, self.switch_info.suffix_lookup_map)
        if action is None:
            raise UIn_Error("Action profile '{}' has no action '{}'".format(
                act_prof_name, action_name))

        try:
            mbr_handle = int(mbr_handle)
        except:
            raise UIn_Error("Bad format for member handle")

        runtime_data = self.parse_runtime_data(action, action_params)
        self.client.bm_mt_act_prof_modify_member(
            0, act_prof.name, mbr_handle, action.name, runtime_data)

    @handle_bad_input
    def act_prof_create_group(self, act_prof_name):
        "Add a group to an action pofile: act_prof_create_group <action profile name>"

        act_prof = self.get_res("action profile", act_prof_name,
                                ResType.action_prof)

        self.check_act_prof_ws(act_prof)
        grp_handle = self.client.bm_mt_act_prof_create_group(0, act_prof.name)
        print("Group has been created with handle", grp_handle)


    @handle_bad_input
    def act_prof_delete_group(self, act_prof_name, grp_handle):
        "Delete a group from an action profile: act_prof_delete_group <action profile name> <group handle>"

        act_prof = self.get_res("action profile", act_prof_name,
                                ResType.action_prof)
        self.check_act_prof_ws(act_prof)

        try:
            grp_handle = int(grp_handle)
        except:
            raise UIn_Error("Bad format for group handle")

        self.client.bm_mt_act_prof_delete_group(0, act_prof.name, grp_handle)

    @handle_bad_input
    def act_prof_add_member_to_group(self, act_prof_name, mbr_handle, grp_handle):
        "Add member to group in an action profile: act_prof_add_member_to_group <action profile name> <member handle> <group handle>"

        act_prof = self.get_res("action profile", act_prof_name,
                                ResType.action_prof)

        self.check_act_prof_ws(act_prof)

        try:
            mbr_handle = int(mbr_handle)
        except:
            raise UIn_Error("Bad format for member handle")

        try:
            grp_handle = int(grp_handle)
        except:
            raise UIn_Error("Bad format for group handle")

        self.client.bm_mt_act_prof_add_member_to_group(
            0, act_prof.name, mbr_handle, grp_handle)

    @handle_bad_input
    def act_prof_remove_member_from_group(self, act_prof_name, mbr_handle, grp_handle):
        "Remove member from group in action profile: act_prof_remove_member_from_group <action profile name> <member handle> <group handle>"

        act_prof = self.get_res("action profile", act_prof_name,
                                ResType.action_prof)

        self.check_act_prof_ws(act_prof)

        try:
            mbr_handle = int(mbr_handle)
        except:
            raise UIn_Error("Bad format for member handle")

        try:
            grp_handle = int(grp_handle)
        except:
            raise UIn_Error("Bad format for group handle")

        self.client.bm_mt_act_prof_remove_member_from_group(
            0, act_prof.name, mbr_handle, grp_handle)

    def check_has_pre(self):
        if self.pre_type == PreType.none:
            raise UIn_Error(
                "Cannot execute this command without packet replication engine"
            )

    def get_mgrp(self, s):
        try:
            return int(s)
        except:
            raise UIn_Error("Bad format for multicast group id")

    @handle_bad_input_mc
    def mc_mgrp_create(self, mgrp):
        "Create multicast group: mc_mgrp_create <group id>"

        mgrp = self.get_mgrp(mgrp)
        print("Creating multicast group", mgrp)
        mgrp_hdl = self.mc_client.bm_mc_mgrp_create(0, mgrp)
        assert(mgrp == mgrp_hdl)

        return mgrp_hdl

    @handle_bad_input_mc
    def mc_mgrp_destroy(self, mgrp):
        "Destroy multicast group: mc_mgrp_destroy <group id>"

        mgrp = self.get_mgrp(mgrp)
        print("Destroying multicast group", mgrp)
        self.mc_client.bm_mc_mgrp_destroy(0, mgrp)

    def ports_to_port_map_str(self, ports, description="port"):
        last_port_num = 0
        port_map_str = ""
        ports_int = []
        for port_num_str in ports:
            try:
                port_num = int(port_num_str)
            except:
                raise UIn_Error("'{}' is not a valid {} number".format(port_num_str, description))
            if port_num < 0:
                raise UIn_Error("'{}' is not a valid {} number".format(port_num_str, description))
            ports_int.append(port_num)
        ports_int.sort()
        for port_num in ports_int:
            if port_num == (last_port_num - 1):
                raise UIn_Error("Found duplicate {} number '{}'".format(description, port_num))
            port_map_str += "0" * (port_num - last_port_num) + "1"
            last_port_num = port_num + 1
        return port_map_str[::-1]

    @handle_bad_input_mc
    def mc_node_create(self, rid, ports, lags=[]):
        "Create multicast node: mc_node_create <rid> <space-separated port list> [ | <space-separated lag list> ]"
        try:
            rid = int(rid)
        except:
            raise UIn_Error("Bad format for rid")
        port_map_str = self.ports_to_port_map_str(ports)
        lag_map_str = self.ports_to_port_map_str(lags, description="lag")
        if self.pre_type == PreType.SimplePre:
            print("Creating node with rid", rid, "and with port map", port_map_str)
            l1_hdl = self.mc_client.bm_mc_node_create(0, rid, port_map_str)
        else:
            print("Creating node with rid", rid, ", port map", port_map_str, "and lag map", lag_map_str)
            l1_hdl = self.mc_client.bm_mc_node_create(0, rid, port_map_str, lag_map_str)
        print("node was created with handle", l1_hdl)

        return l1_hdl

    def get_node_handle(self, s):
        try:
            return int(s)
        except:
            raise UIn_Error("Bad format for node handle")

    @handle_bad_input_mc
    def mc_node_update(self, l1_hdl, ports, lags=[]):
        "Update multicast node: mc_node_update <node handle> <space-separated port list> [ | <space-separated lag list> ]"

        l1_hdl = self.get_node_handle(l1_hdl)
        port_map_str = self.ports_to_port_map_str(ports)
        lag_map_str = self.ports_to_port_map_str(lags, description="lag")
        if self.pre_type == PreType.SimplePre:
            print("Updating node", l1_hdl, "with port map", port_map_str)
            self.mc_client.bm_mc_node_update(0, l1_hdl, port_map_str)
        else:
            print("Updating node", l1_hdl, "with port map", port_map_str, "and lag map", lag_map_str)
            self.mc_client.bm_mc_node_update(0, l1_hdl, port_map_str, lag_map_str)

    @handle_bad_input_mc
    def mc_node_associate(self, mgrp, l1_hdl):
        "Associate node to multicast group: mc_node_associate <group handle> <node handle>"

        mgrp = self.get_mgrp(mgrp)
        l1_hdl = self.get_node_handle(l1_hdl)
        print("Associating node", l1_hdl, "to multicast group", mgrp)
        self.mc_client.bm_mc_node_associate(0, mgrp, l1_hdl)

    @handle_bad_input_mc
    def mc_node_dissociate(self, mgrp, l1_hdl):
        "Dissociate node from multicast group: mc_node_associate <group handle> <node handle>"

        mgrp = self.get_mgrp(mgrp)
        l1_hdl = self.get_node_handle(l1_hdl)
        print("Dissociating node", l1_hdl, "from multicast group", mgrp)
        self.mc_client.bm_mc_node_dissociate(0, mgrp, l1_hdl)

    @handle_bad_input_mc
    def mc_node_destroy(self, l1_hdl):
        "Destroy multicast node: mc_node_destroy <node handle>"

        l1_hdl = self.get_node_handle(l1_hdl)
        print("Destroying node", l1_hdl)
        self.mc_client.bm_mc_node_destroy(0, l1_hdl)

    @handle_bad_input_mc
    def mc_set_lag_membership(self, lag_index, ports):
        "Set lag membership of port list: mc_set_lag_membership <lag index> <space-separated port list>"
        self.check_has_pre()
        if self.pre_type != PreType.SimplePreLAG:
            raise UIn_Error(
                "Cannot execute this command with this type of PRE,"\
                " SimplePreLAG is required"
            )

        try:
            lag_index = int(lag_index)
        except:
            raise UIn_Error("Bad format for lag index")
        port_map_str = self.ports_to_port_map_str(ports, description="lag")
        print("Setting lag membership:", lag_index, "<-", port_map_str)
        self.mc_client.bm_mc_set_lag_membership(0, lag_index, port_map_str)

    @handle_bad_input_mc
    def mc_dump(self):
        "Dump entries in multicast engine"
        self.check_has_pre()
        json_dump = self.mc_client.bm_mc_get_entries(0)
        try:
            mc_json = json.loads(json_dump)
        except:
            print("Exception when retrieving MC entries")
            return

        l1_handles = {}
        for h in mc_json["l1_handles"]:
            l1_handles[h["handle"]] = (h["rid"], h["l2_handle"])
        l2_handles = {}
        for h in mc_json["l2_handles"]:
            l2_handles[h["handle"]] = (h["ports"], h["lags"])

        print("==========")
        print("MC ENTRIES")
        for mgrp in mc_json["mgrps"]:
            print("**********")
            mgid = mgrp["id"]
            print("mgrp({})".format(mgid))
            for L1h in mgrp["l1_handles"]:
                rid, L2h = l1_handles[L1h]
                print("  -> (L1h={}, rid={})".format(L1h, rid), end=' ')
                ports, lags = l2_handles[L2h]
                print("-> (ports=[{}], lags=[{}])".format(
                    ", ".join([str(p) for p in ports]),
                    ", ".join([str(l) for l in lags])))

        print("==========")
        print("LAGS")
        if "lags" in mc_json:
            for lag in mc_json["lags"]:
                print("lag({})".format(lag["id"]), end=' ')
                print("-> ports=[{}]".format(", ".join([str(p) for p in ports])))
        else:
            print("None for this PRE type")
        print("==========")

    @handle_bad_input
    def load_new_config_file(self, filename):
        "Load new json config: load_new_config_file <path to .json file>"

        if not os.path.isfile(filename):
            raise UIn_Error("Not a valid filename")
        print("Loading new Json config")
        with open(filename, 'r') as f:
            json_str = f.read()
            try:
                json.loads(json_str)
            except:
                raise UIn_Error("Not a valid JSON file")
            self.client.bm_load_new_config(json_str)
            self.load_json_str(json_str)

    @handle_bad_input
    def swap_configs(self):
        "Swap the 2 existing configs, need to have called load_new_config_file before"
        print("Swapping configs")
        self.client.bm_swap_configs()

    @handle_bad_input
    def meter_array_set_rates(self, meter_name, rates):
        """
        Configure rates for an entire meter array: meter_array_set_rates <name> [(<rate_1>,<burst_1>), (<rate_2>,<burst_2>)] ...
        Rate uses units/microsecond and burst uses units where units is bytes or packets.
        """

        meter = self.get_res("meter", meter_name, ResType.meter_array)
        if len(rates) != meter.rate_count:
            raise UIn_Error(
                "Invalid number of rates, expected {} but got {}".format(meter.rate_count, len(rates))
            )
        new_rates = []
        for rate, burst in rates:
            try:
                r = float(rate)
                b = int(burst)
                new_rates.append(BmMeterRateConfig(r, b))
            except:
                raise UIn_Error("Error while parsing rates")
        self.client.bm_meter_array_set_rates(0, meter.name, new_rates)

    @handle_bad_input
    def meter_set_rates(self, meter_name, index, rates):
        """
        Configure rates for a meter: meter_set_rates <name> <index> [(<rate_1>,<burst_1>), (<rate_2>,<burst_2>)] ...
        Rate uses units/microsecond and burst uses units where units is bytes or packets.
        """

        meter = self.get_res("meter", meter_name, ResType.meter_array)
        try:
            index = int(index)
        except:
            raise UIn_Error("Bad format for index")
        if len(rates) != meter.rate_count:
            raise UIn_Error(
                "Invalid number of rates, expected {} but got {}".format(meter.rate_count, len(rates))
            )
        new_rates = []
        for rate, burst in rates:
            try:
                r = float(rate)
                b = int(burst)
                new_rates.append(BmMeterRateConfig(r, b))
            except:
                raise UIn_Error("Error while parsing rates")
        if meter.is_direct:
            table_name = meter.binding
            self.client.bm_mt_set_meter_rates(0, table_name, index, new_rates)
        else:
            self.client.bm_meter_set_rates(0, meter.name, index, new_rates)

    @handle_bad_input
    def meter_get_rates(self, meter_name, index):
        """
        Retrieve rates for a meter: meter_get_rates <name> <index>.
        Rate uses units/microsecond and burst uses units where units is bytes or packets.
        """

        meter = self.get_res("meter", meter_name, ResType.meter_array)
        try:
            index = int(index)
        except:
            raise UIn_Error("Bad format for index")
        # meter.rate_count
        if meter.is_direct:
            table_name = meter.binding
            rates = self.client.bm_mt_get_meter_rates(0, table_name, index)
        else:
            rates = self.client.bm_meter_get_rates(0, meter.name, index)
        if len(rates) != meter.rate_count:
            print("WARNING: expected", meter.rate_count, "rates", end=' ')
            print("but only received", len(rates))

        values = []
        for idx, rate in enumerate(rates):
            print("{}: info rate = {}, burst size = {}".format(
                idx, rate.units_per_micros, rate.burst_size))
            values.append(rate.units_per_micros)
            values.append(rate.burst_size)

        return values

    @handle_bad_input
    def counter_read(self, counter_name, index):
        "Read counter value: counter_read <name> <entry handle>"

        counter = self.get_res("counter", counter_name, ResType.counter_array)
        try:
            index = int(index)
        except:
            raise UIn_Error("Bad format for index")
        if counter.is_direct:
            table_name = counter.binding
            print("this is the direct counter for table", table_name)
            # index = index & 0xffffffff
            value = self.client.bm_mt_read_counter(0, table_name, index)
        else:
            value = self.client.bm_counter_read(0, counter.name, index)

        print("{}[{}]= ({} bytes, {} packets)".format(counter_name, index, value.bytes, value.packets))
        return value

    @handle_bad_input
    def counter_write(self, counter_name, index, pkts, byts):
        "Write counter value: counter_write <name> <index> <packets> <bytes>"

        counter = self.get_res("counter", counter_name, ResType.counter_array)
        try:
            index = int(index)
        except:
            raise UIn_Error("Bad format for index")
        try:
            pkts = int(pkts)
        except:
            raise UIn_Error("Bad format for packets")
        try:
            byts = int(byts)
        except:
            raise UIn_Error("Bad format for bytes")
        if counter.is_direct:
            table_name = counter.binding
            print("writing to direct counter for table", table_name)
            self.client.bm_mt_write_counter(0, table_name, index, BmCounterValue(bytes=byts, packets=pkts))
        else:
            self.client.bm_counter_write(0, counter_name, index, BmCounterValue(bytes=byts, packets=pkts))
        print("{}[{}] has been updated".format(counter_name, index))

    @handle_bad_input
    def counter_reset(self, counter_name):
        "Reset counter: counter_reset <name>"

        counter = self.get_res("counter", counter_name, ResType.counter_array)
        if counter.is_direct:
            table_name = counter.binding
            print("this is the direct counter for table", table_name)
            self.client.bm_mt_reset_counters(0, table_name)
        else:
            self.client.bm_counter_reset_all(0, counter.name)

    @handle_bad_input
    def register_read(self, register_name, index=None, show=False):
        "Read register value: register_read <name> [index]"

        register = self.get_res("register", register_name,
                                ResType.register_array)
        if index or index == 0:
            try:
                index = int(index)
            except:
                raise UIn_Error("Bad format for index")
            value = self.client.bm_register_read(0, register.name, index)
            if show:
                print("{}[{}]=".format(register_name, index), value)
            return value
        else:
            entries = self.client.bm_register_read_all(0, register.name)
            if show:
                sys.stderr.write("register index omitted, reading entire array\n")
                print("{}=".format(register_name), ", ".join([str(e) for e in entries]))
            return entries

    @handle_bad_input
    def register_write(self, register_name, index, value):
        "Write register value: register_write <name> <index>|[start_index, end_index] <value>"

        register = self.get_res("register", register_name,
                                ResType.register_array)


        try:
            if isinstance(index, list):
                index = list(map(int, index))
            else:
                index = int(index)
        except:
            raise UIn_Error("Bad format for index")

        try:
            value = int(value)
        except:
            raise UIn_Error("Bad format for value, must be an integer")

        if isinstance(index, list):
            self.client.bm_register_write_range(0, register.name, index[0], index[1], value)
        else:
            self.client.bm_register_write(0, register.name, index, value)

    @handle_bad_input
    def register_reset(self, register_name):
        "Reset all the cells in the register array to 0: register_reset <name>"

        register = self.get_res("register", register_name,
                                ResType.register_array)
        self.client.bm_register_reset(0, register.name)

    def dump_action_and_data(self, action_name, action_data):
        print("Action entry: {} - {}".format(
            action_name, ", ".join([hexstr(a) for a in action_data])))

    def dump_action_entry(self, a_entry):
        if a_entry.action_type == BmActionEntryType.NONE:
            print("EMPTY")
        elif a_entry.action_type == BmActionEntryType.ACTION_DATA:
            self.dump_action_and_data(a_entry.action_name, a_entry.action_data)
        elif a_entry.action_type == BmActionEntryType.MBR_HANDLE:
            print("Index: member({})".format(a_entry.mbr_handle))
        elif a_entry.action_type == BmActionEntryType.GRP_HANDLE:
            print("Index: group({})".format(a_entry.grp_handle))

    def dump_one_member(self, member):
        print("Dumping member {}".format(member.mbr_handle))
        self.dump_action_and_data(member.action_name, member.action_data)

    def dump_members(self, members):
        for m in members:
            print("**********")
            self.dump_one_member(m)

    def dump_one_group(self, group):
        print("Dumping group {}".format(group.grp_handle))
        print("Members: [{}]".format(", ".join(
            [str(h) for h in group.mbr_handles])))

    def dump_groups(self, groups):
        for g in groups:
            print("**********")
            self.dump_one_group(g)

    def dump_one_entry(self, table, entry):
        if table.key:
            out_name_w = max(20, max([len(t[0]) for t in table.key]))

        def dump_exact(p):
             return hexstr(p.exact.key)

        def dump_lpm(p):
            return "{}/{}".format(hexstr(p.lpm.key), p.lpm.prefix_length)

        def dump_ternary(p):
            return "{} &&& {}".format(hexstr(p.ternary.key),
                                      hexstr(p.ternary.mask))

        def dump_range(p):
            return "{} -> {}".format(hexstr(p.range.start),
                                     hexstr(p.range.end_))

        def dump_valid(p):
            return "01" if p.valid.key else "00"
        pdumpers = {"exact": dump_exact, "lpm": dump_lpm,
                    "ternary": dump_ternary, "valid": dump_valid,
                    "range": dump_range}

        print("Dumping entry {}".format(hex(entry.entry_handle)))
        print("Match key:")
        for p, k in zip(entry.match_key, table.key):
            assert(k[1] == p.type)
            pdumper = pdumpers[MatchType.to_str(p.type)]
            print("* {0:{w}}: {1:10}{2}".format(
                k[0], MatchType.to_str(p.type).upper(),
                pdumper(p), w=out_name_w))
        if entry.options.priority >= 0:
            print("Priority: {}".format(entry.options.priority))
        self.dump_action_entry(entry.action_entry)
        if entry.life is not None:
            print("Life: {}ms since hit, timeout is {}ms".format(
                entry.life.time_since_hit_ms, entry.life.timeout_ms))

    @handle_bad_input
    def table_dump_entry(self, table_name, entry_handle):
        "Display some information about a table entry: table_dump_entry <table name> <entry handle>"

        table = self.get_res("table", table_name, ResType.table)

        try:
            entry_handle = int(entry_handle)
        except:
            raise UIn_Error("Bad format for entry handle")

        entry = self.client.bm_mt_get_entry(0, table.name, entry_handle)
        self.dump_one_entry(table, entry)

    @handle_bad_input
    def act_prof_dump_member(self, act_prof_name, mbr_handle):
        "Display some information about a member: act_prof_dump_member <action profile name> <member handle>"

        act_prof = self.get_res("action profile", act_prof_name,
                                ResType.action_prof)

        try:
            mbr_handle = int(mbr_handle)
        except:
            raise UIn_Error("Bad format for member handle")

        member = self.client.bm_mt_act_prof_get_member(
            0, act_prof.name, mbr_handle)
        self.dump_one_member(member)

    @handle_bad_input
    def act_prof_dump_group(self, act_prof_name, grp_handle):
        "Display some information about a group: table_dump_group <action profile name> <group handle>"

        act_prof = self.get_res("action profile", act_prof_name,
                                ResType.action_prof)
        try:
            grp_handle = int(grp_handle)
        except:
            raise UIn_Error("Bad format for group handle")

        group = self.client.bm_mt_act_prof_get_group(
            0, act_prof.name, grp_handle)
        self.dump_one_group(group)

    def _dump_act_prof(self, act_prof):
        act_prof_name = act_prof.name
        members = self.client.bm_mt_act_prof_get_members(0, act_prof.name)
        print("==========")
        print("MEMBERS")
        self.dump_members(members)
        if act_prof.with_selection:
            groups = self.client.bm_mt_act_prof_get_groups(0, act_prof.name)
            print("==========")
            print("GROUPS")
            self.dump_groups(groups)

    @handle_bad_input
    def act_prof_dump(self, act_prof_name):
        "Display entries in an action profile: act_prof_dump <action profile name>"

        act_prof = self.get_res("action profile", act_prof_name,
                                ResType.action_prof)
        self._dump_act_prof(act_prof)


    def load_table_entries_match_to_handle(self):

        for table_name, table in list(self.get_tables().items()):
            #remove the entries if any
            self.table_entries_match_to_handle[table_name].clear()
            switch_entries = self.client.bm_mt_get_entries(0, table.name)
            for entry in switch_entries:
                self.table_entries_match_to_handle[table_name] = {str(entry.match_key) : entry.entry_handle}

    @handle_bad_input
    def table_dump(self, table_name):
        "Display entries in a match-table: table_dump <table name>"

        table = self.get_res("table", table_name, ResType.table)
        entries = self.client.bm_mt_get_entries(0, table.name)

        print("==========")
        print("TABLE ENTRIES")

        for e in entries:
            print("**********")
            self.dump_one_entry(table, e)

        if table.type_ == TableType.indirect or\
           table.type_ == TableType.indirect_ws:
            assert(table.action_prof is not None)
            self._dump_act_prof(table.action_prof)

        # default entry
        default_entry = self.client.bm_mt_get_default_entry(0, table.name)
        print("==========")
        print("Dumping default entry")
        self.dump_action_entry(default_entry)

        print("==========")

    @handle_bad_input
    def table_dump_entry_from_key(self, table_name, match_keys, priority):
        "Display some information about a table entry: table_dump_entry_from_key <table name> <match fields> [priority]"

        table = self.get_res("table", table_name, ResType.table)

        if table.match_type in {MatchType.TERNARY, MatchType.RANGE}:
            try:
                priority = int(priority)
            except:
                raise UIn_Error(
                    "Table is ternary, but could not extract a valid priority from args"
                )
        else:
            priority = 0

        if len(match_keys) != table.num_key_fields():
            raise UIn_Error(
                "Table {} needs {} key fields".format(table_name, table.num_key_fields())
            )
        match_key = parse_match_key(table, match_keys)

        entry = self.client.bm_mt_get_entry_from_key(
            0, table.name, match_key, BmAddEntryOptions(priority=priority))
        self.dump_one_entry(table, entry)

    @handle_bad_input
    def show_pvs(self, line):
        "List parser value sets defined in the P4 program: show_pvs"
        self.exactly_n_args(line.split(), 0)
        for pvs_name in sorted(self.switch_info.parse_vsets):
            print(self.switch_info.parse_vsets[pvs_name].parse_vset_str())

    @handle_bad_input
    def pvs_add(self, pvs_name, value):
        """
        Add a value to a parser value set: pvs_add <pvs_name> <value>
        bmv2 will not report an error if the value already exists.
        """
        pvs = self.get_res("parser value set", pvs_name, ResType.parse_vset)

        v = parse_pvs_value(value, pvs.bitwidth)
        self.client.bm_parse_vset_add(0, pvs_name, v)

    @handle_bad_input
    def pvs_remove(self, pvs_name, value):
        """
        Remove a value from a parser value set: pvs_remove <pvs_name> <value>
        bmv2 will not report an error if the value does not exist.
        """
        pvs = self.get_res("parser value set", pvs_name, ResType.parse_vset)

        v = parse_pvs_value(value, pvs.bitwidth)
        self.client.bm_parse_vset_remove(0, pvs_name, v)

    @handle_bad_input
    def pvs_get(self, pvs_name):
        """
        Print all values from a parser value set: pvs_get <pvs_name>
        Values are displayed in no particular order, one per line.
        """
        pvs = self.get_res("parser value set", pvs_name, ResType.parse_vset)

        values = self.client.bm_parse_vset_get(0, pvs_name)
        for v in values:
            print(hexstr(v))
        return values

    @handle_bad_input
    def pvs_clear(self, pvs_name):
        """
        Remove all values from a parser value set: pvs_clear <pvs_name>
        """
        pvs = self.get_res("parser value set", pvs_name, ResType.parse_vset)

        self.client.bm_parse_vset_clear(0, pvs_name)

    @handle_bad_input
    def port_add(self, iface_name, port_num, pcap_path=""):
        "Add a port to the switch (behavior depends on device manager used): port_add <iface_name> <port_num> [pcap_path]"

        try:
            port_num = int(port_num)
        except:
            raise UIn_Error("Bad format for port_num, must be an integer")

        self.client.bm_dev_mgr_add_port(iface_name, port_num, pcap_path)

    @handle_bad_input
    def port_remove(self, port_num):
        "Removes a port from the switch (behavior depends on device manager used): port_remove <port_num>"

        try:
            port_num = int(port_num)
        except:
            raise UIn_Error("Bad format for port_num, must be an integer")
        self.client.bm_dev_mgr_remove_port(port_num)

    @handle_bad_input
    def show_ports(self):
        "Shows the ports connected to the switch: show_ports"
        ports = self.client.bm_dev_mgr_show_ports()
        print("{:^10}{:^20}{:^10}{}".format(
            "port #", "iface name", "status", "extra info"))
        print("=" * 50)
        for port_info in ports:
            status = "UP" if port_info.is_up else "DOWN"
            extra_info = "; ".join(
                [k + "=" + v for k, v in port_info.extra.items()])
            print("{:^10}{:^20}{:^10}{}".format(
                port_info.port_num, port_info.iface_name, status, extra_info))

    @handle_bad_input
    def switch_info(self):
        "Show some basic info about the switch: switch_info"

        info = self.client.bm_mgmt_get_info()
        attributes = [t[2] for t in info.thrift_spec[1:]]
        out_attr_w = 5 + max(len(a) for a in attributes)
        for a in attributes:
            print("{:{w}}: {}".format(a, getattr(info, a), w=out_attr_w))

    @handle_bad_input
    def reset_state(self):
        "Reset all state in the switch (table entries, registers, ...), but P4 config is preserved: reset_state"
        self.client.bm_reset_state()

    @handle_bad_input
    def write_config_to_file(self, filename):
        "Retrieves the JSON config currently used by the switch and dumps it to user-specified file"

        json_cfg = self.client.bm_get_config()
        with open(filename, 'w') as f:
            f.write(json_cfg)

    @handle_bad_input
    def serialize_state(self, filename):
        "Serialize the switch state and dumps it to user-specified file"

        state = self.client.bm_serialize_state()
        with open(filename, 'w') as f:
            f.write(state)

    def set_crc_parameters_common(self, name, polynomial, initial_remainder, final_xor_value, reflect_data, reflect_remainder, crc_width=16):
        conversion_fn = {16: hex_to_i16, 32: hex_to_i32}[crc_width]
        config_type = {16: BmCrc16Config, 32: BmCrc32Config}[crc_width]
        thrift_fn = {16: self.client.bm_set_crc16_custom_parameters,
                     32: self.client.bm_set_crc32_custom_parameters}[crc_width]

        if name not in self.switch_info.custom_crc_calcs or self.switch_info.custom_crc_calcs[name] != crc_width:
            raise UIn_ResourceError("crc{}_custom".format(crc_width), name)
        config_args = [conversion_fn(a) for a in [polynomial, initial_remainder, final_xor_value]]
        config_args += [parse_bool(a) for a in [reflect_data, reflect_remainder]]
        crc_config = config_type(*config_args)
        thrift_fn(0, name, crc_config)

    @handle_bad_input
    def set_crc16_parameters(self, name, polynomial, initial_remainder, final_xor_value, reflect_data, reflect_remainder):
        "Change the parameters for a custom crc16 hash: set_crc16_parameters <name> <polynomial> <initial remainder> <final xor value> <reflect data?> <reflect remainder?>"
        self.set_crc_parameters_common(name, polynomial, initial_remainder, final_xor_value, reflect_data, reflect_remainder, 16)

    @handle_bad_input
    def set_crc32_parameters(self, name, polynomial, initial_remainder, final_xor_value, reflect_data, reflect_remainder):
        "Change the parameters for a custom crc32 hash: set_crc32_parameters <name> <polynomial> <initial remainder> <final xor value> <reflect data?> <reflect remainder?>"
        self.set_crc_parameters_common(name, polynomial, initial_remainder, final_xor_value, reflect_data, reflect_remainder, 32)


    #Global Variable Getters
    def get_tables(self):
        return self.switch_info.tables

    def get_action_profs(self):
        return self.switch_info.action_profs

    def get_actions(self):
        return self.switch_info.actions

    def get_meter_arrays(self):
        return self.switch_info.meter_arrays

    def get_counter_arrays(self):
        return self.switch_info.counter_arrays

    def get_register_arrays(self):
        return self.switch_info.register_arrays

    def get_custom_crc_calcs(self):
        return self.switch_info.custom_crc_calcs

    def get_parse_vsets(self):
        return self.switch_info.parse_vsets

    def get_suffix_lookup_map(self):
        return self.switch_info.suffix_lookup_map
