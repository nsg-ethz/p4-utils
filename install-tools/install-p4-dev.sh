#!/bin/bash

USER_NAME=<put your username here>

# Print commands and exit on errors
set -xe

#Install Generic Dependencies and Programs

sudo apt-get update

# removed
KERNEL=$(uname -r)
DEBIAN_FRONTEND=noninteractive sudo apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" upgrade
sudo apt-get install -y --no-install-recommends \
  autoconf \
  automake \
  bison \
  build-essential \
  ca-certificates \
  cmake \
  cpp \
  curl \
  emacs nano\
  flex \
  git \
  git-review \
  libboost-dev \
  libboost-filesystem-dev \
  libboost-iostreams-dev \
  libboost-program-options-dev \
  libboost-system-dev \
  libboost-thread-dev \
  libc6-dev \
  libevent-dev \
  libffi-dev \
  libfl-dev \
  libgc-dev \
  libgc1c2 \
  libgflags-dev \
  libgmp-dev \
  libgmp10 \
  libgmpxx4ldbl \
  libjudy-dev \
  libpcap-dev \
  libreadline-dev \
  libtool \
  linux-headers-$KERNEL\
  make \
  pkg-config \
  python \
  python-dev \
  python-ipaddr \
  python-setuptools \
  tcpdump \
  zip unzip \
  vim \
  wget \
  xcscope-el \
  xterm \
  htop \
  arping \
  gawk \
  iptables \
  libprotobuf-c-dev \
  g++ \
  bash-completion \
  traceroute


#Install pip (Python2.7) from source
curl https://bootstrap.pypa.io/2.7/get-pip.py -o get-pip2.py
# python 2
python get-pip2.py
sudo python get-pip2.py

#Install pip (Python3) from source
curl https://bootstrap.pypa.io/get-pip.py -o get-pip3.py
# python 3
python3 get-pip3.py
sudo python3 get-pip3.py

# remove
rm get-pip2.py
rm get-pip3.py

#python libraries
sudo pip install ipaddress

# debugging
sudo pip install ipython ipdb

# make the system passwordless
sudo bash -c 'echo "${USER_NAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/99_advnet'
sudo chmod 440 /etc/sudoers.d/99_advnet

sudo locale-gen en_US.UTF-8


# user apps
#Installs wireshark skiping the inte
sudo DEBIAN_FRONTEND=noninteractive apt-get -y install wireshark
echo "wireshark-common wireshark-common/install-setuid boolean true" | sudo debconf-set-selections
sudo DEBIAN_FRONTEND=noninteractive dpkg-reconfigure wireshark-common

sudo apt-get -y --no-install-recommends install \
    vim \
    wget \
    tshark

# Install iperf3 (last version)
PREV_PATH=`pwd`
cd /tmp
sudo apt-get remove  -y --no-install-recommends iperf3 libiperf0
wget https://iperf.fr/download/ubuntu/libiperf0_3.1.3-1_amd64.deb
wget https://iperf.fr/download/ubuntu/iperf3_3.1.3-1_amd64.deb
sudo dpkg -i libiperf0_3.1.3-1_amd64.deb iperf3_3.1.3-1_amd64.deb
rm libiperf0_3.1.3-1_amd64.deb iperf3_3.1.3-1_amd64.deb

cd $PREV_PATH
cp conf_files/tmux.conf ~/.tmux.conf

# P4 Tools installs
BUILD_DIR=~/p4-tools

#Install requirements (a lot of them might be redundant

sudo apt update
sudo apt-get install -y --no-install-recommends \
    libavl-dev \
    libboost-test-dev \
    libev-dev \
    libpcre3-dev \
    libtool \
    make \
    pkg-config \
    protobuf-c-compiler \
    tcpdump \
    wget \
    unzip \
    valgrind \
    bridge-utils

sudo -H pip install setuptools cffi ipaddr ipaddress pypcap

# Advanced Topics in Communication networks 2019 Commits
#BMV2_COMMIT="b447ac4c0cfd83e5e72a3cc6120251c1e91128ab" # Aug 6 2019
#P4C_COMMIT="8742052c70836a8b0855e621aad9d6cc11b1f6ee"  # Sep 8 2019
#PI_COMMIT="41358da0ff32c94fa13179b9cee0ab597c9ccbcc"   # Aug 6 2019

# Advanced Topics in Communication networks 2020 Commits
BMV2_COMMIT="c65fe2ef3e56395efe2a918cf004de1e62430713" # Feb 4 2021
P4C_COMMIT="62a013a15ed2c42b1063c26331d73c2560d1e4d0"  # Feb 11 2021
PI_COMMIT="451b208a5f1a54d9b5ac7975e496ca0a5dee6deb"   # Feb 23 2021

PROTOBUF_COMMIT="v3.6.1"
GRPC_COMMIT="tags/v1.17.2"

NUM_CORES=`grep -c ^processor /proc/cpuinfo`

mkdir -p ${BUILD_DIR}

# If false, build tools without debug features to improve throughput of BMv2 and
# reduce CPU/memory footprint.
DEBUG_FLAGS=true
ENABLE_P4_RUNTIME=true

#install mininet
function do_mininet {

    cd $HOME

    git clone git://github.com/mininet/mininet mininet
    cd mininet
    sudo ./util/install.sh -nwv
    cd ..
}

#Install Protobuf
function do_protobuf {
    cd ${BUILD_DIR}
    if [ ! -d protobuf ]; then
      git clone https://github.com/google/protobuf.git
    fi
    cd protobuf
    git fetch
    git checkout ${PROTOBUF_COMMIT}

    export CFLAGS="-Os"
    export CXXFLAGS="-Os"
    export LDFLAGS="-Wl,-s"
    ./autogen.sh
    ./configure --prefix=/usr
    make -j${NUM_CORES}
    sudo make install
    sudo ldconfig
    unset CFLAGS CXXFLAGS LDFLAGS
    #clean 0.5G
    make clean

    # force install python module
    cd python
    sudo python setup.py install --cpp_implementation
}

#needed for PI.
function do_grpc {
    cd ${BUILD_DIR}
    if [ ! -d grpc ]; then
      git clone https://github.com/grpc/grpc.git
    fi
    cd grpc
    git fetch
    git checkout ${GRPC_COMMIT}
    git submodule update --init --recursive

    export LDFLAGS="-Wl,-s"
    make -j${NUM_CORES}
    sudo make install
    sudo ldconfig
    unset LDFLAGS
    make clean

    # Install gRPC Python Package
    sudo pip install -r requirements.txt
    sudo pip install grpcio==1.17.1
    sudo pip install protobuf==3.6.1
    sudo pip install .
}

#needed for PI, this is the same than install_deps.sh but without the first apt-gets
function do_bmv2_deps {
    # BMv2 deps (needed by PI)
    cd ${BUILD_DIR}
    if [ ! -d bmv2 ]; then
        git clone https://github.com/p4lang/behavioral-model.git bmv2
    fi
    cd bmv2
    git checkout ${BMV2_COMMIT}
    ./install_deps.sh
}

#Tentative gNMI support with sysrepo
function do_sysrepo {
    # Dependencies in : https://github.com/p4lang/PI/blob/master/proto/README.md
    sudo apt-get --yes install build-essential cmake libpcre3-dev libavl-dev libev-dev libprotobuf-c-dev protobuf-c-compiler

    cd ${BUILD_DIR}

    # Install libyang
    if [ ! -d libyang ]; then
        git clone https://github.com/CESNET/libyang.git
    fi
    cd libyang
    git checkout v0.16-r1
    mkdir build
    cd build
    cmake ..
    make
    sudo make install
    sudo ldconfig

    cd ../..

    # Install sysrepo
    if [ ! -d sysrepo ]; then
        git clone https://github.com/sysrepo/sysrepo.git
    fi
    cd sysrepo
    git checkout v0.7.5
    mkdir build
    cd build
    cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_EXAMPLES=Off -DCALL_TARGET_BINS_DIRECTLY=Off ..
    make
    sudo make install
    sudo ldconfig
    cd ..
}

#only if we want P4Runtime
function do_PI {
    cd ${BUILD_DIR}
    if [ ! -d PI ]; then
        git clone https://github.com/p4lang/PI.git
    fi
    cd PI
    git fetch
    git checkout ${PI_COMMIT}
    git submodule update --init --recursive
    ./autogen.sh
    if [ "$DEBUG_FLAGS" = true ] ; then
        ./configure --with-proto --with-sysrepo "CXXFLAGS=-O0 -g"
    else
        ./configure --with-proto --with-sysrepo
    fi
    make -j${NUM_CORES}
    sudo make install
    sudo ldconfig
    cd ..
}

function do_bmv2 {

    if [ "$ENABLE_P4_RUNTIME" = false ] ; then
        do_bmv2_deps
    fi

    cd ${BUILD_DIR}
    if [ ! -d bmv2 ]; then
       git clone https://github.com/p4lang/behavioral-model.git bmv2
    fi
    cd bmv2
    git checkout ${BMV2_COMMIT}
    ./autogen.sh

    #./configure 'CXXFLAGS=-O0 -g' --with-nanomsg --with-thrift --enable-debugger
    if [ "$DEBUG_FLAGS" = true ] && [ "$ENABLE_P4_RUNTIME" = true ] ; then
        #./configure --enable-debugger --enable-elogger --with-thrift --with-nanomsg  "CXXFLAGS=-O0 -g"
        ./configure --with-pi --enable-debugger --with-thrift --with-nanomsg --disable-elogger "CXXFLAGS=-O0 -g"

    elif [ "$DEBUG_FLAGS" = true ] && [ "$ENABLE_P4_RUNTIME" = false ] ; then
        ./configure --enable-debugger --enable-elogger --with-thrift --with-nanomsg  "CXXFLAGS=-O0 -g"

    elif [ "$DEBUG_FLAGS" = false ] && [ "$ENABLE_P4_RUNTIME" = true ] ; then
         ./configure --with-pi --without-nanomsg --disable-elogger --disable-logging-macros 'CFLAGS=-g -O2' 'CXXFLAGS=-g -O2'
    else #both false
        #Option removed until we use this commit: https://github.com/p4lang/behavioral-model/pull/673
        #./configure --with-pi --disable-logging-macros --disable-elogger --without-nanomsg
        ./configure --without-nanomsg --disable-elogger --disable-logging-macros 'CFLAGS=-g -O2' 'CXXFLAGS=-g -O2'

    fi
    make -j${NUM_CORES}
    sudo make install
    sudo ldconfig

    # Simple_switch_grpc target
    if [ "$ENABLE_P4_RUNTIME" = true ] ; then
        cd targets/simple_switch_grpc
        ./autogen.sh

        if [ "$DEBUG_FLAGS" = true ] ; then
            ./configure --with-sysrepo --with-thrift "CXXFLAGS=-O0 -g"
        else
            ./configure --with-sysrepo --with-thrift
        fi

        make -j${NUM_CORES}
        sudo make install
        sudo ldconfig
        cd ../../..
    fi
}

function do_bmv2_opt {

    cd ${BUILD_DIR}
    if [ ! -d bmv2-opt ]; then
       git clone https://github.com/p4lang/behavioral-model.git bmv2-opt
    fi
    cd bmv2-opt
    
    git checkout ${BMV2_COMMIT}
    ./autogen.sh

    ./configure --without-nanomsg --disable-elogger --disable-logging-macros 'CFLAGS=-g -O2' 'CXXFLAGS=-g -O2'
    make -j${NUM_CORES}
    
    # dont install by default
    #sudo make install
    #sudo ldconfig
}

function do_p4c {
    cd ${BUILD_DIR}
    if [ ! -d p4c ]; then
        git clone https://github.com/p4lang/p4c.git
    fi
    cd p4c
    git fetch
    git checkout ${P4C_COMMIT}
    git submodule update --init --recursive

    mkdir -p build
    cd build

    if [ "$DEBUG_FLAGS" = true ] ; then
        cmake .. -DCMAKE_BUILD_TYPE=DEBUG $*

    else
        # Debug build
        cmake ..
    fi

    make -j${NUM_CORES}
    sudo make install
    sudo ldconfig

    cd ..
    rm -rf build/
    cd ..
}

function do_scapy-vxlan {
    cd ${BUILD_DIR}
    if [ ! -d scapy-vxlan ]; then
        git clone https://github.com/p4lang/scapy-vxlan.git
    fi
    cd scapy-vxlan

    git pull origin master

    sudo python setup.py install
}

function do_scapy {
    # Installs normal scapy (installs latest version 2.4.4 right now)
    sudo pip install scapy
}

function do_ptf {
    cd ${BUILD_DIR}
    if [ ! -d ptf ]; then
        git clone https://github.com/p4lang/ptf.git
    fi
    cd ptf
    git pull origin master

    sudo python setup.py install
}

function do_p4-utils {
    cd ${BUILD_DIR}
    if [ ! -d p4-utils ]; then
        git clone https://github.com/nsg-ethz/p4-utils.git
    fi
    cd p4-utils
    sudo ./install.sh
    cd ..
}

function do_p4-learning {
    cd ${BUILD_DIR}
    if [ ! -d p4-learning ]; then
        git clone https://github.com/nsg-ethz/p4-learning.git
    fi
    cd ..
}

# its needed for p4c
do_protobuf
if [ "$ENABLE_P4_RUNTIME" = true ] ; then
    do_grpc
    do_bmv2_deps
    do_sysrepo
    do_PI
fi
do_bmv2
#do_bmv2_opt
do_p4c
do_scapy
do_ptf
do_mininet
do_p4-utils
do_p4-learning
echo "Done with p4-tools install!"
