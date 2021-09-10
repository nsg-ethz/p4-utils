import time
import socket
import math

# min udp packet size
minSizeUDP = 42
maxUDPSize = 1400
DEFAULT_BATCH_SIZE = 1


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


def send_udp_flow(dst="10.0.1.2", sport=5000, dport=5001, tos=0, rate='10M', d=10, 
                  packet_size=maxUDPSize, batch_size=DEFAULT_BATCH_SIZE, out_file="send.txt", **kwargs):
    """Udp sending function that keeps a constant rate and logs sent packets to a file.
    Args:
        dst (str, optional): [description]. Defaults to "10.0.1.2".
        sport (int, optional): [description]. Defaults to 5000.
        dport (int, optional): [description]. Defaults to 5001.
        tos (int, optional): [description]. Defaults to 0.        
        rate (str, optional): [description]. Defaults to '10M'.
        d (int, optional): [description]. Defaults to 10.
        packet_size ([type], optional): [description]. Defaults to maxUDPSize.
        batch_size (int, optional): [description]. Defaults to 5.
        out_file (str, optional): [description]. Defaults to "send.txt".
    """

    sport = int(sport)
    dport = int(dport)
    packet_size = int(packet_size)
    tos = int(tos)
    if packet_size > maxUDPSize:
        packet_size = maxUDPSize

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_IP, socket.IP_TOS, tos)
    s.bind(('', sport))

    rate = int(setSizeToInt(rate)/8)
    totalTime = float(d)

    # we use 17 to correct a bit the bw
    packet = b"A" * int((packet_size - 17))
    seq = 0
    output_log = open(out_file, "w")

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
                    output_log.write("{}\n".format(seq))
                    output_log.flush()
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
        output_log.close()


def recv_udp_flow(src, dport, out_file="recv.txt"):
    """Receiving function. It blocks reciving packets and store the first
       4 bytes into out file

    Args:
        src ([str]): source ip address to listen
        dport ([int]): port to listen
        out_file ([str]): out file to log
    """

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("", dport))
    output_log = open(out_file, "w")
    c = 0
    try:
        while True:
            data, address = s.recvfrom(2048)
            # only accept packets from the expected source
            if address[0] == src:
                c += 1
                output_log.write("{}\n".format(
                    int.from_bytes(data[:4], 'big')))
                output_log.flush()

    except:
        print("Packets received {}".format(c))
        s.close()
        output_log.close()


def save_sequences(sequences, file_name):
    """Helper function to save sequence numbers in bulk

    Args:
        sequences ([list]): list of sequences
        file_name ([str]):  output file
    """

    with open(file_name, "w") as f:
        for seq in sequences:
            f.write("{}\n".format(seq))
