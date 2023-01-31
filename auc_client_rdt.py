# Author: Isabella Samuelsson
# Date: 10/7/22
import os
import sys
from datetime import datetime
from random import randint
from socket import *
from interruptingcow import timeout
"""
Auction client class. If you are the first to connect to the server you will be connected as a seller client, if not you 
will be connected as a buyer client. Bids must be an integer greater than zero. Once the auction has concluded the seller 
will initiate reliable data transfer to transfer the file item tosend.txt to the winning buyer.

Seller Client: Once connected you will be prompted to enter auction information. This includes Auction Type: 1 
for a first price auction and 2 for a second price auction, Minimum Bid price: non-negative integer, Number of Bidders: 
non-negative integer less than 10 and Item Name: string. If you enter invalid auction information you will be prompted 
for valid information before continuing. At the end of the auction your file item tosend.txt will be transferred to the 
winning buyer through rdt.

Buyer Client: Once connected you will be prompted to enter a bid. A bid should be a non-negative integer, if an invalid 
bid is given you will be prompted again. You will receive the file item received.txt through rdt.

Run example: python3 auc_client_rdt.py server_ip_address server_port_number transfer_port_number drop_rate
"""
class auc_client:
    # default server name and port
    serverName = "192.168.0.15"
    serverPort = 12345

    # Project 2:
    sendingPort = 12346             # specified sending port for rdt
    chunk_size = 2000
    loss_rate = 0                   # specified loss rate for rdt
    filename = "tosend.txt"         # filename of seller item
    timeout = 2
    initial_send = True             # if this is the first instance of msg send
    file_arr = []                   # received file buffer for winning buyer

    """ Initializes server name and port from run command arguments and starts the main() function."""
    def __init__(self):
        self.serverName = sys.argv[1]
        self.serverPort = int(sys.argv[2])
        self.sendingPort = int(sys.argv[3])

        if len(sys.argv) == 5:
            self.loss_rate = float(sys.argv[4])

        self.main()

    """ 
    Creates a connection to the auction server and at the end of the auction initiates file transfer for Seller 
    and Winning Buyer.
    - If you are the first to connect to the server you will be connected as a seller client, if not you will be 
    connected as a buyer client. 
    - If the client connects when the sever is busy setting up a seller connection or the server is busy handling 
    bidding the client will receive a "connect again later" message and the client will close the socket and exit. 
    """
    def main(self):
        clientSocket = socket(AF_INET, SOCK_STREAM)
        clientSocket.connect((self.serverName, self.serverPort))        # client connection

        client_status_msg = clientSocket.recv(1024).decode()
        if "connect again later" in client_status_msg:                  # if server sends a busy msg disconnect and exit
            print(client_status_msg)
            clientSocket.close()
            exit()
        if "Seller" in client_status_msg:                               # if client is a buyer prompt for auction info
            auc_info_msg = input(client_status_msg)
            clientSocket.send(auc_info_msg.encode())
            received_auc_info = clientSocket.recv(1024).decode()

            while "Invalid" in received_auc_info:                       # if invalid auction info given prompt again
                new_auc_info = input(received_auc_info)
                clientSocket.send(new_auc_info.encode())
                received_auc_info = clientSocket.recv(1024).decode()

            print(received_auc_info)

            auction_finished = clientSocket.recv(1024).decode()
            print(auction_finished)

            # Project2: Start sending item.
            if "Success" in auction_finished:
                clientSocket.send(str(self.sendingPort).encode())
                buyer_info = clientSocket.recv(1024).decode().split(" ")
                buyer_ip = buyer_info[0]
                buyer_port = buyer_info[1]
                buyer_port = int(buyer_port)
                self.send_item(buyer_ip, buyer_port)

        else:                                                           # if client is a seller wait for bid start
            print(client_status_msg)
            did_bid_start = clientSocket.recv(1024).decode()
            if "waiting" in did_bid_start:
                print(did_bid_start)
                did_bid_start = clientSocket.recv(1024).decode()

            bid = input(did_bid_start)                                  # at bid start prompt for bid
            clientSocket.send(bid.encode())
            received_bid = clientSocket.recv(1024).decode()

            while "Invalid" in received_bid:                            # if bid is invalid prompt again
                new_bid = input(received_bid)
                clientSocket.send(new_bid.encode())
                received_bid = clientSocket.recv(1024).decode()

            print(received_bid)

            auction_finished = clientSocket.recv(1024).decode()         # print auction result and disconnect
            print(auction_finished)

            # Project2: Start receiving item.
            if "won" in auction_finished:
                clientSocket.send(str(self.sendingPort).encode())
                seller_info = clientSocket.recv(1024).decode().split(" ")
                seller_ip = seller_info[0]
                seller_port = seller_info[1]
                seller_port = int(seller_port)
                self.recieve_item(seller_ip, seller_port)

        clientSocket.close()


    """ 
    Project 2: Handles UDP rdt for a seller client. Sends CHUNK_SIZE chunks of the file through stop and wait. Utilizes method 
    send_packet for actual packet construction and sending.
    """
    def send_item(self, buyer_ip, buyer_port):

        clientSocket = socket(AF_INET, SOCK_DGRAM)
        clientSocket.bind(('', self.sendingPort))
        seq_num = 0

        print('UDP socket opened for RDT.')
        print('Start sending file.')

        if os.path.isfile(self.filename):  # if file is found

            total_bytes = os.stat(self.filename).st_size

            # Send rdt start msg
            print('Sending control seq ' + str(seq_num) + ': start ' + str(total_bytes))
            while True:
                if self.send_packet(seq_num, 0, "start " + str(total_bytes), clientSocket, buyer_ip, buyer_port) == 1:
                    self.initial_send = True
                    break
                print('Msg re-sent HERE: ' + str(seq_num))

            seq_num = 0 if seq_num == 1 else 1

            # Start rdt file transmission
            f = open(file=self.filename, mode='rb')
            chunk = f.read(self.chunk_size)
            num_chunks_sent = 0

            while chunk:
                num_chunks_sent += 1

                # Send chunk until ack received
                while True:
                    if self.initial_send:
                        print('Sending data seq ' + str(seq_num) + ': ' + str(num_chunks_sent*self.chunk_size) + ' / ' + str(total_bytes))
                    else:
                        print('Msg re-sent: ' + str(seq_num))

                    # Send chunk and check for ack success
                    if self.send_packet(seq_num, 1, chunk, clientSocket, buyer_ip, buyer_port) == 1:
                        seq_num = 0 if seq_num == 1 else 1
                        chunk = f.read(self.chunk_size)
                        self.initial_send = True
                        break

            # Send rdt finished
            print('Sending control seq ' + str(seq_num) + ': fin')
            while True:
                if self.send_packet(seq_num, 0, "fin", clientSocket, buyer_ip, buyer_port) == 1:
                    self.initial_send = True
                    break
                print('Msg re-sent: ' + str(seq_num))

        else:
            print("Can't open file item. Notifying buyer and exiting.")
            while True:
                if self.send_packet(seq_num, 0, "Can't open file item. Exiting.", clientSocket, buyer_ip, buyer_port) == 1:
                    break
                print('Msg re-sent: ' + str(seq_num))

        clientSocket.close()

    """ 
    Project 2: Handles UDP rdt packet send for a seller client. Sends CHUNK_SIZE chunk of the file through stop and 
    wait. Waits timeout seconds for ack. Returns 1 ack success if received correct sequence ack within timeout seconds.
    Returns 0 if timeout occurs, ack is dropped or incorrect sender. Will drop msgs with the specified loss_rate.
    """
    def send_packet(self, seq_num, type, chunk, clientSocket, buyer_ip, buyer_port):
        self.initial_send = False

        header = ""
        if type == 0:
            header += str(seq_num) + str(type) + chunk
        else:
            header += str(seq_num) + str(type) + chunk.decode()

        try:
            with timeout(self.timeout):
                clientSocket.sendto(header.encode(), (buyer_ip, buyer_port))

                # Wait for ACK or timeout
                res, res_info = clientSocket.recvfrom(1024)

                msg = int(res.decode())

                # Simulate packet drop
                if randint(1, 100) > self.loss_rate*100:
                    if res_info[0] != buyer_ip or res_info[1] != buyer_port:
                        print('Msg received from incorrect sender: IP: ' + res_info[0] + ' Port: ' + res_info[
                            1])
                        return 0

                    print('Ack received: ' + str(msg))
                    return 1
                else:
                    print('Ack dropped: ' + str(msg))
                    return 0
        except RuntimeError:
            pass

        return 0

    """ 
    Project 2: Handles UDP rdt packet receive for a winning buyer client. Receives CHUNK_SIZE chunk of the file through 
    stop and wait. Calculates total file send time and throughput and saves metrics to performance.txt. Writes transferred 
    file to received.txt. Will drop acks with the specified loss_rate.
    """
    def recieve_item(self, seller_addr, seller_port):

        itemSocket = socket(AF_INET, SOCK_DGRAM)
        itemSocket.bind(('', self.sendingPort))
        print('UDP socket opened for RDT.')
        print('Start receiving file.')

        total_time = datetime.now()

        seq_num_expected = 0
        total_bytes = 0
        num_bytes = 0
        while True:
            # Wait for packet to arrive
            msg, clientAddress = itemSocket.recvfrom(2048)

            msg = msg.decode()
            seq_num = int(msg[0])
            msg_type = int(msg[1])
            content = msg[2:]

            # Simulate packet loss
            if randint(1, 100) > self.loss_rate*100:
                if clientAddress[0] != seller_addr:
                    continue

                # If incorrect sequence number ack previous message
                if seq_num_expected != seq_num:
                    header = 0 if seq_num_expected == 1 else 1
                    itemSocket.sendto(str(header).encode(), (seller_addr, seller_port))
                    print('Msg received with mismatched sequence number ' + str(seq_num) + '. Expecting ' + str(seq_num_expected))
                    print('Ack re-sent: ' + str(header))
                    continue

                # Handle control messages start and fin
                if msg_type == 0:
                    if 'start' in content:
                        total_bytes = int(content[6:])
                        header = seq_num_expected
                        itemSocket.sendto(str(header).encode(), (seller_addr, seller_port))
                        print('Msg received: ' + str(seq_num))
                        print('Ack sent: ' + str(seq_num))
                    if 'fin' in content:
                        header = seq_num_expected
                        itemSocket.sendto(str(header).encode(), (seller_addr, seller_port))
                        itemSocket.sendto(str(header).encode(), (seller_addr, seller_port))
                        itemSocket.sendto(str(header).encode(), (seller_addr, seller_port))
                        print('Msg received: ' + str(seq_num))
                        print('Ack sent: ' + str(seq_num))
                        print('All data received! Exiting...')

                        break
                else:
                    # Handle data messages and add to file data buffer
                    print('Msg received: ' + str(seq_num))
                    self.file_arr.append(content.encode())

                    header = seq_num_expected
                    itemSocket.sendto(str(header).encode(), (seller_addr, seller_port))
                    num_bytes += len(content)
                    print('Ack sent: ' + str(seq_num))
                    print('Received data seq ' + str(seq_num) + ': ' + str(num_bytes) + ' / ' + str(total_bytes))

                seq_num_expected = 0 if seq_num_expected == 1 else 1

            else:
                print('Pkt dropped: ' + str(seq_num))

        # Write file data buffer to received.txt
        self.write_file()

        # Calculate file transfer metrics.
        total_time = (datetime.now() - total_time).total_seconds()
        print('Transmission finished: ' + str(num_bytes) + ' / ' + str(total_time) + ' seconds = ' + str(num_bytes / total_time) + ' bps')

        with open('performance.txt', 'a') as log:
            run_metrics = '\'\'^||^\'\'' + '\n'
            run_metrics += 'LOSS RATE=' + str(self.loss_rate) + '\n'
            run_metrics += 'NUMBER OF BYTES=' + str(num_bytes) + '\n'
            run_metrics += 'TOTAL TIME=' + str(total_time) + '\n'
            run_metrics += 'AVERAGE THROUGHPUT=' + str(num_bytes / total_time) + '\n'
            log.write(run_metrics)


    """ 
    Project 2: Writes the received file chunks to the received.txt file for UDP rdt for the winning buyer client.
    """
    def write_file(self):
        new_file = open('received.txt', 'wb')
        for x in self.file_arr:
            new_file.write(x)
        new_file.close()


""" Creates a client object. """
if __name__ == "__main__":
    client = auc_client()

