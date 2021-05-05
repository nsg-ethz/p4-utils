#!/bin/bash

function spawn_fpm () {
    dest="$1"
    size=$2
    tmux split-window -h -p "$size" -d "mx '$dest' python3 fpmcontroller.py '$dest'"
}

while [ ! -z "$1" ]; do
    spawn_fpm "$1" $((100/($#+1)))
    shift
done

echo "Press Ctrl-C to exit"

(

function handler () { exit; }
trap handler SIGINT
while true; do
    sleep 1
done

)

echo "Received Ctrl-C; exiting..."
sleep 1
tmux kill-pane -a