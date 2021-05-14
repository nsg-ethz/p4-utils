import pickle
import socket

from p4utils.utils.task_scheduler import *


class TaskClient:
    """
    Task scheduler client which communicates with servers.
    """
    def __init__(self, unix_socket_file):
        """
        Attributes:
            unix_socket_file (string): path to the file used by the Unix socket
        """
        # Unix socket file
        self.unix_socket_file = unix_socket_file
        # Blocking server socket
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.setblocking(True)
    
    def send(self, obj, retry=False):
        """
        Send an object to the server and close connection.

        Arguments:
            obj         : serializable object to send to the server
                          using Pickle
            retry (bool): whether to attempt a reconnection upon failure
        """
        self._send(obj, retry=retry)
        self._close()

    def _send(self, obj, retry=False):
        """
        Send an object to the server.

        Arguments:
            obj : serializable object to send to the server
                  using Pickle
        """
        # Serialize object
        bin_data = pickle.dumps(obj)
        # Connect socket
        while True:
            try:
                self.socket.connect(self.unix_socket_file)
                break
            except Exception as e:
                if not retry:
                    raise e
                      
        self.socket.sendall(bin_data)      
        
    def _close(self):
        """
        Close the socket.
        """
        self.socket.close()