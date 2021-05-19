import os
import sys
import time
import types
import queue
import pickle
import socket
import signal
import shutil as sh
import threading as th
import subprocess as sp
import multiprocessing as mp


class Task:
    """
    Abstraction of a Task executed by the TaskScheduler.
    """
    def __init__(self, exe, *args, start=0, duration=0, **kwargs):
        """
        Attributes:
            exe             : executable to run (either a shell string 
                              command or a python function)
            args            : positional arguments for the passed function
            start (float)   : task absolute starting time (unix time)
            duration (float): task duration time in seconds (if duration is 
                              lower than or equal to 0, then the task has no 
                              time limitation)
            kwargs          : key-word arguments for the passed function
        """
        if start >= 0:
            self.start = start
        else:
            raise Exception('cannot have negative Unix time.')

        if duration > 0:
            self.duration = duration
        else:
            raise Exception('cannot have negative duration!')

        self.exe = exe
        self.args = args
        self.kwargs = kwargs

        # Process states
        self.started = False
        self.stopped = False

        # Spanning processes
        self.proc = None
        self.thread = None

    def is_alive(self):
        """
        Check whether the task is alive or not and
        update the task states.
        """
        if isinstance(self.proc, sp.Popen):
            alive = True if self.proc.poll() is None else False
        elif isinstance(self.proc, mp.Process):
            alive = self.proc.is_alive()
        return alive

    def _start(self):
        """
        Start the executable in a separate process and populate
        self.process with it.
        """
        # If it is a function
        if isinstance(self.exe, types.FunctionType):
            self.proc = mp.Process(target=self.exe,
                                   args=self.args,
                                   kwargs=self.kwargs)
            self.proc.start()
        # If it is a shell command
        elif isinstance(self.exe, str):
            self.exe = self.exe.split()
            self.proc = sp.Popen(self.exe,
                                 stdout=sp.DEVNULL,
                                 stderr=sp.DEVNULL)
        else:
            raise TypeError('{} is not a supported type.'.format(type(self.exe)))
    
    def _stop(self):
        """
        Stops the execution of the process.
        """
        # Check if the process is running
        if self.is_alive():
            # Kill process
            os.kill(self.proc.pid, signal.SIGKILL)

    def _run(self):
        """
        Start the process, wait for its end and then kill it.
        """
        # Wait for starting time
        time.sleep(max(0, self.start - time.time()))
        # Start process
        self._start()
        # If duration has been specified, wait and then stop.
        if self.duration > 0:
            # Wait for duration
            time.sleep(max(0, self.start + self.duration - time.time()))
            self._stop()

    def run(self):
        """
        Start a thread to control the execution of the task.
        """
        # Avoid zombie processes
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        # Run the thread in non-blocking mode
        self.thread = th.Thread(target=self._run, daemon=True)
        self.thread.start()

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
        # Server thread
        self.server = None

        # Queue of received tasks
        self.queue = queue.Queue()
        # List of tasks currently managed by the scheduler
        self.tasks = []

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

            # Get list from chunks
            bin_data = b''.join(chunks)
            tasks_list = pickle.loads(bin_data)

            # Iterate over tasks
            for args, kwargs in tasks_list:
                # Initialize a new task
                task = Task(*args, **kwargs)
                # Enqueue task
                self.queue.put(task)

    def scheduler_loop(self):
        """
        Start the tasks and stop them when it is required.
        """
        while True:
                # Try to get task from the queue and wait
                # for a minute 
                try:
                    task = self.queue.get(60)
                    self.tasks.append(task)
                except queue.Empty:
                    pass

                # List of stopped tasks to remove
                stopped_tasks = []
                
                for task in self.tasks:
                    # Identify new tasks
                    if not task.started:
                        # Update state
                        task.started = True
                        # Run
                        task.run()
                    # Identify dead tasks
                    elif task.started and not task.is_alive():
                        # Update state
                        task.stopped = True

                    # Identify stopped tasks
                    if task.stopped:
                        stopped_tasks.append(task)
                
                # Remove old stopped tasks from the list
                for task in stopped_tasks:
                    self.tasks.remove(task)

    def start(self):
        """
        Start the server.
        """
        # Start server to listen for tasks
        self.server = th.Thread(target=self.server_loop, daemon=True)
        self.server.start()
        # Start scheduler
        self.scheduler_loop()


if __name__ == '__main__':

    if len(sys.argv) != 2:
        raise Exception('wrong execution call.')

    ts = TaskScheduler(sys.argv[1])