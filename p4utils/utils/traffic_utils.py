import math
import time
import socket


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


def send_udp_flow(dst="10.0.0.2", sport=5000, dport=5001, tos=0, rate='10M', duration=0, 
                  packet_size=1400, batch_size=1, **kwargs):
    """
    Udp sending function that keeps a constant rate and logs sent packets to a file.
    Args:
        dst (str, optional): [description]. Defaults to "10.0.1.2".
        sport (int, optional): [description]. Defaults to 5000.
        dport (int, optional): [description]. Defaults to 5001.
        tos (int, optional): [description]. Defaults to 0.        
        rate (str, optional): [description]. Defaults to '10M'.
        duration (int, optional): [description]. Defaults to 0, i.e. no time limit.
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
        while True: 
            
            # If a finite duration is given
            if totalTime > 0:
                if time.time() - startTime >= totalTime:
                    break

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
    dport = int(dport)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("", dport))
    try:
        while True:
            data, address = s.recvfrom(2048)
    except:
        print("Packets received {}".format(c))
        s.close()
