#!/bin/bash

# Author: Edgar Costa Molero
# Email: cedgar@ethz.ch

# This scripts installs all the required software to learn and prototype P4
# programs using the p4lang software suite. 

# Furthermore, we install p4-utils and p4-learning and ffr routers.

# This install script has only been tested with the following systems:
# Ubuntu 20.04
# Ubuntu 22.04

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

# p4-utils branch 
# TODO: improve this in the future
P4_UTILS_BRANCH="update-p4-tools"

# Software versions

# PI dependencies from https://github.com/p4lang/PI#dependencies

# protobuf
PROTOBUF_VER="3.20.3"
PROTOBUF_COMMIT="v${PROTOBUF_VER}"

# from https://github.com/p4lang/PI#dependencies
GRPC_VER="1.43.2"
GRPC_COMMIT="tags/v${GRPC_VER}"

LIBYANG_VER="1.0.225"
LIBYANG_COMMIT="v${LIBYANG_VER}"

PI_COMMIT="6d0f3d6c08d595f65c7d96fd852d9e0c308a6f30"    # Aug 21 2023
BMV2_COMMIT="d064664b58b8919782a4c60a3b9dbe62a835ac74"  # Sep 8 2023
P4C_COMMIT="66eefdea4c00e3fbcc4723bd9c8a8164e7288724"   # Sep 13 2023

FRROUTING_COMMIT="18f209926fb659790926b82dd4e30727311d22aa" # Mar 25 2021


function do_os_message() {
    1>&2 echo "Found ID ${ID} and VERSION_ID ${VERSION_ID} in /etc/os-release"
    1>&2 echo "This script only supports these:"
    1>&2 echo "    ID ubuntu, VERSION_ID in 20.04 22.04"
    1>&2 echo ""
    1>&2 echo "Proceed installing at your own risk."
}

function do_init_checks {
    if [ ! -r /etc/os-release ]
    then
        1>&2 echo "No file /etc/os-release.  Cannot determine what OS this is."
        do_os_message
        exit 1
    fi
    source /etc/os-release

    supported_distribution=0
    if [ "${ID}" = "ubuntu" ]
    then
        case "${VERSION_ID}" in
        18.04)
            supported_distribution=1
            ;;
        20.04)
            supported_distribution=1
            ;;
        22.04)
            supported_distribution=1
            ;;
        esac
    fi

    if [ ${supported_distribution} -eq 1 ]
    then
        echo "Found supported ID ${ID} and VERSION_ID ${VERSION_ID} in /etc/os-release"
    else
        do_os_message
        exit 1
    fi
}

function do_global_setup {
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
    zip \
    unzip

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
    sudo apt-get -y --no-install-recommends install iperf3
    #cd /tmp
    #sudo apt-get remove  -y --no-install-recommends iperf3 libiperf0
    #wget https://iperf.fr/download/ubuntu/libiperf0_3.1.3-1_amd64.deb
    #wget https://iperf.fr/download/ubuntu/iperf3_3.1.3-1_amd64.deb
    #sudo dpkg -i libiperf0_3.1.3-1_amd64.deb iperf3_3.1.3-1_amd64.deb
    #rm libiperf0_3.1.3-1_amd64.deb iperf3_3.1.3-1_amd64.deb

    # Configure tmux
    wget -O ~/.tmux.conf https://raw.githubusercontent.com/nsg-ethz/p4-utils/${P4_UTILS_BRANCH}/install-tools/conf_files/tmux.conf
}

#### PROTOBUF FUNCTIONS
function do_protobuf {
    echo "Uninstalling Ubuntu python3-protobuf if present"
    sudo apt-get purge -y python3-protobuf || echo "Failed removing protobuf"

    # install python
    sudo pip install protobuf==${PROTOBUF_VER}

    cd ${BUILD_DIR}

    # install from source
    # Clone source
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

    echo "end install protobuf:"
}

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

    mkdir -p cmake/build
    cd cmake/build
    cmake ../..
    make
    sudo make install 
    
    unset LDFLAGS

    echo "grpc installed"
}

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
    if [ ! -d build ]; then
        mkdir build
    else
        rm -R build
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

    echo "PI Installed"
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
    zlib1g-dev \
    lld \
    pkg-config \
    ccache

    sudo pip install scapy==2.5.0
    sudo pip install ply
    sudo pip install pyroute2
    #sudo pip install ptf
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

    # TODO check if this can be done
    rm -rf build/

    echo "p4c installed"
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

# Install mininet
function do_mininet_no_python2 {
    # mininet installing process forces python2 to be installed
    # we want to avoid this in ubuntu 20+
    # This patch helps us doing so
    # from https://github.com/jafingerhut/p4-guide/blob/d36766f2c50a2159e43dd843085fbbe416d23b33/bin/install-p4dev-v6.sh#L868
    MININET_COMMIT="5b1b376336e1c6330308e64ba41baac6976b6874"  # 2023-May-28
    git clone https://github.com/mininet/mininet mininet
    cd mininet
    git checkout ${MININET_COMMIT}

    # patching mininet
    wget -O mininet.patch https://raw.githubusercontent.com/nsg-ethz/p4-utils/${P4_UTILS_BRANCH}/install-tools/conf_files/mininet.patch
    patch -p1 < "mininet.patch"

    # Build mininet
    sudo PYTHON=python3 ./util/install.sh -nwv

    echo "mininet installed"
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

function google_module_fix {
    curl -sSL https://raw.githubusercontent.com/nsg-ethz/p4-utils/${P4_UTILS_BRANCH}/install-tools/scripts/protoinitfix.py | sudo python3
}

###### MAIN ######

do_init_checks

# Print commands and exit on errors
set -xe

echo "------------------------------------------------------------"
echo "Time and disk space used before installation begins:"
set -x
date
df -h .
df -BM .

# Make the system passwordless
if [ ! -f /etc/sudoers.d/99_vm ]; then
    sudo bash -c "echo '${USER_NAME} ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/99_vm"
    sudo chmod 440 /etc/sudoers.d/99_vm
fi

# Create BUILD_DIR
mkdir -p ${BUILD_DIR}

# Set locale
sudo locale-gen en_US.UTF-8

# Update packages list
sudo apt-get update

# initial ubuntu packages and global installs
do_global_setup 

# Install P4 tools
do_protobuf

# runtime install
if [ "$P4_RUNTIME" = true ]; then
    do_grpc
    do_bmv2_deps
    if [ "$SYSREPO" = true ]; then
        do_sysrepo_libyang
    fi
    do_PI
fi

# python site packages fix
site_packages_fix

do_bmv2
do_p4c
do_ptf
do_mininet_no_python2

#
## Mininet installs Python2 which becomes the system default binary.
## This sets again Python3 as the system default binary.
#sudo ln -sf $(which python3) /usr/bin/python
#sudo ln -sf $(which pip3) /usr/bin/pip

#
if [ "$FRROUTING" = true ]; then
    do_frrouting
fi
#
do_p4-utils
do_p4-learning
#
## last fixes
site_packages_fix
google_module_fix
#
if [ "$DOCUMENTATION" = true ]; then
    do_sphinx
fi
#
#echo "Installation complete!"