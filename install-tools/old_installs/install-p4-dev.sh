#!/bin/bash

# Author: Edgar Costa Molero
# Email: cedgar@ethz.ch

# This scripts installs all the required software to learn and prototype P4
# programs using the p4lang software suite. 

# Furthermore, we install p4-utils and p4-learning and ffr routers.

# This install script has only been tested with the following systems:
# Ubuntu 18.04

# Configuration variables
# Currently loaded linux kernel
KERNEL=$(uname -r)
# non interactive install
DEBIAN_FRONTEND=noninteractive sudo apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" upgrade
# username
USER_NAME=$(whoami)
# building directory
BUILD_DIR=~/p4-tools
# number of cores
NUM_CORES=`grep -c ^processor /proc/cpuinfo`
DEBUG_FLAGS=true
P4_RUNTIME=true
SYSREPO=false   # Sysrepo prevents simple_switch_grpc from starting correctly
FRROUTING=true
DOCUMENTATION=true

### Checks

os_message() {
    1>&2 echo "Found ID ${ID} and VERSION_ID ${VERSION_ID} in /etc/os-release"
    1>&2 echo "This script only supports these:"
    1>&2 echo "    ID ubuntu, VERSION_ID in 20.04 22.04"
    1>&2 echo ""
    1>&2 echo "Proceed installing at your own risk."
}


# Software versions

# Newer versions of protobuf and grpc can be used but the
# testing and development has been done with protobuf 3.6.1
# and grpc 1.17.2.
PROTOBUF_VER="3.6.1"
GRPC_VER="1.17.2"

LIBYANG_VER="1.0.225"
PI_COMMIT="c65fe2ef3e56395efe2a918cf004de1e62430713"    # Feb 4 2021
BMV2_COMMIT="62a013a15ed2c42b1063c26331d73c2560d1e4d0"  # Feb 11 2021
P4C_COMMIT="451b208a5f1a54d9b5ac7975e496ca0a5dee6deb"   # Feb 23 2021
FRROUTING_COMMIT="18f209926fb659790926b82dd4e30727311d22aa" # Mar 25 2021
PROTOBUF_COMMIT="v${PROTOBUF_VER}"
GRPC_COMMIT="tags/v${GRPC_VER}"
LIBYANG_COMMIT="v${LIBYANG_VER}"

# p4-utils branch 
# TODO: improve this in the future
P4_UTILS_BRANCH="master"

# Print commands and exit on errors
set -xe

# Make the system passwordless
if [ ! -f /etc/sudoers.d/99_advnet ]; then
    sudo bash -c "echo '${USER_NAME} ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/99_advnet"
    sudo chmod 440 /etc/sudoers.d/99_advnet
fi

# Create BUILD_DIR
mkdir -p ${BUILD_DIR}

# Set locale
sudo locale-gen en_US.UTF-8

# Update packages list
sudo apt-get update

# Install shared dependencies
sudo apt-get install -y --no-install-recommends \
arping \
autoconf \
automake \
bash-completion \
bridge-utils \
build-essential \
ca-certificates \
cmake \
cpp \
curl \
emacs \
gawk \
git \
git-review \
g++ \
htop \
libboost-dev \
libboost-filesystem-dev \
libboost-program-options-dev \
libboost-test-dev \
libc6-dev \
libevent-dev \
libgc1c2 \
libgflags-dev \
libgmpxx4ldbl \
libgmp10 \
libgmp-dev \
libffi-dev \
libtool \
libpcap-dev \
linux-headers-$KERNEL \
make \
nano \
pkg-config \
python3 \
python3-dev \
python3-pip \
python3-setuptools \
tmux \
traceroute \
vim \
wget \
xcscope-el \
xterm \
zip

# upgrade pip3
sudo pip3 install --upgrade pip==21.3.1

# Set Python3 as the default binary
sudo ln -sf $(which python3) /usr/bin/python
sudo ln -sf $(which pip3) /usr/bin/pip

# Install shared dependencies (pip3)
sudo pip3 install \
cffi \
ipaddress \
ipdb \
ipython \
pypcap

# Install wireshark
sudo DEBIAN_FRONTEND=noninteractive apt-get -y install wireshark
echo "wireshark-common wireshark-common/install-setuid boolean true" | sudo debconf-set-selections
sudo DEBIAN_FRONTEND=noninteractive dpkg-reconfigure wireshark-common
sudo apt-get -y --no-install-recommends install \
tcpdump \
tshark

# Install iperf3 (last version)
cd /tmp
sudo apt-get remove  -y --no-install-recommends iperf3 libiperf0
wget https://iperf.fr/download/ubuntu/libiperf0_3.1.3-1_amd64.deb
wget https://iperf.fr/download/ubuntu/iperf3_3.1.3-1_amd64.deb
sudo dpkg -i libiperf0_3.1.3-1_amd64.deb iperf3_3.1.3-1_amd64.deb
rm libiperf0_3.1.3-1_amd64.deb iperf3_3.1.3-1_amd64.deb

# Configure tmux
wget -O ~/.tmux.conf https://raw.githubusercontent.com/nsg-ethz/p4-utils/${P4_UTILS_BRANCH}/install-tools/conf_files/tmux.conf

# Fix site-packages issue 
# Modified file from 
# https://github.com/jafingerhut/p4-guide/blob/4111c7fa0a26ccdc40d3200040c767e9bba478ea/bin/install-p4dev-v4.sh#L244
PY3LOCALPATH=`curl -sSL https://raw.githubusercontent.com/nsg-ethz/p4-utils/${P4_UTILS_BRANCH}/install-tools/scripts/py3localpath.py | python3`
function site_packages_fix {
    local SRC_DIR
    local DST_DIR

    SRC_DIR="${PY3LOCALPATH}/site-packages"
    DST_DIR="${PY3LOCALPATH}/dist-packages"

    # When I tested this script on Ubunt 16.04, there was no
    # site-packages directory.  Return without doing anything else if
    # this is the case.
    if [ ! -d ${SRC_DIR} ]; then
	    return 0
    fi

    echo "Adding ${SRC_DIR} to Python3 path..."
    sudo su -c "echo '${SRC_DIR}' > ${DST_DIR}/p4-tools.pth"
    echo "Done!"
}

# Fix google module issue which creates problems with sphinx
function google_module_fix {
    curl -sSL https://raw.githubusercontent.com/nsg-ethz/p4-utils/${P4_UTILS_BRANCH}/install-tools/scripts/protoinitfix.py | sudo python3
}

## Module-specific dependencies
# Install protobuf dependencies
function do_protobuf_deps {
    sudo apt-get install -y --no-install-recommends \
    unzip
}

# Install gprcio dependencies
# grpc depends only on shared deps

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
    libboost-system-dev \
    libboost-thread-dev \
    libjudy-dev \
    libreadline-dev \
    libtool-bin \
    valgrind
}

# Install p4c dependencies
function do_p4c_deps {
    sudo apt-get install -y --no-install-recommends \
    bison \
    clang \
    flex \
    iptables \
    libboost-graph-dev \
    libboost-iostreams-dev \
    libelf-dev \
    libfl-dev \
    libgc-dev \
    llvm \
    net-tools \
    zlib1g-dev

    sudo pip3 install \
    ipaddr \
    pyroute2 \
    ply \
    scapy
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

    # Install protobuf Python

    # Google protobuf module is installed as p4-utils 
    # requirement. We do not use the following source 
    # compiled method because it creates problems with
    # other Python libraries.

    # cd python
    # sudo python3 setup.py install --cpp_implementation
}

# Install grpc (needed for PI)
function do_grpc {
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

    # Install gprcio Python

    # Do not install grpcio here and postpone it to
    # the installation of p4-utils.

    # sudo pip3 install -r requirements.txt
    # sudo pip3 install .
}

# Install sysrepo (tentative gNMI support with sysrepo)
# Warning: In theory not used since grpc crashes
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
    if [ ! -d build ]; then
        mkdir build
    else
        sudo rm -R build
        mkdir build
    fi
    cd build
    cmake ..
    make -j${NUM_CORES}
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
    make -j${NUM_CORES}
    sudo make install
    sudo ldconfig
}

# Install libyang necessary for FRRouting
function do_libyang {
    # Install dependencies
    do_sysrepo_libyang_deps

    # Clone source libyang
    cd ${BUILD_DIR}
    if [ ! -d libyang ]; then
        git clone https://github.com/CESNET/libyang.git libyang
    fi
    cd libyang
    git checkout ${LIBYANG_COMMIT}

    # Build libyang
    if [ ! -d build ]; then
        mkdir build
    else
        rm -R build
        mkdir build
    fi
    cd build
    cmake -DENABLE_LYD_PRIV=ON -DCMAKE_INSTALL_PREFIX:PATH=/usr \
        -D CMAKE_BUILD_TYPE:String="Release" ..
    make -j${NUM_CORES}
    sudo make install
    sudo ldconfig
}

# Install FRRouting dependencies
function do_frrouting_deps {
    # Install dependencies
    do_libyang

    sudo apt-get install -y \
    git autoconf automake libtool make libreadline-dev texinfo \
    pkg-config libpam0g-dev libjson-c-dev bison flex python3-pytest \
    libc-ares-dev python3-dev libsystemd-dev python-ipaddress python3-sphinx \
    install-info build-essential libsystemd-dev libsnmp-dev perl libcap-dev \
    libelf-dev
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
    if [ "$DEBUG_FLAGS" = true ]; then
        if [ "$SYSREPO" = true ]; then
            ./configure --with-proto --with-sysrepo --without-internal-rpc --without-cli --without-bmv2 "CXXFLAGS=-O0 -g"
        else
            ./configure --with-proto --without-internal-rpc --without-cli --without-bmv2 "CXXFLAGS=-O0 -g"
        fi
    else
        if [ "$SYSREPO" = true ]; then
            ./configure --with-proto --with-sysrepo --without-internal-rpc --without-cli --without-bmv2
        else
            ./configure --with-proto --without-internal-rpc --without-cli --without-bmv2
        fi
    fi
    make -j${NUM_CORES}
    sudo make install
    sudo ldconfig
    make clean
}

# Install behavioral model
function do_bmv2 {
    # Install dependencies
    if [ "$P4_RUNTIME" = false ]; then
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
    if [ "$DEBUG_FLAGS" = true ] && [ "$P4_RUNTIME" = true ]; then
        ./configure --with-pi --with-thrift --with-nanomsg --enable-debugger --disable-elogger "CXXFLAGS=-O0 -g"
    elif [ "$DEBUG_FLAGS" = true ] && [ "$P4_RUNTIME" = false ]; then
        ./configure --with-thrift --with-nanomsg --enable-debugger --enable-elogger "CXXFLAGS=-O0 -g"
    elif [ "$DEBUG_FLAGS" = false ] && [ "$P4_RUNTIME" = true ]; then
        ./configure --with-pi --without-nanomsg --disable-elogger --disable-logging-macros 'CFLAGS=-g -O2' 'CXXFLAGS=-g -O2'
    else
        ./configure --without-nanomsg --disable-elogger --disable-logging-macros 'CFLAGS=-g -O2' 'CXXFLAGS=-g -O2'
    fi
    make -j${NUM_CORES}
    sudo make install
    sudo ldconfig

    # Build simple_switch_grpc
    if [ "$P4_RUNTIME" = true ]; then
        cd targets/simple_switch_grpc
        ./autogen.sh
        if [ "$DEBUG_FLAGS" = true ]; then
            if [ "$SYSREPO" = true ]; then
                ./configure --with-sysrepo --with-thrift "CXXFLAGS=-O0 -g"
            else
                ./configure --with-thrift "CXXFLAGS=-O0 -g"
            fi
        else
            if [ "$SYSREPO" = true ]; then
                ./configure --with-sysrepo --with-thrift
            else
                ./configure --with-thrift
            fi
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
    if [ "$DEBUG_FLAGS" = true ]; then
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
}

# Install ptf
function do_ptf {
    # Clone source
    cd ${BUILD_DIR}
    if [ ! -d ptf ]; then
        git clone https://github.com/p4lang/ptf.git ptf
    fi
    cd ptf
    git pull origin main

    # Build ptf
    sudo pip3 install .
    #sudo python3 setup.py install
}

# Install mininet
function do_mininet {
    # Clone source
    cd $HOME
    git clone https://github.com/mininet/mininet mininet
    cd mininet

    # Build mininet
    sudo PYTHON=python3 ./util/install.sh -nwv
}

# Install FRRouting
function do_frrouting {
    # Install dependencies
    do_frrouting_deps

    # Clone source
    cd ${BUILD_DIR}
    if [ ! -d frr ]; then
        git clone https://github.com/FRRouting/frr.git frr
    fi
    cd frr
    git checkout ${FRROUTING_COMMIT}

    # Build FRRouting
    ./bootstrap.sh
    ./configure --enable-fpm --enable-protobuf --enable-multipath=8
    make -j${NUM_CORES}
    sudo make install
    sudo ldconfig
}

# Install p4-utils
function do_p4-utils {
    # Clone source
    cd ${BUILD_DIR}
    if [ ! -d p4-utils ]; then
        git clone https://github.com/nsg-ethz/p4-utils.git p4-utils
    fi
    cd p4-utils

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
}

# Install Sphinx and ReadtheDocs
function do_sphinx {
    sudo apt-get install python3-sphinx
    sudo pip3 install sphinx-rtd-theme
}

##########
# Install 
##########

# p4c depends on protobuf to compile p4runtime info files.
do_protobuf
if [ "$P4_RUNTIME" = true ]; then
    do_grpc
    do_bmv2_deps
    if [ "$SYSREPO" = true ]; then
        do_sysrepo_libyang
    fi
    do_PI
fi
do_bmv2
do_p4c
do_ptf
do_mininet

# Mininet installs Python2 which becomes the system default binary.
# This sets again Python3 as the system default binary.
sudo ln -sf $(which python3) /usr/bin/python
sudo ln -sf $(which pip3) /usr/bin/pip

if [ "$FRROUTING" = true ]; then
    do_frrouting
fi

do_p4-utils
do_p4-learning

# last fixes
site_packages_fix
google_module_fix

if [ "$DOCUMENTATION" = true ]; then
    do_sphinx
fi

echo "Installation complete!"
