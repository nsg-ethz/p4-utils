from netaddr import IPAddress

# Pipe variable
p4 = bfrt.heavy_hitter.pipe

# Table variable
l3 = p4.Ingress.ipv4_lpm

# Add forwarding rules
l3.add_with_ipv4_forward(dstAddr=IPAddress('10.2.2.2'), dstAddr_p_length=32, port=1, dst_addr='00:00:0a:02:02:02')
l3.add_with_ipv4_forward(dstAddr=IPAddress('10.1.1.2'), dstAddr_p_length=32, port=2, dst_addr='3a:e6:5d:d5:f5:0b')