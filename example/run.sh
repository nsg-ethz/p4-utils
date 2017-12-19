#!/usr/bin/env bash
#clean
sudo rm -rf *pcap *log topology.db

#run
P4APPRUNNER=p4run
sudo $P4APPRUNNER --conf p4app.json
