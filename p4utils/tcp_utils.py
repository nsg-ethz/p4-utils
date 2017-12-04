import socket


class Socket(object):

    def __init__(self):

        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def send(self,msg):
        self._s.send(msg)


    def close(self):
        self._s.close()

    def recv(self, conn):
        return conn.recv(4096)


class Sender(Socket):

    def __init__(self):
        super(Sender, self).__init__()

    def connect(self,ip, port):
        self._s.connect((ip, port))

class Receiver(Socket):

    def __init__(self, port):
        super(Receiver, self).__init__()

        self._port = port
        self.bind(port)
        self.conn = ""


    def bind(self,port):

        self._s.bind(('', port))


    def listen(self):
        self._s.listen(1)
        conn, addr =  self._s.accept()
        self.conn = conn
        
    def recv(self):
        return super(Receiver, self).recv(self.conn)


    def close(self):
        if self.conn:
            self.conn.close()
        super(Receiver, self).close()
