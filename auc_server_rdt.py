# Author: Isabella Samuelsson
# Date: 10/7/22
import sys
from _thread import *
from socket import *

"""
Auction server class. There are two types of auctions type 1 which is first price auction and type 2 which is second 
price auction. In a first price auction the participant with the highest bid wins, and pays exactly the price that 
he/she bids (the highest bid). In a second price auction the participant with highest bid also wins, but only pays the 
price of the second highest bid. The server has two clients connecting Buyers and Sellers. The first client to connect 
is designated the seller and the others will be buyers. The server will accept incoming connections, designate seller 
and buyers and relay the result of the auction. Once the auction has been concluded the server will facilitate the 
transfer of the seller and winning buyers ip address and transfer port numbers for UDP rdt of the file item. After the 
server will disconnect the seller and buyer clients, restart the auction state and will wait for more incoming 
connections to start another auction.

Seller Client: The first client to connect will be the seller. The server prompts for auction information. This 
includes Auction Type: 1 for a first price auction and 2 for a second price auction, Minimum Bid price: non-negative 
integer, Number of Bidders: non-negative integer less than 10 and Item Name: string. If invalid auction information is received the 
server will continue to prompt for valid information. If a client tries to connect while auction information is being 
received the client will be sent a busy message and disconnected.

Buyer Client: All subsequent connections will be designated buyers. The server will only allow the specified number of 
bidders sent in the auction information given by the seller. If additional clients try to connect a server busy message 
will be sent to the client and then it will be disconnected. The server will prompt for a bid. A bid should be a 
non-negative integer, if an invalid bid is given the client will be prompted again.

Run example: python3 auc_server_rdt.py server_port_number
"""
class auc_server:
    # Server info
    serverPort = 12345   # default port
    state = 0            # state 0: waiting for seller, state 1: waiting for buyer
    bad_info = True      # if auction info is invalid

    # Server Seller Msg's
    seller_msg = "Connected to the Auctioneer server.\n\nYour role is: [Seller] \nPlease submit auction request: \n"
    busy_msg = "Server is busy. Try to connect again later.\n"
    invalid_info_msg = "Server: Invalid auction request! \nPlease submit auction request: \n"
    valid_info = "Server: Auction start\n"
    auc_finished_msg = "Disconnecting from the Auctioneer server. Auction is over!\n"

    # Server Buyer Msg's
    buyer_msg = "Connected to the Auctioneer server.\n\nYour role is: [Buyer] \n"
    busy_bidding_msg = "Bidding on-going! Try to connect again later.\n"
    buyer_wait_msg = "The auctioneer is still waiting for other Buyer to connect... \n"
    bidding_start_msg = "The bidding has started!\nPlease submit your bid:\n"
    invalid_bid_msg = "Server: Invalid bid. Please submit a positive integer!\nPlease submit your bid:\n"
    bid_received_msg = "Server: Bid received. Please wait...\n"
    buyer_lost_msg = "Auction finished!\nUnfortunately you did not win the last round.\nDisconnecting from the Auctioneer server. Auction is over!\n"

    # Auction info
    auc_type = 1                # 1 for first price 2 for second price
    lowest_price = 1            # positive integer
    num_bids = 1                # positive integer less then 10
    seller_ip_addr = 0          # seller ip addr
    winning_buyer_transfer_port = -1  # winning buyer UDP rdt port
    seller_transfer_port = -1     # seller UDP rdt port
    winning_buyer_ready = False   # if wining buyer is ready to receive file
    item = ""                   # item name
    buyer_connections = []      # list of buyer client connections
    buyer_ip_addr = []          # list of buyer ip addr
    buyer_bids = []             # list of buyer bids
    client_count = 0            # number of buyer clients connected
    seller = 0                  # if seller and auction info has been established
    bidding_start = False       # if bidding has started
    bidding_resolved = False    # if bidding has finished
    highest_bid = 0             # highest bid
    sold_price = 0              # sold price
    winning_buyer_idx = -1      # index of winning buyer in buyer bids list

    """ Initializes server port from run command arguments and starts the main() function."""
    def __init__(self):
        self.serverPort = int(sys.argv[1])
        self.main()

    """ 
    Handles server communication with the seller client. The server will ask for the auction information and inform 
    the seller at the end of the auction what the auction result is. The parameter connectionSocket is the seller 
    client connection. On auction finish the server will receive the sellers transfer port and send the seller 
    the winning buyers iP address and port information for UDP rdt.
    """
    def handle_seller(self, connectionSocket):
        print(">> New Seller Thread spawned\n")

        auc_info = connectionSocket.recv(1024).decode()                 # request auction info
        auc_info_arr = auc_info.split()

        while self.bad_info:                                            # error check auction info
            if len(auc_info_arr) == 4:

                try:
                    self.auc_type = int(auc_info_arr[0])
                    self.lowest_price = int(auc_info_arr[1])
                    self.num_bids = int(auc_info_arr[2])
                    self.item = str(auc_info_arr[3])

                    if (self.auc_type == 1 or self.auc_type == 2) and self.lowest_price > 0 and 0 < self.num_bids < 10:
                        self.bad_info = False
                    else:
                        connectionSocket.send(self.invalid_info_msg.encode())
                        auc_info = connectionSocket.recv(1024).decode()
                        auc_info_arr = auc_info.split()
                        self.bad_info = True

                except:
                    connectionSocket.send(self.invalid_info_msg.encode())
                    auc_info = connectionSocket.recv(1024).decode()
                    auc_info_arr = auc_info.split()
                    self.bad_info = True

            else:
                connectionSocket.send(self.invalid_info_msg.encode())
                auc_info = connectionSocket.recv(1024).decode()
                auc_info_arr = auc_info.split()

        print("Auction request received. Now waiting for Buyer.\n")
        connectionSocket.send(self.valid_info.encode())
        self.state = 1

        while True:                                                # wait for buyers to connect
            if self.bidding_resolved:                              # once buyers have connected and bidding is resolved
                break

        if self.winning_buyer_idx != -1:
            msg = "Auction finished!\nSuccess! Your item " + str(self.item) + " has been sold for $" + str(self.sold_price) + ".\n"
        else:
            msg = "Auction finished!\nUnfortunately your item " + str(self.item) + " was not sold in the Auction.\n"

        connectionSocket.send((msg + self.auc_finished_msg).encode())    # notify seller client of auction result

        if self.winning_buyer_idx != -1:
            # Project2: Set seller transfer port and wait for the winning buyer transfer port
            self.seller_transfer_port = connectionSocket.recv(1024).decode()

            while self.winning_buyer_transfer_port == -1 or not self.winning_buyer_ready:
                continue


            # Project2: sending winning buyer info to Seller
            print("buyer ip send: " + str(self.buyer_ip_addr[self.winning_buyer_idx]))
            print("buyer port send: " + str(self.winning_buyer_transfer_port))
            winning_buyer_info = self.buyer_ip_addr[self.winning_buyer_idx] + " " + str(self.winning_buyer_transfer_port)
            connectionSocket.send(winning_buyer_info.encode())

        connectionSocket.close()

        # reset state for another auction
        self.state = 0
        self.bad_info = True
        self.buyer_connections = []
        self.buyer_ip_addr = []
        self.seller_ip_addr = 0
        self.winning_buyer_transfer_port = -1
        self.seller_transfer_port = -1
        self.winning_buyer_ready = False
        self.buyer_bids = []
        self.client_count = 0
        self.seller = 0
        self.bidding_start = False
        self.bidding_resolved = False
        self.winning_buyer_idx = -1
        print("Auction Restart: Auctioneer is ready for hosting auctions!\n")


    """ 
    Handles server communication with the seller client. The server will ask for the auction information and inform 
    the seller at the end of the auction what the auction result is. The parameter connectionSocket is the seller 
    client connection. On auction finish the server will receive the winning buyers transfer port and send the winning 
    buyer the sellers iP address and port information for UDP rdt.
    """
    def bidding(self):
        for ix in range(0, self.num_bids):                                         # retrieve bid from each buyer client
            self.buyer_connections[ix].send(self.bidding_start_msg.encode())
            bid = self.buyer_connections[ix].recv(1024).decode()

            not_int = False
            try:
                bid = int(bid)
            except:
                not_int = True

            while not_int or bid <= 0:                                              # make sure valid bid
                self.buyer_connections[ix].send(self.invalid_bid_msg.encode())
                bid = self.buyer_connections[ix].recv(1024).decode()
                not_int = False
                try:
                    bid = int(bid)
                except:
                    not_int = True

            self.buyer_bids.append(bid)
            print("Buyer " + str(ix + 1) + " bid $" + str(bid) + "\n")
            self.buyer_connections[ix].send(self.bid_received_msg.encode())

        self.highest_bid = max(self.buyer_bids)

        if self.highest_bid >= self.lowest_price:                          # select winning buyer based on auction type

            if self.auc_type == 1:
                self.winning_buyer_idx = self.buyer_bids.index(self.highest_bid)
                self.sold_price = self.highest_bid
            else:
                self.winning_buyer_idx = self.buyer_bids.index(self.highest_bid)

                other_bids = self.buyer_bids.copy()
                other_bids.remove(self.highest_bid)
                self.sold_price = max(other_bids)

            print("<< Item sold! The highest bid is $" + str(self.highest_bid) + ". The actual payment is $" + str(self.sold_price) + ".\n")
        else:
            print("<< Item did not sell! The highest bid is $" + str(self.highest_bid) + " and the lowest price is $" + str(self.lowest_price) + ".\n")

        self.bidding_resolved = True                                    # mark bidding as finished for seller thread

        for ix in range(0, self.num_bids):                              # notify buyer clients if they have won the item
            if ix == self.winning_buyer_idx:
                buyer_win_msg = "Auction finished!\nYou won this item " + str(self.item) + "! Your payment due is $" + str(self.sold_price) + "\nDisconnecting from the Auctioneer server. Auction is over!\n"
                self.buyer_connections[ix].send(buyer_win_msg.encode())

                # Project2: Transfer Seller IP and port information to winning buyer for UDP rdt
                self.winning_buyer_transfer_port = self.buyer_connections[ix].recv(1024).decode()

                while self.seller_transfer_port == -1:                  # wait until seller has specified transfer port
                    continue

                seller_info = self.seller_ip_addr + " " + str(self.seller_transfer_port)
                self.buyer_connections[ix].send(seller_info.encode())

                self.winning_buyer_ready = True

            else:
                self.buyer_connections[ix].send(self.buyer_lost_msg.encode())
            self.buyer_connections[ix].close()


    """ 
    Creates connection sockets for each of the clients. The first client to connect is designated seller and the 
    others buyers. Handles starting a seller thread on the handle_seller() function for interacting with the seller 
    client and also starts a bidding thread on the bidding() function to facilitate the bidding process. After the 
    auction has concluded the seller thread will disconnect the seller client and reset auction state. The bidding 
    thread will disconnect buyer clients. Then the server is ready for more incoming connections and to start a new 
    auction.
    """
    def main(self):
        serverSocket = socket(AF_INET, SOCK_STREAM)                                 # Main server socket
        serverSocket.bind(("", self.serverPort))
        serverSocket.listen(1)
        print("Auctioneer is ready for hosting auctions!\n")

        while True:

            connectionSocket, addr = serverSocket.accept()                          # client socket
            if self.state == 0:                                                     # client is a seller
                if self.seller == 1:                                                # send busy msg to incoming client connection and disconnect
                    connectionSocket.send(self.busy_msg.encode())
                    connectionSocket.close()
                else:
                    self.seller_ip_addr = addr[0]
                    connectionSocket.send(self.seller_msg.encode())
                    print("Seller is connected from " + addr[0] + "\n")
                    self.seller = 1
                    start_new_thread(self.handle_seller, (connectionSocket,))      # start handle seller thread
            else:
                if self.bidding_start:                                             # send busy msg tp incoming client connection and disconnect
                    connectionSocket.send(self.busy_bidding_msg.encode())
                    connectionSocket.close()
                else:
                    self.client_count += 1
                    print("Buyer " + str(self.client_count) + " is connected from " + addr[0] + "\n")

                    # Project2: Added list of buyer ip addr
                    self.buyer_ip_addr.append(addr[0])
                    print("added")

                    if self.client_count == self.num_bids:                          # since correct number buyers are now connected, add buyer client connection to buyer connections list
                        connectionSocket.send(self.buyer_msg.encode())

                        self.buyer_connections.append((connectionSocket))
                        print("Requested number of bidders arrived. Let's start bidding!\n")
                        print(">> New Bidding Thread spawned\n")
                        self.bidding_start = True
                        start_new_thread(self.bidding, ())                          # start bidding thread since correct number of buyer clients are connected
                    else:
                        connectionSocket.send(self.buyer_msg.encode())              # still need more buyers connected so add buyer client connection to buyer connection list, and wait for more buyers
                        connectionSocket.send(self.buyer_wait_msg.encode())
                        self.buyer_connections.append((connectionSocket))


if __name__ == "__main__":
    server = auc_server()
