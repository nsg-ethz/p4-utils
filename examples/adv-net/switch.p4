/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

#define CONST_MAX_MPLS_STACK 10
#define SIZE 1024
#define FLOW_ID_SIZE 32

const bit<16> TYPE_IPV4 = 0x0800;
const bit<16> TYPE_MPLS = 0x8847;
const bit<16> TYPE_META = 0x2602;

const bit<8> PROTO_UDP = 0x11;

const bit<16> BCAST_GRP = 0x0001;
const bit<16> MCAST_GRP = 0x0002;
const bit<16> NOCAST_GRP = 0x0000;

const bit<8> GOLD_TOS = 8w128;
const bit<8> SILVER_TOS = 8w64;
const bit<8> BRONZE_TOS = 8w32;

const bit<3> GOLD_EXP = 3w3;
const bit<3> SILVER_EXP = 3w2;
const bit<3> BRONZE_EXP = 3w1;

const bit<20> LABEL_OFFSET = 20w16;

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;
typedef bit<20> label_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header mpls_t {
    bit<20> label;
    bit<3>  exp;
    bit<1>  s;
    bit<8>  ttl;
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<6>    dscp;
    bit<2>    ecn;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}

header udp_t {
    bit<16>   srcPort;
    bit<16>   dstPort;
    bit<16>   length;
    bit<16>   checksum;
}

// Since resubmitting and recirculating do not work well with non empty
// metadata fields to preserve, we use an internal header.
header meta_t {
    bit<FLOW_ID_SIZE>  subflow_id;                  // Subflow for the specified destination
}

struct metadata {
    bit<FLOW_ID_SIZE>  subflow_id;                  // Subflow for the specified destination
    bit<FLOW_ID_SIZE>  nhop;                        // Next hop for IPv4 load balancing
    bit<3>             exp;                         // Priority class for MPLS
    bit<1>             to_recirculate_ingress;      // Set to 1 if the packet has to be recirculated (requested by ingress switch)
    bit<1>             to_recirculate_egress;       // Set to 1 if the packet has to be recirculated (requested by egress switch)
}

struct headers {
    ethernet_t                        ethernet;
    meta_t                            meta;
    mpls_t[CONST_MAX_MPLS_STACK]      mpls;
    ipv4_t                            ipv4;
    udp_t                             udp;
}

/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            TYPE_META: parse_meta;
            TYPE_MPLS: parse_mpls;
            default: accept;
        }
    }

    state parse_meta{
        packet.extract(hdr.meta);
        transition parse_ipv4;
    }

    state parse_mpls {
        packet.extract(hdr.mpls.next);
        transition select(hdr.mpls.last.s) {
            0: parse_mpls;
            1: parse_ipv4;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol){
            PROTO_UDP : parse_udp;
            default: accept;
        }
    }

    state parse_udp {
        packet.extract(hdr.udp);
        transition accept;
    }
}


/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {  }
}


/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    // Register which counts the number of packets arrived per each subflow
    // (indexed by subflow_id)
    register<bit<32>>(SIZE) subflow_packets_counter;
    // Register which contains the failure status of subflows:
    // 1 if the subflow is down, 0 else.
    register<bit<1>>(SIZE) subflow_failure_status;
    // Counter which counts the number of packets sent per each flow (indexed by
    // flow_id)
    register<bit<32>>(SIZE) flow_packets_counter;
    // Register which contains the last subflow used to forward packets (indexed
    // by flow_id)
    register<bit<FLOW_ID_SIZE>>(SIZE) last_subflow;
    // Register which contains the last nhop used for IPv4 multipath
    register<bit<FLOW_ID_SIZE>>(1) last_nhop;
    // Register which contains the backup subflows (indexed by subflow_id). Each
    // subflow (normal and backup ones) has a unique subflow_id. By accessing this
    // register at index I, we get the subflow_id of the backup subflow of subflow
    // I. The interesting thing is that I can also be a backup subflow for some
    // other subflow, which allows us to define multiple backup subflows.
    register<bit<FLOW_ID_SIZE>>(SIZE) backup_subflows;

    // Drop action
    action drop() {
        // Drop packet
        mark_to_drop(standard_metadata);
    }

    // L2 forwarding
    action l2_forward_action(egressSpec_t port) {
        // Forward the packet
        meta.to_recirculate_egress = 0;
        meta.to_recirculate_ingress = 0;
        // Set outgoing port
        standard_metadata.egress_spec = port;
    }

    // L2 broadcasting
    action broadcast() {
        // Set broadcast group
        standard_metadata.mcast_grp = BCAST_GRP;
    }

    // L2 multicasting for multicast MAC addresses
    action multicast() {
        // Set multicast group
        standard_metadata.mcast_grp = MCAST_GRP;
    }

    // L2 Forwarding table
    // Longest Prefix Match is used to make easier the configuration of
    // multicast MAC addresses
    table l2_forward {
        key = {
            hdr.ethernet.dstAddr: lpm;
        }
        actions = {
            l2_forward_action;
            broadcast;
            multicast;
            drop;
        }
        size = SIZE;
        default_action = drop;
    }

    // L3 forwarding
    action ipv4_forward_action(macAddr_t dstAddr, macAddr_t srcAddr, egressSpec_t port) {
        // Update source and destination MAC addresses
        hdr.ethernet.srcAddr = srcAddr;
        hdr.ethernet.dstAddr = dstAddr;
        // Forward the packet
        meta.to_recirculate_ingress = 0;
        meta.to_recirculate_egress = 0;
        // Set outgoing port
        standard_metadata.egress_spec = port;
    }

    // IPv3 multipath
    action ipv4_multipath_select(bit<32> n_splits) {
        // Initialize temporary variable
        bit<FLOW_ID_SIZE> nhop_tmp;
        // Read last_nhop
        last_nhop.read(nhop_tmp, 0);
        // Compute current nhop
        nhop_tmp = nhop_tmp + 1;
        // Check if nhop_tmp is equal to n_splits
        if (nhop_tmp >= (bit<FLOW_ID_SIZE>)n_splits) {
            // Reset nhop_tmp to 0
            nhop_tmp = 0;
        }
        // Assign nhop_tmp to nhop metadata field
        meta.nhop = nhop_tmp;
    }

    // Set subflow for the specified destination
    // This action take as input the number of different subflows for a
    // destination (needed for load balancing) and then chooses one at random
    // to forward the packet.
    action mpls_ecmp_select(bit<32> n_splits, bit<32> flow_id) {

        // Declare temporary variables
        bit<1> failure_tmp;
        bit<8> tos_tmp;
        bit<3> exp_tmp;
        bit<FLOW_ID_SIZE> subflow_tmp;
        bit<FLOW_ID_SIZE> backup_subflow_id_tmp;
        bit<32> flow_packets_count;

        // Compute tos field of ipv4 header
        tos_tmp = (((bit<8>)hdr.ipv4.dscp) << 2) | ((bit<8>)hdr.ipv4.ecn);
        // Set MPLS priority
        if (tos_tmp == GOLD_TOS) {
            // Priority 3 to gold flows (highest one)
            exp_tmp = GOLD_EXP;
        }
        else if (tos_tmp == SILVER_TOS) {
            // Priority 2 to silver flows
            exp_tmp = SILVER_EXP;
        }
        else {
            // Priority 1 to bronze flows (lowest one)
            exp_tmp = BRONZE_EXP;
        }
        // Assign prtiority to packet
        meta.exp = exp_tmp;

        // Read current packet count
        flow_packets_counter.read(flow_packets_count, flow_id);
        // Read the last subflow used
        last_subflow.read(subflow_tmp, flow_id);
        // Check if the packet has not been resubmitted
        if (!hdr.meta.isValid()) {
            // Increment subflow_tmp by 1
            subflow_tmp = subflow_tmp + 1;
            // Increment flow packet count by 1
            flow_packets_count = flow_packets_count + 1;
            // Check if subflow_tmp is equal to n_splits
            if (subflow_tmp >= (bit<FLOW_ID_SIZE>)n_splits) {
                // Reset subflow_tmp to 0
                subflow_tmp = 0;
            }
            // Assign subflow to packet
            meta.subflow_id = subflow_tmp + (bit<FLOW_ID_SIZE>)flow_id;
        }
        else {
            // Get last subflow_id from meta header
            meta.subflow_id = hdr.meta.subflow_id;
        }
        // Write the subflow used into the register
        last_subflow.write(flow_id, subflow_tmp);
        // Write updated packet count
        flow_packets_counter.write(flow_id, flow_packets_count);

        // Read subflow failure status
        subflow_failure_status.read(failure_tmp, (bit<32>)meta.subflow_id);
        // Read backup subflow id
        backup_subflows.read(backup_subflow_id_tmp, (bit<32>)meta.subflow_id);
        // Check if the chosen subflow is down
        if (failure_tmp == 1) {
            // The packet has to be recirculated
            meta.to_recirculate_ingress = 1;
            // Update meta.subflow_id with the backup subflow id
            meta.subflow_id = backup_subflow_id_tmp;
        }
        // If the chosen subflow is up
        else {
            // The packet has to be forwarded
            meta.to_recirculate_ingress = 0;
        }
    }

    // L3 forwarding table and L2.5 FEC table
    table ipv4_forward {
        key = {
            hdr.ipv4.dstAddr: lpm;
        }
        actions = {
            ipv4_forward_action;
            mpls_ecmp_select;
            ipv4_multipath_select;
            NoAction;
        }
        size = SIZE;
        default_action = NoAction;
    }

    // IPv4 multipath
    table ipv4_multipath {
        key = {
            meta.nhop: exact;
            standard_metadata.ingress_port: exact;
        }
        actions = {
            ipv4_forward_action;
            NoAction;
        }
        size = SIZE;
        default_action = NoAction;
    }

    // MPLS ingress actions
    action mpls_ingress_1_hop(label_t label_1) {
        // Set TTL decrement variable
        bit<8> decrement = 8w0;
        // Set etherType to MPLS
        hdr.ethernet.etherType = TYPE_MPLS;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_1;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Bottom of the stack
        hdr.mpls[0].s = 1;
    }

    action mpls_ingress_2_hop(label_t label_2, label_t label_1) {
        // Set TTL decrement variable
        bit<8> decrement = 8w1;
        // Set etherType to MPLS
        hdr.ethernet.etherType = TYPE_MPLS;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_1;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Bottom of the stack
        hdr.mpls[0].s = 1;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_2;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
    }

    action mpls_ingress_3_hop(label_t label_3, label_t label_2, label_t label_1) {
        // Set TTL decrement variable
        bit<8> decrement = 8w2;
        // Set etherType to MPLS
        hdr.ethernet.etherType = TYPE_MPLS;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_1;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Bottom of the stack
        hdr.mpls[0].s = 1;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_2;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_3;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
    }

    action mpls_ingress_4_hop(label_t label_4, label_t label_3, label_t label_2, label_t label_1) {
        // Set TTL decrement variable
        bit<8> decrement = 8w3;
        // Set etherType to MPLS
        hdr.ethernet.etherType = TYPE_MPLS;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_1;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Bottom of the stack
        hdr.mpls[0].s = 1;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_2;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_3;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_4;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
    }

    action mpls_ingress_5_hop(label_t label_5, label_t label_4, label_t label_3, label_t label_2, label_t label_1) {
        // Set TTL decrement variable
        bit<8> decrement = 8w4;
        // Set etherType to MPLS
        hdr.ethernet.etherType = TYPE_MPLS;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_1;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Bottom of the stack
        hdr.mpls[0].s = 1;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_2;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_3;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_4;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_5;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
    }

    action mpls_ingress_6_hop(label_t label_6, label_t label_5, label_t label_4, label_t label_3, label_t label_2, label_t label_1) {
        // Set TTL decrement variable
        bit<8> decrement = 8w5;
        // Set etherType to MPLS
        hdr.ethernet.etherType = TYPE_MPLS;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_1;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Bottom of the stack
        hdr.mpls[0].s = 1;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_2;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_3;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_4;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_5;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_6;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
    }

    action mpls_ingress_7_hop(label_t label_7, label_t label_6, label_t label_5, label_t label_4, label_t label_3, label_t label_2, label_t label_1) {
        // Set TTL decrement variable
        bit<8> decrement = 8w6;
        // Set etherType to MPLS
        hdr.ethernet.etherType = TYPE_MPLS;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_1;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Bottom of the stack
        hdr.mpls[0].s = 1;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_2;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_3;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_4;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_5;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_6;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_7;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
    }

    action mpls_ingress_8_hop(label_t label_8, label_t label_7, label_t label_6, label_t label_5, label_t label_4, label_t label_3, label_t label_2, label_t label_1) {
        // Set TTL decrement variable
        bit<8> decrement = 8w7;
        // Set etherType to MPLS
        hdr.ethernet.etherType = TYPE_MPLS;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_1;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Bottom of the stack
        hdr.mpls[0].s = 1;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_2;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_3;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_4;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_5;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_6;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_7;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_8;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
    }

    action mpls_ingress_9_hop(label_t label_9, label_t label_8, label_t label_7, label_t label_6, label_t label_5, label_t label_4, label_t label_3, label_t label_2, label_t label_1) {
        // Set TTL decrement variable
        bit<8> decrement = 8w8;
        // Set etherType to MPLS
        hdr.ethernet.etherType = TYPE_MPLS;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_1;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Bottom of the stack
        hdr.mpls[0].s = 1;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_2;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_3;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_4;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_5;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_6;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_7;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_8;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_9;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
    }

    action mpls_ingress_10_hop(label_t label_10, label_t label_9, label_t label_8, label_t label_7, label_t label_6, label_t label_5, label_t label_4, label_t label_3, label_t label_2, label_t label_1) {
        // Set TTL decrement variable
        bit<8> decrement = 8w9;
        // Set etherType to MPLS
        hdr.ethernet.etherType = TYPE_MPLS;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_1;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Bottom of the stack
        hdr.mpls[0].s = 1;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_2;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_3;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_4;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_5;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_6;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_7;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_8;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Push label on top of the stack
        hdr.mpls.push_front(1);
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_9;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Update decrement
        decrement = decrement - 1;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
        // Set header as valid and configure fields
        hdr.mpls[0].setValid();
        hdr.mpls[0].label = label_10;
        hdr.mpls[0].ttl = hdr.ipv4.ttl + 1 - decrement;
        hdr.mpls[0].exp = meta.exp;
        // Not bottom of the stack
        hdr.mpls[0].s = 0;
    }

    // L2.5 FEC select
    table mpls_fec {
        key = {
            meta.subflow_id: exact;
        }
        actions = {
            mpls_ingress_1_hop;
            mpls_ingress_2_hop;
            mpls_ingress_3_hop;
            mpls_ingress_4_hop;
            mpls_ingress_5_hop;
            mpls_ingress_6_hop;
            mpls_ingress_7_hop;
            mpls_ingress_8_hop;
            mpls_ingress_9_hop;
            mpls_ingress_10_hop;
            NoAction;
        }
        size = SIZE;
        default_action = NoAction;
    }

    // Subflow counter update
    action subflow_count_update() {
        // Compute index of incoming subflow
        bit<32> index = (bit<32>)(hdr.mpls[0].label - LABEL_OFFSET);
        // Initialize temporary variable to store current count
        bit<32> subflow_packets_count_tmp;
        // Read current packet count
        subflow_packets_counter.read(subflow_packets_count_tmp, index);
        // Increment count
        subflow_packets_count_tmp = subflow_packets_count_tmp + 1;
        // Write updated packet count
        subflow_packets_counter.write(index, subflow_packets_count_tmp);
        // Set etherType back to IPv4
        hdr.ethernet.etherType = TYPE_IPV4;
        // Recirculate the packet
        meta.to_recirculate_egress = 1;
        // Pop last (and first since there is only one label) label of the stack
        hdr.mpls.pop_front(1);
    }

    // L2.5 forwarding
    action mpls_forward_action(macAddr_t dstAddr, macAddr_t srcAddr, egressSpec_t port) {
        // Update source and destination MAC addresses
        hdr.ethernet.srcAddr = srcAddr;
        hdr.ethernet.dstAddr = dstAddr;
        // Set outgoing port
        standard_metadata.egress_spec = port;
        // Forward the packet
        meta.to_recirculate_egress = 0;
        meta.to_recirculate_ingress = 0;
        // Pop first label of the stack
        hdr.mpls.pop_front(1);
    }

    // L2.5 forwarding table
    table mpls_forward {
        key = {
            hdr.mpls[0].label: exact;
        }
        actions = {
            mpls_forward_action;
            NoAction;
        }
        default_action = NoAction;
        size = SIZE;
    }

    apply {
        // If it is a pure IP packet
        if(hdr.ipv4.isValid() && !hdr.mpls[0].isValid()) {
            // Forward IP packet only if TTL >= 1
            if (hdr.ipv4.ttl >= 1) {
                // Forward the packet according to the IPv4 destination
                switch(ipv4_forward.apply().action_run) {
                    // If the IP destination is known and if the packet
                    // has to be forwarded via MPLS, select a subflow
                    mpls_ecmp_select: {
                        // If the packet has to be forwarded
                        if (meta.to_recirculate_ingress == 0 && meta.to_recirculate_egress == 0) {
                            // If the subflow ID is known, associate an LSP to the packet
                            if (mpls_fec.apply().hit) {
                                // If this is not the bottom of the stack
                                if (hdr.mpls[0].s == 0) {
                                    // If the MPLS destination is not known
                                    if (mpls_forward.apply().miss) {
                                        // Apply l2_forward
                                        l2_forward.apply();
                                    }
                                }
                                // If it is the bottom of the stack
                                else {
                                    // Increment subflow count
                                    subflow_count_update();
                                }
                            }
                            else {
                                // Apply l2_forward
                                l2_forward.apply();
                            }
                        }
                    }
                    // If we use IPv4 multipath
                    ipv4_multipath_select: {
                        // Apply ipv4_multipath table
                        if (ipv4_multipath.apply().miss) {
                            // Apply l2_forward
                            l2_forward.apply();
                        }
                    }
                    // If the IP destination is not known
                    NoAction: {
                        // Apply l2_forward
                        l2_forward.apply();
                    }
                }
            }
            // If the packet has expired, drop it
            else {
                drop();
            }
        }
        // If it is an MPLS packet
        else if(hdr.mpls[0].isValid()) {
            // Forward MPLS packet only if TTL > 1
            if (hdr.mpls[0].ttl > 1) {
                // Check if MPLS encapsulates IPv4 packet
                if (hdr.ipv4.isValid()) {
                    // Update IPv4 TTL field
                    hdr.ipv4.ttl = hdr.mpls[0].ttl;
                }
                // If this is not the bottom of the stack
                if (hdr.mpls[0].s == 0) {
                    // If the MPLS destination is not known
                    if(mpls_forward.apply().miss) {
                        // Apply l2_forward
                        l2_forward.apply();
                    }
                }
                // If it is the bottom of the stack
                else {
                    // Increment subflow count
                    subflow_count_update();
                }
            }
            // If the packet has expired, drop it
            else {
                drop();
            }
        }
        // If it is an Ethernet packet
        else {
            // Apply l2_forward
            l2_forward.apply();
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {

    // Drop action
    action drop() {
        // Drop packets
        mark_to_drop(standard_metadata);
    }

    apply {
        // If the packet has to be forwarded
        if (meta.to_recirculate_egress == 0 && meta.to_recirculate_ingress == 0) {
            // Check if the meta header is valid
            if (hdr.meta.isValid()) {
                // Set it as invelid
                hdr.meta.setInvalid();
                // Check if it is an MPLS packet
                if (hdr.mpls[0].isValid()) {
                    // Set etherType back to TYPE_MPLS
                    hdr.ethernet.etherType = TYPE_MPLS;
                }
                // If it is not an MPLS packet and it is an IPv4 packet
                else if (hdr.ipv4.isValid()) {
                    // Set etherType back to TYPE_IPV4
                    hdr.ethernet.etherType = TYPE_IPV4;
                }
            }
            // If the packet is multicast
            if (standard_metadata.mcast_grp != NOCAST_GRP) {
                // If the egress port is equal to the ingress port
                if (standard_metadata.egress_port == standard_metadata.ingress_port) {
                    // Drop the packets
                    drop();
                }
            }
        }
        // If the packet has to be recirculated
        else {
            if (meta.to_recirculate_ingress == 1) {
                // Set meta header as valid
                hdr.meta.setValid();
                // Set etherType equal to TYPE_META
                hdr.ethernet.etherType = TYPE_META;
                // Store metadata into the header
                hdr.meta.subflow_id = meta.subflow_id;
            }
            // Set outgoing port to one, but this is not so important
            // because we recirculate the packet afterwards.
            standard_metadata.egress_spec = 1;
            // Recirculate all the metadata fields
            recirculate(0);
        }
    }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
     apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version,
            hdr.ipv4.ihl,
            hdr.ipv4.dscp,
            hdr.ipv4.ecn,
            hdr.ipv4.totalLen,
            hdr.ipv4.identification,
            hdr.ipv4.flags,
            hdr.ipv4.fragOffset,
            hdr.ipv4.ttl,
            hdr.ipv4.protocol,
            hdr.ipv4.srcAddr,
            hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}

/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {

        //parsed headers have to be added again into the packet.
        packet.emit(hdr.ethernet);
        packet.emit(hdr.meta);
        packet.emit(hdr.mpls);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.udp);
    }
}

/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

//switch architecture
V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
