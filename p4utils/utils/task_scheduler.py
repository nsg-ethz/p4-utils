import os
import sys
import math
import time
import types
import pickle
import socket
import shutil as sh
import threading as th
import subprocess as sp
import multiprocessing as mp


def setSizeToInt(size):
    """" Converts the sizes string notation to the corresponding integer
    (in bytes).  Input size can be given with the following
    magnitudes: B, K, M and G.
    """
    if isinstance(size, int):
        return size
    elif isinstance(size, float):
        return int(size)
    try:
        conversions = {'B': 1, 'K': 1e3, 'M': 1e6, 'G': 1e9}
        digits_list = list(range(48, 58)) + [ord(".")]
        magnitude = chr(
            sum([ord(x) if (ord(x) not in digits_list) else 0 for x in size]))
        digit = float(size[0:(size.index(magnitude))])
        magnitude = conversions[magnitude]
        return int(magnitude*digit)
    except:
        print("Conversion Fail")
        return 0


def send_udp_flow(dst="10.0.0.2", sport=5000, dport=5001, tos=0, rate='10M', duration=10, 
                  packet_size=1400, batch_size=1, **kwargs):
    """
    Udp sending function that keeps a constant rate and logs sent packets to a file.
    Args:
        dst (str, optional): [description]. Defaults to "10.0.1.2".
        sport (int, optional): [description]. Defaults to 5000.
        dport (int, optional): [description]. Defaults to 5001.
        tos (int, optional): [description]. Defaults to 0.        
        rate (str, optional): [description]. Defaults to '10M'.
        duration (int, optional): [description]. Defaults to 10.
        packet_size ([type], optional): [description]. Defaults to 1400.
        batch_size (int, optional): [description]. Defaults to 5.
    """

    sport = int(sport)
    dport = int(dport)
    packet_size = int(packet_size)
    tos = int(tos)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_IP, socket.IP_TOS, tos)
    s.bind(('', sport))

    rate = int(setSizeToInt(rate)/8)
    totalTime = float(duration)

    # we use 17 to correct a bit the bw
    packet = b"A" * int((packet_size - 17))
    seq = 0

    try:
        startTime = time.time()
        while (time.time() - startTime < totalTime):

            packets_to_send = rate/packet_size
            times = math.ceil((float(rate) / (packet_size))/batch_size)
            time_step = 1/times
            start = time.time()
            i = 0
            packets_sent = 0
            # batches of 1 sec
            while packets_sent < packets_to_send:
                for _ in range(batch_size):
                    s.sendto(seq.to_bytes(4, byteorder='big') +
                             packet, (dst, dport))
                    # sequence_numbers.append(seq)
                    packets_sent += 1
                    seq += 1

                i += 1
                next_send_time = start + (i * time_step)
                time.sleep(max(0, next_send_time - time.time()))
                # return
            time.sleep(max(0, 1-(time.time()-start)))

    finally:
        s.close()


def recv_udp_flow(src, dport):
    """Receiving function. It blocks reciving packets and store the first
       4 bytes into out file

    Args:
        src ([str]): source ip address to listen
        dport ([int]): port to listen
    """

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("", dport))
    try:
        while True:
            data, address = s.recvfrom(2048)
    except:
        print("Packets received {}".format(c))
        s.close()


class Task:
    """
    Abstraction of a Task executed by the TaskScheduler.
    """
    def __init__(self, exe, *args, start=0, duration=0, **kwargs):
        """
        Attributes:
            exe           : executable to run (either a shell string 
                            command or a python function)
            args          : positional arguments for the passed function
            start (int)   : task starting time with respect to the current
                            time in seconds (i.e. 0 means start as soon as
                            you receive it)
            duration (int): task duration time in seconds (if duration is 
                            lower than or equal to 0, then the task has no 
                            time limitation)
            kwargs        : key-word arguments for the passed function
        """
        if start >= 0:
            self.start = start + time.time()
        else:
            raise Exception('cannot start tasks in the past!')

        if duration > 0:
            self.stop = self.start + duration
        else:
            self.stop = None

        self.exe = exe
        self.args = args
        self.kwargs = kwargs
        self.running = False
        self.proc = None

    def to_start(self):
        """
        Whether the task has to be started or not.
        """
        return time.time() >= self.start

    def to_stop(self):
        """
        Whether the task has to be stopped or not.
        """
        if self.stop is not None:
            return time.time() >= self.stop
        else:
            return False

    def run(self):
        """
        Run the executable in a separate process and populate
        self.process with it.
        """
        # If it is a function
        if isinstance(self.exe, types.FunctionType):
            self.proc = mp.Process(target=self.exe,
                                   args=self.args,
                                   kwargs=self.kwargs)
            self.proc.start()
            self.running = True
        # If it is a shell command
        elif isinstance(self.exe, str):
            self.exe = self.exe.split()
            self.proc = sp.Popen(self.exe,
                                 stdout=sp.DEVNULL,
                                 stderr=sp.DEVNULL)
            self.running = True
        else:
            raise TypeError('{} is not a supported type.'.format(type(self.exe)))
    
    def kill(self):
        """
        Stops the execution of the process.
        """
        self.proc.terminate()
        self.running = False


class TaskScheduler:
    """
    Task scheduler server which runs on the Mininet nodes.
    """

    def __init__(self, unix_socket_file):
        """
        Attributes:
            unix_socket_file (string): path to the file used by the Unix socket
        """
        if os.path.exists(unix_socket_file):
            if os.path.isdir(unix_socket_file):
                sh.rmtree(unix_socket_file)
            else:
                os.remove(unix_socket_file)

        # Unix socket file
        self.unix_socket_file = unix_socket_file
        # Blocking server socket
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.setblocking(True)
        # Bind socket
        self.socket.bind(unix_socket_file)

        # List of tasks
        self.scheduled = []
        # Lock on list of tasks
        self.lock = th.Lock()
        # Scheduler thread
        self.scheduler = None

        # Start server
        self.start()

    def server_loop(self):
        """
        Enqueue the tasks received via the Unix Domain Socket.
        """
        self.socket.listen()
        while True:
            # Accept connection
            conn, addr = self.socket.accept()
            chunks = []
            # Retrieve chunks
            while True:
                chunk = conn.recv(4096)
                if len(chunk) > 0:
                    chunks.append(chunk)
                else:
                    conn.close()
                    break
            # Get kwargs from chunks
            bin_data = b''.join(chunks)
            args, kwargs = pickle.loads(bin_data)
            # Initialize a new task
            task = Task(*args, **kwargs)
            # Schedule task
            with self.lock:
                self.scheduled.append(task)

    def scheduler_loop(self):
        """
        Start the tasks and stop them when it is required.
        """
        while True:
            stopped_tasks = []

            with self.lock:
                for task in self.scheduled:
                    if task.running:
                        if task.to_stop():
                            task.kill()
                            stopped_tasks.append(task)
                    else:
                        if task.to_start():
                            task.run()

                for task in stopped_tasks:
                    self.scheduled.remove(task)     

    def start(self):
        """
        Start the server.
        """
        self.scheduler = th.Thread(target=self.scheduler_loop, daemon=True)
        self.scheduler.start()
        self.server_loop()


if __name__ == '__main__':

    if len(sys.argv) != 2:
        raise Exception('wrong execution call.')

    ts = TaskScheduler(sys.argv[1])