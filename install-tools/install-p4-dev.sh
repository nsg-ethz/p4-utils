#!/bin/bash

# Configuration variables
KERNEL=$(uname -r)
DEBIAN_FRONTEND=noninteractive sudo apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" upgrade
USER_NAME=$(whoami)
BUILD_DIR=~/p4-tools
SCRIPT_DIR=$(pwd)
NUM_CORES=`grep -c ^processor /proc/cpuinfo`
DEBUG_FLAGS=true
ENABLE_P4_RUNTIME=true

# Software versions
PI_COMMIT="c65fe2ef3e56395efe2a918cf004de1e62430713"    # Feb 4 2021
BMV2_COMMIT="62a013a15ed2c42b1063c26331d73c2560d1e4d0"  # Feb 11 2021
P4C_COMMIT="451b208a5f1a54d9b5ac7975e496ca0a5dee6deb"   # Feb 23 2021
PROTOBUF_COMMIT="v3.6.1"
GRPC_COMMIT="tags/v1.17.2"

# Print commands and exit on errors
set -xe

# Create BUILD_DIR
mkdir -p ${BUILD_DIR}

# Set locale
sudo locale-gen en_US.UTF-8

# Update packages list
sudo apt-get update

# Install generic dependencies
sudo apt-get install -y --no-install-recommends \
git \
python3 \
python3-pip \
python3-setuptools \
libboost-test-dev \
vim \
wget \
tshark \
bridge-utils \
traceroute \
bash-completion \
zip \
xterm \
htop \
arping \
xcscope-el \
gawk \
linux-headers-$KERNEL \
libpcap-dev \
libgmpxx4ldbl \
ca-certificates \
cpp \
emacs \
nano \
git-review \
libboost-filesystem-dev \
libboost-program-options-dev \
libc6-dev \
libevent-dev \
libffi-dev \
libgc1c2 \
libgflags-dev \
libgmp-dev \
libgmp10

# Set Python3 as the default binary
sudo ln -sf /usr/bin/python3 /usr/bin/python
sudo ln -sf /usr/bin/pip3 /usr/bin/pip

# Make the system passwordless
function no_passwd {
    sudo bash -c "echo '${USER_NAME} ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/99_advnet"
    sudo chmod 440 /etc/sudoers.d/99_advnet
}

# Fix site-packages issue (https://github.com/jafingerhut/p4-guide/blob/4111c7fa0a26ccdc40d3200040c767e9bba478ea/bin/install-p4dev-v4.sh#L244)
PY3LOCALPATH=`python ${SCRIPT_DIR}/py3localpath.py`
function move_usr_local_lib_python3_from_site_packages_to_dist_packages {
    local SRC_DIR
    local DST_DIR
    local j
    local k

    SRC_DIR="${PY3LOCALPATH}/site-packages"
    DST_DIR="${PY3LOCALPATH}/dist-packages"

    # When I tested this script on Ubunt 16.04, there was no
    # site-packages directory.  Return without doing anything else if
    # this is the case.
    if [ ! -d ${SRC_DIR} ]
    then
	return 0
    fi

    # Do not move any __pycache__ directory that might be present.
    sudo rm -fr ${SRC_DIR}/__pycache__

    echo "Source dir contents before moving: ${SRC_DIR}"
    ls -lrt ${SRC_DIR}
    echo "Dest dir contents before moving: ${DST_DIR}"
    ls -lrt ${DST_DIR}
    for j in ${SRC_DIR}/*
    do
	echo $j
	k=`basename $j`
	# At least sometimes (perhaps always?) there is a directory
	# 'p4' or 'google' in both the surce and dest directory.  I
	# think I want to merge their contents.  List them both so I
	# can see in the log what was in both at the time:
        if [ -d ${SRC_DIR}/$k -a -d ${DST_DIR}/$k ]
   	then
	    echo "Both source and dest dir contain a directory: $k"
	    echo "Source dir $k directory contents:"
	    ls -l ${SRC_DIR}/$k
	    echo "Dest dir $k directory contents:"
	    ls -l ${DST_DIR}/$k
            sudo mv ${SRC_DIR}/$k/* ${DST_DIR}/$k/
	    sudo rmdir ${SRC_DIR}/$k
	else
	    echo "Not a conflicting directory: $k"
            sudo mv ${SRC_DIR}/$k ${DST_DIR}/$k
	fi
    done

    echo "Source dir contents after moving: ${SRC_DIR}"
    ls -lrt ${SRC_DIR}
    echo "Dest dir contents after moving: ${DST_DIR}"
    ls -lrt ${DST_DIR}
}

## Dependencies
# Install protobuf dependencies
function do_protobuf_deps {
    sudo apt-get install -y --no-install-recommends \
    autoconf \
    automake \
    libtool \
    curl \
    make \
    g++ \
    unzip
}

# Install gprcio dependencies
function do_grpc_deps {
    sudo apt-get install -y --no-install-recommends \
    build-essential \
    autoconf \
    libtool \
    pkg-config
}

# Install sysrepo dependencies
function do_sysrepo_libyang_deps {
    # Dependencies in : https://github.com/p4lang/PI/blob/master/proto/README.md
    sudo apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libpcre3-dev \
    libavl-dev \
    libev-dev \
    libprotobuf-c-dev \
    protobuf-c-compiler
}

# Install PI dependencies
function do_PI_deps {
    sudo apt-get install -y --no-install-recommends \
    libjudy-dev \
    libreadline-dev \
    valgrind \
    libtool-bin \
    libboost-dev \
    libboost-system-dev \
    libboost-thread-dev
}

# Install p4c dependencies
function do_p4c_deps {
    sudo apt-get install -y --no-install-recommends \
    cmake \
    g++ \
    git \
    automake \
    libtool \
    libgc-dev \
    bison \
    flex \
    libfl-dev \
    libgmp-dev \
    libboost-dev \
    libboost-iostreams-dev \
    libboost-graph-dev \
    llvm \
    pkg-config \
    python3 \
    python3-pip \
    tcpdump \
    doxygen \
    graphviz \
    texlive-full

    sudo pip install \
    scapy \
    ply \
    ipaddr
}

# Install behavioral model dependencies
function do_bmv2_deps {
    # Clone source
    cd ${BUILD_DIR}
    if [ ! -d bmv2 ]; then
        git clone https://github.com/p4lang/behavioral-model.git bmv2
    fi
    cd bmv2
    git checkout ${BMV2_COMMIT}

    # Install dependencies
    ./install_deps.sh
}

## Modules
# Install wireshark
function do_wireshark {
    sudo DEBIAN_FRONTEND=noninteractive apt-get -y install wireshark
    echo "wireshark-common wireshark-common/install-setuid boolean true" | sudo debconf-set-selections
    sudo DEBIAN_FRONTEND=noninteractive dpkg-reconfigure wireshark-common
}

# Install iperf3
function do_iperf3 {
    # Install iperf3 (last version)
    cd /tmp
    sudo apt-get remove  -y --no-install-recommends iperf3 libiperf0
    wget https://iperf.fr/download/ubuntu/libiperf0_3.1.3-1_amd64.deb
    wget https://iperf.fr/download/ubuntu/iperf3_3.1.3-1_amd64.deb
    sudo dpkg -i libiperf0_3.1.3-1_amd64.deb iperf3_3.1.3-1_amd64.deb
    rm libiperf0_3.1.3-1_amd64.deb iperf3_3.1.3-1_amd64.deb
}

# Configure tmux
function do_tmux {
    cd $SCRIPT_DIR
    cp conf_files/tmux.conf ~/.tmux.conf
}

# Install protobuf from source
function do_protobuf {
    # Install dependencies
    do_protobuf_deps

    # Clone source
    cd ${BUILD_DIR}
    if [ ! -d protobuf ]; then
        git clone https://github.com/protocolbuffers/protobuf protobuf
    fi
    cd protobuf
    git checkout ${PROTOBUF_COMMIT}
    git submodule update --init --recursive

    # Build protobuf C++
    export CFLAGS="-Os"
    export CXXFLAGS="-Os"
    export LDFLAGS="-Wl,-s"

    ./autogen.sh
    ./configure --prefix=/usr
    make -j${NUM_CORES}
    sudo make install
    sudo ldconfig
    make clean

    unset CFLAGS CXXFLAGS LDFLAGS

    # Build protobuf Python
    cd python
    sudo python setup.py install --cpp_implementation
}

# Install grpc (needed for PI)
function do_grpc {
    # Install dependencies
    do_grpc_deps

    # Clone source
    cd ${BUILD_DIR}
    if [ ! -d grpc ]; then
      git clone https://github.com/grpc/grpc.git grpc
    fi
    cd grpc
    git checkout ${GRPC_COMMIT}
    git submodule update --init --recursive

    # Build grpc
    export LDFLAGS="-Wl,-s"

    make -j${NUM_CORES}
    sudo make install
    sudo ldconfig
    make clean

    unset LDFLAGS

    # Build gprcio
    sudo pip install -r requirements.txt
    sudo pip install .
}

# Install sysrepo (tentative gNMI support with sysrepo)
function do_sysrepo_libyang {
    # Install dependencies
    do_sysrepo_libyang_deps

    # Clone source libyang
    cd ${BUILD_DIR}
    if [ ! -d libyang ]; then
        git clone https://github.com/CESNET/libyang.git libyang
    fi
    cd libyang
    git checkout v0.16-r1

    # Build libyang
    mkdir build
    cd build
    cmake ..
    make
    sudo make install
    sudo ldconfig

    # Clone source sysrepo
    cd ${BUILD_DIR}
    if [ ! -d sysrepo ]; then
        git clone https://github.com/sysrepo/sysrepo.git sysrepo
    fi
    cd sysrepo
    git checkout v0.7.5

    # Build sysrepo
    mkdir build
    cd build
    cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_EXAMPLES=Off -DCALL_TARGET_BINS_DIRECTLY=Off ..
    make
    sudo make install
    sudo ldconfig
}

# Install PI
function do_PI {
    # Install dependencies
    do_PI_deps

    # Clone source
    cd ${BUILD_DIR}
    if [ ! -d PI ]; then
        git clone https://github.com/p4lang/PI.git PI
    fi
    cd PI
    git checkout ${PI_COMMIT}
    git submodule update --init --recursive

    # Build PI
    ./autogen.sh
    if [ "$DEBUG_FLAGS" = true ] ; then
        ./configure --with-proto --with-sysrepo "CXXFLAGS=-O0 -g"
    else
        ./configure --with-proto --with-sysrepo
    fi
    make -j${NUM_CORES}
    sudo make install
    sudo ldconfig
    make clean
}

# Install behavioral model
function do_bmv2 {
    # Install dependencies
    if [ "$ENABLE_P4_RUNTIME" = false ] ; then
        do_bmv2_deps
    fi

    # Clone source
    cd ${BUILD_DIR}
    if [ ! -d bmv2 ]; then
        git clone https://github.com/p4lang/behavioral-model.git bmv2
    fi
    cd bmv2
    git checkout ${BMV2_COMMIT}

    # Build behavioral-model
    ./autogen.sh
    if [ "$DEBUG_FLAGS" = true ] && [ "$ENABLE_P4_RUNTIME" = true ] ; then
        ./configure --with-pi --with-thrift --with-nanomsg --enable-debugger --disable-elogger "CXXFLAGS=-O0 -g"
    elif [ "$DEBUG_FLAGS" = true ] && [ "$ENABLE_P4_RUNTIME" = false ] ; then
        ./configure --with-thrift --with-nanomsg --enable-debugger --enable-elogger "CXXFLAGS=-O0 -g"
    elif [ "$DEBUG_FLAGS" = false ] && [ "$ENABLE_P4_RUNTIME" = true ] ; then
        ./configure --with-pi --without-nanomsg --disable-elogger --disable-logging-macros 'CFLAGS=-g -O2' 'CXXFLAGS=-g -O2'
    else
        ./configure --without-nanomsg --disable-elogger --disable-logging-macros 'CFLAGS=-g -O2' 'CXXFLAGS=-g -O2'
    fi
    make -j${NUM_CORES}
    sudo make install
    sudo ldconfig

    # Build simple_switch_grpc
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
    fi
}

# Install p4c
function do_p4c {
    # Install dependencies
    do_p4c_deps

    # Clone source
    cd ${BUILD_DIR}
    if [ ! -d p4c ]; then
        git clone https://github.com/p4lang/p4c.git p4c
    fi
    cd p4c
    git checkout ${P4C_COMMIT}
    git submodule update --init --recursive
    mkdir -p build
    cd build

    # Build p4c
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

# Install ptf
function do_ptf {
    # Clone source
    cd ${BUILD_DIR}
    if [ ! -d ptf ]; then
        git clone https://github.com/p4lang/ptf.git ptf
    fi
    cd ptf
    git pull origin master

    # Build ptf
    sudo python setup.py install
}

# Install mininet
function do_mininet {
    # Clone source
    cd $HOME
    git clone git://github.com/mininet/mininet mininet
    cd mininet

    # Build mininet
    sudo ./util/install.sh -nwv
}

# Install p4-utils
function do_p4-utils {
    # Clone source
    cd ${BUILD_DIR}
    if [ ! -d p4-utils ]; then
        git clone https://github.com/nsg-ethz/p4-utils.git p4-utils
    fi
    cd p4-utils
    git checkout junota

    # Build p4-utils    
    sudo ./install.sh
}

# Install p4-learning
function do_p4-learning {
    # Clone source
    cd ${BUILD_DIR}
    if [ ! -d p4-learning ]; then
        git clone https://github.com/nsg-ethz/p4-learning.git p4-learning
    fi
    cd p4-learning
    git checkout junota
}

no_passwd
do_wireshark
do_iperf3
do_tmux
do_protobuf
if [ "$ENABLE_P4_RUNTIME" = true ] ; then
    do_grpc
    do_bmv2_deps
    do_sysrepo_libyang
    do_PI
fi
do_bmv2
do_p4c
# ptf is Python2 only
do_ptf
do_mininet
do_p4-utils
do_p4-learning
move_usr_local_lib_python3_from_site_packages_to_dist_packages
echo "Installation complete!"