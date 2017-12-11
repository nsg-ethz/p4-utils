#!/usr/bin/env bash
#clean
sudo rm -rf *pcap *log topology.db

#run
P4APPRUNNER=././../p4utils/p4utils.py
sudo python $P4APPRUNNER
