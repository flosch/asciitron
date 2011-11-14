# -*- coding: utf-8 -*-

import argparse

from server import TronServer
from client import TronClient

def main():
    parser = argparse.ArgumentParser(description='TronClient Game')
    parser.add_argument('-p', '--port', dest='port', type=int, 
                        default=9158, help='communication port, default: 9158')
    
    subparsers = parser.add_subparsers()
    
    client_parser = subparsers.add_parser('connect', help='Connect to a game')
    client_parser.add_argument('hostname', help='server hostname')
    client_parser.add_argument('playerid', type=int, help='player id')
    client_parser.add_argument('--beep', action='store_true',
                        help='beeps during game countdown to notify the user')

    server_parser = subparsers.add_parser('serve', help='Serve a game')
    server_parser.add_argument('playercount', type=int, help='number of players')

    args = parser.parse_args()
    args = vars(args)
    
    if args.has_key('hostname'):
        # Connect to a server
        tron = TronClient(hostname=args['hostname'], 
                    player_id=args['playerid'],
                    port=args['port'],
                    beep=args['beep'])
        try:
            tron.run()
        finally:
            tron.stop()
    else:
        # Run a server
        server = TronServer(player_count=args['playercount'], port=args['port'])
        try:
            server.serve()
        except KeyboardInterrupt:
            server.stop()