import pickle
import socket

from p4utils.utils.task_scheduler import *

kwargs = {
    'exe': send_udp_flow,
    'start': 0,
    'duration': 10
}

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
    
    def send(self, obj):
        """
        Send an object to the server.

        Arguments:
            obj : serializable object to send to the server
                  using Pickle
        """
        # Serialize object
        bin_data = pickle.dumps(obj)
        # Connect socket
        self.socket.connect(self.unix_socket_file)
        self.socket.sendall(bin_data)
        
    def close(self):
        """
        Close the socket.
        """
        self.socket.close()

if __name__ == '__main__':

    ts = TaskClient('/tmp/ciao')
    ts.send(kwargs)
    ts.close()