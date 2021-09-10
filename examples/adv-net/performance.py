"""Computes the performance of your run

Example usage: python2 performance.py --traffic-spec ../scenarios/default.traffic

"""

import os
import argparse
import csv
from collections import OrderedDict


traffic_weights = {
    "128": 10,
    "64":  4,
    "32":  1
}

traffic_names = OrderedDict([
    ("128", "Gold"),
    ("64",  "Silver"),
    ("32",  "Bronze")
])

class Performance(object):
    """Load the traffic matrix and generate everything."""

    def __init__(self, traffic, out_path):
        self.traffic_spec = traffic
        self.out_path = out_path
        self.flows = self._load_traffic_spec()
        self._count_points()

    def _load_traffic_spec(self):
        """Loads traffic matrix spec"""

        flows = []
        with open(self.traffic_spec, 'r') as csvfile:
            dialect = csv.Sniffer().sniff(csvfile.read(1024))
            csvfile.seek(0)
            reader = csv.DictReader(csvfile, dialect=dialect)
            return list(reader)

    def _read_sequences(self, file_name):
        """Helper function to read"""
        
        with open(file_name, "r") as f:
            return set([int(x) for x in f.read().split()])

    def _count_flow(self, flow):
        """ Counts the packet in out for a given flow"""

        sender_path = "{}/sender_{}_{}_{}_{}.txt".format(self.out_path,
                                                         flow["src"], flow["dst"], flow["sport"], flow["dport"])
        sender_seq =  self._read_sequences(sender_path)                                           
        receiver_path = "{}/receiver_{}_{}_{}_{}.txt".format(self.out_path,
                                                         flow["src"], flow["dst"], flow["sport"], flow["dport"])         
        receiver_seq =  self._read_sequences(receiver_path)                                          
        received_and_sent = sender_seq.intersection(receiver_seq)

        # returns pkt_in and pkt_out (sent from this sender and not repeated)
        return len(sender_seq), len(received_and_sent)                                                                                 

    def _count_points(self):
        """ Counts all flows in/out """

        self._traffic_counts = {
            "128":
            {"pkts_in": 0.0, "pkts_out": 0.0},
            "64":
            {"pkts_in": 0.0, "pkts_out": 0.0},
            "32":
            {"pkts_in": 0.0, "pkts_out": 0.0},
        }
        for flow in self.flows:
            tos = flow["tos"]
            pkt_in, pkt_out = self._count_flow(flow)
        
            self._traffic_counts[tos]["pkts_in"] += pkt_in
            self._traffic_counts[tos]["pkts_out"] += pkt_out
    
    def get_weighted_perfomance(self):
        """ computes final performance """

        self._count_points()
        weighted_performance = 0
        for traffic_type, packets in self._traffic_counts.items():
            # type weighted performance
            if packets["pkts_in"] == 0:
                _performance = 0
            else:
                _performance = (packets["pkts_out"]/packets["pkts_in"]) * (traffic_weights[traffic_type])/(sum(traffic_weights.values()))
            weighted_performance += _performance

        return weighted_performance

    def print_performance(self):
        """ Print per traffic class and weighted performance """

        print("\n===============================")
        print("""Your last run performances are:\n===============================""")

        weighted_performance = self.get_weighted_perfomance()
        for traffic_type, traffic_name in traffic_names.items():
            packets = self._traffic_counts[traffic_type]
            warning = ""
            if packets["pkts_in"] == 0:
                _performance = 0
                warning = "\033[31m(warning: you did not send traffic for this type)\033[39m"
            else:
                _performance = (packets["pkts_out"]/packets["pkts_in"])
            print("{:10} {:.5f} {}".format(traffic_names[traffic_type], _performance, warning))
        print("-------------------------------")
        print("Weighted   {:.5f}".format(weighted_performance))


if __name__ == "__main__":
    # pylint: disable=invalid-name
    parser = argparse.ArgumentParser()
    parser.add_argument('--traffic-spec',
                        help='Traffic generation specification',
                        type=str, required=True)
    parser.add_argument('--out-path',
                        help='Path to flows logs',
                        type=str, required=False, default="./flows")

    args = parser.parse_args()

    performance = Performance(
        args.traffic_spec, args.out_path
    )

    performance.print_performance()
