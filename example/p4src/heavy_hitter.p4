/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>


/*************************************************************************
***********************     METADATA   ***********************************
*************************************************************************/

struct metadata {
    bit<32> output_hash_one;
    bit<32> output_hash_two;
    bit<32> counter_one;
    bit<32> counter_two;

    bit<6> controller_id;
}

#include "include/headers.p4"
#include "include/parsers.p4"
#include "include/checksums.p4"

/* CONSTANTS */

#define BLOOM_FILTER_ENTRIES 4096
#define BLOOM_FILTER_BIT_WIDTH 32
#define PACKET_THRESHOLD 1000

/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/


control ingress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {


    register<bit<BLOOM_FILTER_BIT_WIDTH>>(BLOOM_FILTER_ENTRIES) bloom_filter;

    action drop() {
        mark_to_drop();
    }

    action _update_bloom_filter(){


       //Get register position

       hash(meta.output_hash_one, HashAlgorithm.crc16, (bit<16>)0, {hdr.ipv4.srcAddr,
                                                          hdr.ipv4.dstAddr,
                                                          hdr.tcp.srcPort,
                                                          hdr.tcp.dstPort,
                                                          hdr.ipv4.protocol},
                                                          (bit<32>)BLOOM_FILTER_ENTRIES);

       /*hash(meta.output_hash_two, HashAlgorithm.crc32, (bit<16>)0, {hdr.ipv4.srcAddr,
                                                          hdr.ipv4.dstAddr,
                                                          hdr.tcp.srcPort,
                                                          hdr.tcp.dstPort,
                                                          hdr.ipv4.protocol},
                                                          (bit<32>)BLOOM_FILTER_ENTRIES);*/


        //Read counters
        bloom_filter.read(meta.counter_one, meta.output_hash_one);
        //bloom_filter.read(meta.counter_two, meta.output_hash_two);

        meta.counter_one = meta.counter_one + 1;
        //meta.counter_two = meta.counter_two + 1;

        //write counters

        bloom_filter.write(meta.output_hash_one, meta.counter_one);
        //bloom_filter.write(meta.output_hash_two, meta.counter_two);


    }

    action ipv4_forward(macAddr_t dstAddr, egressSpec_t port) {

        //set the src mac address as the previous dst, this is not correct right?
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;

       //set the destination mac address that we got from the match in the table
        hdr.ethernet.dstAddr = dstAddr;

        //set the output port that we also get from the table
        standard_metadata.egress_spec = port;

        //decrease ttl by 1
        hdr.ipv4.ttl = hdr.ipv4.ttl -1;

    }

    table ipv4_lpm {
        key = {
            hdr.ipv4.dstAddr: lpm;
        }
        actions = {
            ipv4_forward;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = NoAction();
    }

    table update_bloom_filter{

        actions = {
            _update_bloom_filter;
        }
        size = 1;
        default_action = _update_bloom_filter();
    }

    table drop_table{
        actions = {
            drop;
        }
        size =1;
        default_action = drop();
    }


    apply {
        if (hdr.ipv4.isValid()){
            if (hdr.tcp.isValid()){
                update_bloom_filter.apply();
                //only if IPV4 the rule is applied. Therefore other packets will not be forwarded.
                if ( (meta.counter_one > PACKET_THRESHOLD ) ){
                    drop_table.apply();
                    return;
                }
            }
            ipv4_lpm.apply();
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control egress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply {

    }
}


/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

//switch architecture
V1Switch(
ParserImpl(),
verifyChecksum(),
ingress(),
egress(),
computeChecksum(),
deparser()
) main;