#!/usr/bin/env python3
import csv
import time
import argparse

class Monitor:

    def __init__(self, csv_file, i, t=0.5, d=60):
        """
        Monitor the interface bandwidth and dump a .csv file with
        the rates in Mbps.

        Attributes
            csv_file (string): path to the output file
            i (string)       : name of the interface to monitor
            t (float)        : interval between data points
            d (float)        : monitoring duration
        """
        current_time = time.time()
        start_time = current_time
        stop_time = current_time + d
        old_tx = None
        old_rx = None
        data = []

        while current_time < stop_time:
            current_time = time.time()
            with open('/sys/class/net/{}/statistics/tx_bytes'.format(i), 'r') as tx:
                with open('/sys/class/net/{}/statistics/rx_bytes'.format(i), 'r') as rx:
                    tx = int(tx.read()) * 8
                    rx = int(rx.read()) * 8
            if not (old_tx is None or old_rx is None):
                delta_tx = tx - old_tx
                delta_rx = rx - old_rx
                tx_rate = (delta_tx / t) / 10**6
                rx_rate = (delta_rx / t) / 10**6
                row = {
                    'time': current_time-start_time,
                    'tx_rate': tx_rate,
                    'rx_rate': rx_rate
                }
                data.append(row)
            old_tx = tx
            old_rx = rx
            time.sleep(max(current_time + t - time.time(), 0))

        with open(csv_file, 'w', newline='') as f:
            fieldnames = ['time', 'tx_rate', 'rx_rate']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in data:
                writer.writerow(row)

def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('-i', metavar='intf', help='interface to monitor', type=str, required=True)
    parser.add_argument('-t', metavar='interval', help='interval between data points in seconds', type=float, required=False, default=0.5)
    parser.add_argument('-d', metavar='duration', help='monitoring duration in seconds', required=False, type=float, default=60)
    parser.add_argument('csv', metavar='OUTFILE', type=str, help='csv dump file')
    
    return parser.parse_args()

if __name__ == '__main__':

    args = get_args()
    monitor = Monitor(args.csv, 
                      args.i,
                      t=args.t,
                      d=args.d)