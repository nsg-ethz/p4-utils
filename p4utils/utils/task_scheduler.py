import os
import sys
import time
import types
import queue
import pickle
import socket
import signal
import shlex
import shutil as sh
import threading as th
import subprocess as sp
import multiprocessing as mp
from enum import IntEnum


import p4utils.utils.task_scheduler
from p4utils.utils.helper import WrapFunc


class ProcessType(IntEnum):
    """Enum class that defines task types."""
    MULTIPROC = 0
    SUBPROC = 1


class Task:
    """Abstraction of a Task executed by the TaskServer.

    Args:
        exe (str or types.FunctionType)  : executable to run (either a shell string 
                                           command or a python function)
        start (int or float)   : task absolute starting time (Unix time).
        duration (int or float): task duration time in seconds (if duration is 
                                 lower than or equal to 0, then the task has no 
                                 time limitation)
        args (tuple or list)   : positional arguments for the passed function
        kwargs (dict)          : key-word arguments for the passed function
    """

    def __init__(self, exe, start=0, duration=0, args=(), kwargs={}):
        # Sanity checks
        if isinstance(exe, str):
            self.type = ProcessType.SUBPROC
            # exe is the string to execute
            self.exe = exe
        elif isinstance(exe, types.FunctionType):
            self.type = ProcessType.MULTIPROC
            # exe is a WrapFunc object
            self.exe = WrapFunc(exe)
        else:
            raise TypeError(
                'cannot execute an object of type {}!'.format(type(exe)))

        assert isinstance(exe, str) or isinstance(exe, types.FunctionType)
        assert isinstance(start, int) or isinstance(start, float)
        assert (isinstance(duration, int) or isinstance(
            duration, float)) and duration >= 0

        # Other task parameters
        self.startTime = start
        self.duration = duration
        self.args = tuple(args)
        self.kwargs = kwargs

        # Scheduler thread
        self.thread = None
        # Subprocess spawn
        self.proc = None

        # Communication queue
        self.queue = None

    def __repr__(self):
        return 'Task({}, {})'.format(self.exe,
                                     {'start': self.startTime,
                                      'duration': self.duration,
                                      'args': self.args,
                                      'kwargs': self.kwargs})

    @property
    def pid(self):
        """Returns the PID of the task.

        Returns:
            int: PID of the running task.

        Note:
            Returns **None** if the task has not been started yet.
        """
        if self.proc is not None:
            return self.proc.pid
        else:
            return None

    @property
    def exitcode(self):
        """Returns the exit code of the task.

        Returns:
            int: exit code of the task.

        Note:
            Returns **None** if the process has not yet terminated.
        """
        if self.proc is not None:
            if self.type == ProcessType.MULTIPROC:
                return self._exitcode_mp()
            else:
                return self._exitcode_sp()
        else:
            return None

    def setComm(self, q):
        """Set communication queue for the Task. The task
        will communicate its state putting items in the queue.

        Args:
            id (int)            : task id used to communicate
            q (queue.Queue)     : communication queue
        """
        # Sanity checks
        assert isinstance(q, queue.Queue)
        # Update communication parameters
        self.queue = q

    def schedule(self, cond=None):
        """Starts a new thread that orchestrate the execution
        of the task and stops it if duration expires.

        Args:
            cond (threading.Condition): condition to notify when self.thread is completed
        """
        # Create and start scheduling thread
        self.thread = th.Thread(target=self._schedule, args=(cond,))
        self.thread.start()

    def start(self):
        """Starts the executable in a separate process."""
        if self.type == ProcessType.MULTIPROC:
            self._start_mp()
        else:
            self._start_sp()
        # Log
        self._send_msg('\n{}: task started with PID {}!\n'
                       '{}\n'.format(time.ctime(),
                                     self.pid,
                                     self))

    def stop(self):
        """Stops the task using SIGTERM and, if it fails, SIGKILL."""
        if self.type == ProcessType.MULTIPROC:
            self._stop_mp()
        else:
            self._stop_sp()
        # Log
        self._send_msg(
            '\n{}: task with PID {} stopped!\n'.format(
                time.ctime(),
                self.pid))

    def join(self, timeout=None):
        """Joins the subprocess."""
        if self.type == ProcessType.MULTIPROC:
            self._join_mp(timeout)
        else:
            self._join_sp(timeout)

    def is_alive(self):
        """Returns whether the process is alive.

        Returns:
            bool: **True** if the process is alive, **False** otherwise.
        """
        if self.proc is not None:
            if self.type == ProcessType.MULTIPROC:
                return self.proc.is_alive()
            else:
                return True if self.proc.poll() is None else False
        else:
            return False

    def _send_msg(self, msg, quiet=True):
        """Enqueues a message in self.queue. In order to work,
        :py:meth:`Task.setComm()` must have been called previously.

        Args:
            msg (str)   : message to send to the logger
            quiet (bool): do not raise exception if :py:meth:`Task.setComm()`
                          has not been called previously
        """
        if quiet:
            if self.queue is not None:
                self.queue.put(msg)
        else:
            self.queue.put(msg)

    def _schedule(self, cond=None):
        """Starts the execution of the task and stops it if duration expires.

        Args:
            cond (threading.Condition): condition to notify when this function
                                        is completed
        """
        # Print a warning if sleep time is negatative.
        if time.time() > self.startTime:
            # log it also
            self._send_msg("Schedule time wait: {}".format(
                self.startTime - time.time()))
            self._send_msg(
                "Warning: Invalid start time in the past. This event won't be scheduled. Consider rerunning the experiment with more time margin")
        else:
            self._send_msg("Schedule time wait: {}".format(
                self.startTime - time.time()))

        # Wait for starting time
        time.sleep(max(0, self.startTime - time.time()))
        # Start process
        self.start()
        # If duration has been specified, wait and then stop.
        if self.duration > 0:
            # Wait for duration
            self.join(max(0, self.startTime + self.duration - time.time()))
            # Stop process
            self.stop()
        # Join process
        self.join()
        # If condition is provided
        if cond is not None:
            with cond:
                # Notify
                cond.notify()
        # Log
        self._send_msg(
            '\n{}: task with PID {} exited with code {}.\n'.format(
                time.ctime(),
                self.pid, self.exitcode))

    def _start_mp(self):
        """Starts multiprocess."""
        # Create and start process
        self.proc = mp.Process(target=self.exe.unwrap(),
                               args=self.args,
                               kwargs=self.kwargs,
                               daemon=True)
        self.proc.start()

    def _stop_mp(self):
        """Stops multiprocess."""
        # Terminate process using SIGTERM
        self.proc.terminate()
        # Wait up to 1 second for the process to terminate
        self.proc.join(1)
        # Check if the process is alive
        if self.proc.is_alive():
            # Send SIGKILL
            try:
                os.kill(self.pid, signal.SIGKILL)
            except:
                pass
            # Join process
            self.proc.join()

    def _join_mp(self, timeout=None):
        """Joins multiprocess."""
        self.proc.join(timeout)

    def _exitcode_mp(self):
        """Gets multiprocess return code."""
        return self.proc.exitcode

    def _start_sp(self):
        """Starts subprocess."""
        self.proc = sp.Popen(shlex.split(self.exe),
                             stdout=sp.DEVNULL,
                             stderr=sp.DEVNULL)

    def _stop_sp(self):
        """Stops subprocess."""
        # Terminate process using SIGTERM
        self.proc.terminate()
        # Wait up to 1 second for the process to terminate
        try:
            self.proc.wait(1)
        except sp.TimeoutExpired:
            # Send SIGKILL
            self.proc.kill()
            # Join process
            self.proc.wait()

    def _join_sp(self, timeout=None):
        """Joins subprocess."""
        try:
            self.proc.wait(timeout)
        except sp.TimeoutExpired:
            return

    def _exitcode_sp(self):
        """Gets subprocess return code."""
        return self.proc.returncode


class TaskClient:
    """Task scheduler client which communicates with servers.

    Args:
        unix_socket_file (str): path to the file used by the Unix socket
    """

    def __init__(self, unix_socket_file):
        # Sanity check
        assert isinstance(unix_socket_file, str)
        # Unix socket file
        self.unix_socket_file = unix_socket_file

    def send(self, tasks, retry=False):
        """Send an object to the server and close connection.

        Args:
            tasks (list or tuple): list or tuple of py:class:`Task` objects to execute
            retry (bool)         : whether to attempt a reconnection upon failure
        """
        # Sanity checks
        assert isinstance(tasks, list) or isinstance(tasks, tuple)
        for task in tasks:
            assert isinstance(task, Task)

        # Create client socket
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        # Set blocking mode
        s.setblocking(True)
        # Serialize object
        bin_data = pickle.dumps(tasks)
        # Connect socket
        while True:
            try:
                s.connect(self.unix_socket_file)
                break
            except Exception as e:
                if not retry:
                    raise e
        # Send data
        s.sendall(bin_data)
        # Close socket
        s.close()


class TaskServer:
    """Task scheduler server which runs on the Mininet nodes.

    Args:
        unix_socket_file (string): path to the file used by the Unix socket
    """

    def __init__(self, unix_socket_file):
        # Sanity check
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
        # Main threads
        self.server_start_loop = None
        self.server_join_loop = None
        self.scheduler_join_loop = None

        # Queue of received tasks
        self.recv_tasks = queue.Queue()
        # Log queue
        self.logs = queue.Queue()

        # List of connection threads
        self.conn_threads = []
        # Closed connection condition
        self.conn_close_cond = th.Condition()

        # List of scheduled tasks
        self.sched_tasks = []
        # Scheduling completed
        self.sched_completed_cond = th.Condition()

        # Start server
        self._start()

    def _start(self):
        """Starts TaskServer."""
        self.server_join_loop = th.Thread(
            target=self._server_join_loop, daemon=True)
        self.server_start_loop = th.Thread(
            target=self._server_start_loop, daemon=True)
        self.scheduler_join_loop = th.Thread(
            target=self._scheduler_join_loop, daemon=True)
        self.server_join_loop.start()
        self.scheduler_join_loop.start()
        self.server_start_loop.start()

        # Print logs
        while True:
            print(self.logs.get())

    def _server_start_loop(self):
        """Accepts simultaneous connections in different threads
        and downloads Tasks from client."""
        # Listen for connections
        self.socket.listen()

        while True:
            # Accept connection
            conn, _ = self.socket.accept()
            # Create thread
            thread = th.Thread(target=self._serve, args=(conn,))
            # Start the thread
            thread.start()
            # Append safely thread to self.conn_threads
            with self.conn_close_cond:
                self.conn_threads.append(thread)
            # Log
            self.logs.put(
                '\n{}: new connection ({}) opened!\n'.format(
                    time.ctime(),
                    thread.ident))

    def _server_join_loop(self):
        """Joins completed threads."""
        with self.conn_close_cond:
            while True:
                # Wait for a connection thread to finish
                self.conn_close_cond.wait()
                # List of completed threads
                completed_threads = []
                # Iterate over connection threads
                for thread in self.conn_threads:
                    # Check for completed threads
                    if not thread.is_alive():
                        # Join completed thread
                        thread.join()
                        # Add to the list of completed threads
                        completed_threads.append(thread)
                        # Log
                        self.logs.put(
                            '\n{}: connection {} closed!\n'.format(
                                time.ctime(),
                                thread.ident))
                # Iterate over completed threads
                for thread in completed_threads:
                    # Remove joined thread
                    self.conn_threads.remove(thread)

    def _serve(self, conn):
        """Manages a single connection and starts the received Tasks."""
        # List of chunks
        chunks = []

        # Retrieve chunks from connection
        while True:
            chunk = conn.recv(4096)
            if len(chunk) > 0:
                chunks.append(chunk)
            else:
                conn.close()
                break

        # Get list from chunks
        bin_data = b''.join(chunks)
        # Avoid unpickling exceptions
        try:
            # Unpickle data
            tasks = pickle.loads(bin_data)
        except Exception as e:
            # Log
            self.logs.put('\n{}: cannot unpickle the tasks!\n'
                          '{}\n'.format(time.ctime(), repr(e)))
        else:
            # Sanity check
            if isinstance(tasks, tuple) or isinstance(tasks, list):
                for task in tasks:
                    # Sanity check
                    if isinstance(task, p4utils.utils.task_scheduler.Task):
                        # Set communication
                        task.setComm(self.logs)
                        # Start task scheduler
                        task.schedule(self.sched_completed_cond)
                        # Append safely thread to self.sched_tasks
                        with self.sched_completed_cond:
                            self.sched_tasks.append(task)
                        # Log
                        self.logs.put(
                            '\n{}: task received!\n'
                            '{}\n'
                            'Scheduler {} started!\n'.format(
                                time.ctime(),
                                task, task.thread.ident))
                    else:
                        # Log
                        self.logs.put(
                            '\n{}: malformed task received!\n'.format(
                                time.ctime()))
            else:
                self.logs.put('\n{}: malformed data received!\n')
        finally:
            with self.conn_close_cond:
                # Notify that the connection closed
                self.conn_close_cond.notify()

    def _scheduler_join_loop(self):
        """Joins completed scheduling threads."""
        with self.sched_completed_cond:
            while True:
                # Wait for a schefuling thread to finish
                self.sched_completed_cond.wait()
                # List of completed threads
                completed_tasks = []
                # Iterate over connection threads
                for task in self.sched_tasks:
                    # Check for completed threads
                    if not task.thread.is_alive():
                        # Join completed thread
                        task.thread.join()
                        # Add to the list of completed threads
                        completed_tasks.append(task)
                        # Log
                        self.logs.put(
                            '\n{}: scheduler {} closed!\n'.format(
                                time.ctime(),
                                task.thread.ident))
                # Iterate over completed threads
                for task in completed_tasks:
                    # Remove joined thread
                    self.sched_tasks.remove(task)


if __name__ == '__main__':

    if len(sys.argv) != 2:
        raise Exception('wrong execution call.')

    ts = TaskServer(sys.argv[1])
