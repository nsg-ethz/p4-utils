/* -*- P4_16 -*- */

/* Code inspired by nsg/p4-learning and AdvNet course*/

#include <core.p4>
#include <v1model.p4>


const bit<16> TYPE_IPV4 = 0x800;
const bit<16> TYPE_ARP = 0x806;

#define REGISTER_LENGTH 32

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
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

header ospf_t {
    bit<8>    version;
    bit<8>    type;
    bit<16>   pktLen;
    bit<32>   rtrID;
    bit<32>   areaID;
    bit<16>   checksum;
    bit<16>   auType;
    bit<32>   authen;
}

header tcp_t{
    bit<16> srcPort;
    bit<16> dstPort;
    bit<32> seqNo;
    bit<32> ackNo;
    bit<4>  dataOffset;
    bit<4>  res;
    bit<1>  cwr;
    bit<1>  ece;
    bit<1>  urg;
    bit<1>  ack;
    bit<1>  psh;
    bit<1>  rst;
    bit<1>  syn;
    bit<1>  fin;
    bit<16> window;
    bit<16> checksum;
    bit<16> urgentPtr;
}

struct metadata {
    bit<14> ecmp_hash;
    bit<14> ecmp_group_id;

}

struct headers {
    ethernet_t   ethernet;
    ipv4_t       ipv4;
    ospf_t       ospf;
    tcp_t        tcp;
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
        transition select(hdr.ethernet.etherType){

            TYPE_IPV4: ipv4;
            default: accept;

        }

    }

    state ipv4 {

        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol){
            89 : parse_ospf;
            6 : parse_tcp;
            default: accept;
        }

    }

    // parse the OSPF header
    state parse_ospf {
        packet.extract(hdr.ospf);
        transition accept;
    }

    // parse the TCP header
    state parse_tcp {
        packet.extract(hdr.tcp);
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

    register<bit<8>>(REGISTER_LENGTH) OSPF_type_register;
    register<bit<16>>(REGISTER_LENGTH) BGP_register_port;
    register<bit<1>>(REGISTER_LENGTH) BGP_register_flag;


    action drop() {
        mark_to_drop(standard_metadata);
    }

    // Create an ECMP group ID for a flow
    action ecmp_forward(bit<16> num_nhops){
        hash(meta.ecmp_hash,
	    HashAlgorithm.crc16,
	    (bit<1>)0,
	    { hdr.ipv4.srcAddr,
	      hdr.ipv4.dstAddr,
          hdr.tcp.srcPort,
          hdr.tcp.dstPort,
          hdr.ipv4.protocol},
	    num_nhops);

    }

    // Forward ARP lookup for OSPF messages
    action arp_forward(egressSpec_t port) {

        //set the output port from the table
        standard_metadata.egress_spec = port;

        //decrease ttl by 1
        hdr.ipv4.ttl = hdr.ipv4.ttl -1;

    }

    // Forward OSPF packets (hello, DD, LSU, LSR, LSAck)
    action ospf_hello_forward(egressSpec_t port) {

        //set the output port from the table
        standard_metadata.egress_spec = port;

        //decrease ttl by 1
        hdr.ipv4.ttl = hdr.ipv4.ttl -1;

    }

    // Forward OSPF packets (hello, DD, LSU, LSR, LSAck)
    action bgp_forward(egressSpec_t port) {

        //set the output port from the table
        standard_metadata.egress_spec = port;

        //decrease ttl by 1
        //hdr.ipv4.ttl = hdr.ipv4.ttl -1;

    }

    // IPv4 forwarding between hosts and switches
    action set_nhop(macAddr_t dstAddr, egressSpec_t port) {

        //set the src mac address as the previous dst
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;

        //set the destination mac address from the table
        hdr.ethernet.dstAddr = dstAddr;

        //set the output port that from the table
        standard_metadata.egress_spec = port;

        //decrease ttl by 1
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    table arp{
        key = {
            standard_metadata.ingress_port: exact;
        }
        actions = {
            arp_forward;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = NoAction();
    }

    table ospf_hello{
        key = {
            standard_metadata.ingress_port: exact;
        }
        actions = {
            ospf_hello_forward;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = NoAction();
    }


    table bgp_update{
        key = {
            standard_metadata.ingress_port: exact;
        }
        actions = {
            bgp_forward;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = NoAction();
    }



    table ecmp_to_nhop {
        key = {
            meta.ecmp_hash: exact;
        }
        actions = {
            drop;
            set_nhop;
        }
        size = 1024;
    }


    table ipv4_lpm {
        key = {
            hdr.ipv4.dstAddr: lpm;
        }
        actions = {
            set_nhop;
            ecmp_forward;
            drop;
            
        }
        size = 1024;
        default_action =  drop;
    }


    apply {

        
        // Forward ARP packets for resolution of address (needed for OSPF)
        if (hdr.ethernet.isValid()){

             if(hdr.ethernet.etherType == TYPE_ARP){

                arp.apply();
             }

            // Only if IPV4 the rule is applied
            if (hdr.ipv4.isValid()){

                //If packet is an OSPF packet, then OSPF hellos must be routed.
                if(hdr.ipv4.protocol == 89){

                    ospf_hello.apply();

                    if (hdr.ospf.isValid()){
                        // check which type of OSPF packets are being sent, register written with value at type index
                        
                        OSPF_type_register.write((bit<32>)hdr.ospf.type, hdr.ospf.type);
                    }

                
                }
                
                
                // Do not use ipv4_lpm on internal BGP packets

                else if (hdr.ipv4.protocol != 89 && hdr.tcp.dstPort != 179){

                    // Apply IPv4 forwarding for non OSPF packets, from host to host
                    // If multipath is possible, per flow ECMP is carried out on TCP packets
                    switch (ipv4_lpm.apply().action_run){

                        ecmp_forward: {
                            ecmp_to_nhop.apply();
                        }

                    }

                }

                // If packet is an BGP packet, then we know BGP uses a TCP port 179.
                if (hdr.tcp.isValid()){
                        
                        BGP_register_port.write((bit<32>)0, hdr.tcp.dstPort);
                        BGP_register_flag.write((bit<32>)0, hdr.tcp.syn);
                        BGP_register_flag.write((bit<32>)1, hdr.tcp.ack);
                        BGP_register_flag.write((bit<32>)2, hdr.tcp.psh);
                        bgp_update.apply();
                }
                    
            }

        }

        
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply {  }
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
              hdr.ipv4.diffserv,
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
        packet.emit(hdr.ipv4);
        packet.emit(hdr.ospf);
        packet.emit(hdr.tcp);

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