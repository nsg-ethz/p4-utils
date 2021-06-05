#!/bin/bash

set -eu  # Exit on error (-e), treat unset variables as errors (-u).

generate_qos_setting () {
    port_name=$1
    link_rate=$2

    ## Hierarchical Token Bucket (root qdisc)
    # Not classified traffic is sent as gold traffic.
    tc qdisc add dev ${port_name} root handle 1: htb default 30

    ## Parent token bucket
    # Max rate is set equal to the link capacity
    tc class add dev ${port_name} parent 1: classid 1:1 htb rate ${link_rate}Mbit ceil ${link_rate}Mbit burst 30k

    ## Children tocken buckets
    # Only a small amount of traffic is guaranteed (rate is set to 0.1Mbps).
    # Each traffic class has to borrow the tokens it needs from the parent
    # qdisc according to its priority.

    # Gold traffic qdisc (priority 1)
    tc class add dev ${port_name} parent 1:1 classid 1:10 htb rate 0.1Mbit ceil ${link_rate}Mbit prio 1 burst 30k cburst 30k
    # Filter to classify gold traffic (TOS 128, EXP 3)
    tc filter add dev ${port_name} parent 1: protocol all prio 1 u32 match ip dsfield 128 0xFF flowid 1:10
    # In order to match the EXP field equal to 3, we need to match 0x06 with mask 0x0E starting at byte 2 (see MPLS header)
    tc filter add dev ${port_name} parent 1: protocol all prio 2 u32 match u8 0x06 0x0E at 2 flowid 1:10

    # Silver traffic qdisc (priority 2)
    tc class add dev ${port_name} parent 1:1 classid 1:20 htb rate 0.1Mbit ceil ${link_rate}Mbit prio 2 burst 12k cburst 12k
    # Filter to classify silver traffic (TOS 64, EXP 2)
    tc filter add dev ${port_name} parent 1: protocol all prio 1 u32 match ip dsfield 64 0xFF flowid 1:20
    # In order to match the EXP field equal to 2, we need to match 0x04 with mask 0x0E starting at byte 2 (see MPLS header)
    tc filter add dev ${port_name} parent 1: protocol all prio 2 u32 match u8 0x04 0x0E at 2 flowid 1:20

    # Bronze traffic qdisc (priority 3)
    tc class add dev ${port_name} parent 1:1 classid 1:30 htb rate 0.1Mbit ceil ${link_rate}Mbit prio 3 burst 3k cburst 3k
    # Filter to classify silver traffic (TOS 32, EXP 1)
    tc filter add dev ${port_name} parent 1: protocol all prio 1 u32 match ip dsfield 32 0xFF flowid 1:30
    # In order to match the EXP field equal to 1, we need to match 0x02 with mask 0x0E starting at byte 2 (see MPLS header)
    tc filter add dev ${port_name} parent 1: protocol all prio 2 u32 match u8 0x02 0x0E at 2 flowid 1:30

    ## Stochastic Fairness Queueing (leaves qdiscs)
    # Needed to implement fairness among different flows
    tc qdisc add dev ${port_name} parent 1:10 handle 10: sfq perturb 10 limit 64 quantum 10000
    tc qdisc add dev ${port_name} parent 1:20 handle 20: sfq perturb 10 limit 64 quantum 10000
    tc qdisc add dev ${port_name} parent 1:30 handle 30: sfq perturb 10 limit 64 quantum 10000
}

generate_qos_setting s1-port_R1 6
generate_qos_setting s1-port_R4 4
generate_qos_setting s1-port_S6 6
generate_qos_setting s1-host 12

generate_qos_setting s2-port_R1 4
generate_qos_setting s2-port_R2 4
generate_qos_setting s2-host 12

generate_qos_setting s3-port_R2 6
generate_qos_setting s3-port_R3 4
generate_qos_setting s3-port_S4 6
generate_qos_setting s3-host 12

generate_qos_setting s4-port_R3 6
generate_qos_setting s4-port_R2 4
generate_qos_setting s4-port_S3 6
generate_qos_setting s4-host 12

generate_qos_setting s5-port_R3 4
generate_qos_setting s5-port_R4 4
generate_qos_setting s5-host 12

generate_qos_setting s6-port_R4 6
generate_qos_setting s6-port_R1 4
generate_qos_setting s6-port_S1 6
generate_qos_setting s6-host 12

