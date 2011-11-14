#!/usr/bin/python
# -*- coding: utf-8 -*-

#                           _ _ _                   
#             __ _ ___  ___(_|_) |_ _ __ ___  _ __  
#            / _` / __|/ __| | | __| '__/ _ \| '_ \ 
#           | (_| \__ \ (__| | | |_| | | (_) | | | |
#            \__,_|___/\___|_|_|\__|_|  \___/|_| |_|
#
#                    A Light Cycle game
#
#
#  Copyright (C) 2011, Florian Schlachter <flori@n-schlachter.de>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program. If not, see <http://www.gnu.org/licenses/>.

import socket
import select
import struct
import time

from ..common import *
import settings

class Player(object):
    """
    0 = O hai! (Ping-Package)
    1 = Start game in X seconds
    2 = Set Position for Player N
    3 = Player X lost game
    4 = Player X won game
    5 = Remove Player X from map
    9 = Server disconnected gracefully
    
    # pre-game commands 
    10 = Server full
    11 = Game is running
    12 = Player ID already taken
    13 = Player ID invalid
    14 = Players available (X of Y)
    
    # in game controls
    20 s -> c = set speed in ms of X (1000ms = 1s)
    21 = Activate Nitro
    """

    def __init__(self, server, connection, address):
        self.server = server
        self.socket = connection
        self.address = address
        self.buf_in = ""
        self.buf_out = ""
        self.player_id = None
        self.width = -1
        self.height = -1
        self.crashed = False
        self.speed = settings.SPEED_NORMAL # Current player speed
        self.nitro_start = 0
        self.nitro = False
        self.nitrotank = 100 # in percent
        self.coords = [] # contains all visited coords (x,y) for this player
        self.x = 0 # Current position X
        self.y = 0 # Current position Y
        self.last_activity = 0
        self.log("Connected")
    
    def remove_from_map(self):
        if self.coords:
            for x, y in self.coords:
                del self.server.map[(x, y)]
            self.coords = []
            self.server.broadcast(self.player_id, 5, 0, 0)
            self.log("I was removed from map")
    
    def send(self, player_id, cmd, x, y, misc=0):
        self.buf_out += struct.pack(FMT_TOPLAYER, player_id, cmd, x, y,
                                    int(self.speed), int(self.nitrotank), misc)
    
    def is_last_active(self):
        return not self.crashed and \
            len(filter(lambda f: not f.crashed, self.server.players)) == 1
    
    def is_last(self):
        return len(filter(lambda f: not f.crashed, self.server.players)) == 0
    
    def handle_packet(self, packet):
        self.last_activity = time.time()
        
        cmd, x, y, misc = packet
        #print "Handle packet:", packet
        if cmd == 0:
            # O hai-packet 
            # misc contains player id

            self.width = x
            self.height = y
            
            if len(str(misc)) != 1 or misc == 0:
                self.log("Player id %s invalid, refused." % misc)
                self.send(0, 13, 0, 0)
                self.disconnect()
                self.remove()
                return
            
            for player in self.server.players:
                if misc == player.player_id:
                    self.log("Player id %s already taken, refused." % misc)
                    self.send(0, 12, 0, 0)
                    self.disconnect()
                    self.remove()
                    return

            self.log("Setting player id: %s (%sx%s)" % (misc, x, y))
            self.player_id = misc
        elif cmd == 2:
            if self.crashed:
                # Ignore the new position, since the player already crashed!
                return
            
            if self.server.map.has_key((x, y)) or \
                x <= 0 or x >= self.server.width - 1 or y <= 0 or y >= self.server.height - 1:

                self.crashed = True

                if self.is_last() and len(self.server.players) > 1:
                    # I won! (only in multiplayer modus)
                    self.server.broadcast(self.player_id, 4, 0, 0)
                    self.log("I won!")
                else:
                    # I lost 
                    self.server.broadcast(self.player_id, 3, 0, 0)
                    self.log("I'm crashed.")
                    self.remove_from_map()
            else:
                self.x = x
                self.y = y
                self.coords.append((x, y))
                self.server.map[(x, y)] = self.player_id 
                
                if self.nitrotank < 100:
                    self.nitrotank = min(self.nitrotank + 1, 100)
                
                if self.nitro:
                    # In nitro
                    if (time.time() - self.nitro_start) >= settings.NITRO_TIME:
                        # Nitro time over? Go back to normal.
                        self.speed = settings.SPEED_NORMAL
                        self.nitro = False
                    else:
                        self.speed = min(settings.SPEED_NORMAL, self.speed * 1.01)
                else:
                    # Check if the player runs along the border (10%) ->
                    # change the speed if neccessary!
                    if 0 < x < self.server.width * 0.1 or \
                        self.server.width * 0.9 < x < self.server.width or \
                        0 < y < self.server.height * 0.1 or \
                        self.server.height * 0.9 < y < self.server.height:
                        # Within the 10% border!
                        self.speed = max(self.speed * 0.9,
                                         settings.SPEED_NORMAL - settings.SPEED_BORDER)
                    else:
                        self.speed = min(self.speed * 1.1,
                                         settings.SPEED_NORMAL)
                
                # Notify all users about new coordinations
                self.server.broadcast(self.player_id, 2, x, y)
        elif cmd == 21:
            # Activate nitro!
            if self.nitrotank <= 25:
                return
            
            self.nitro_start = time.time()
            
            r = settings.SPEED_NITRO * (1.0 - (100 - self.nitrotank) / 100.0)
            self.speed = max(settings.SPEED_NORMAL - settings.SPEED_NITRO,
                             self.speed - r)
            
            self.nitrotank = 0
            self.nitro = True
        else:
            self.log("Unknown command received: %s" % cmd)
    
    def handle_read(self):
        try:
            buf = self.socket.recv(8192)
            self.buf_in += buf
        except socket.error:
            self.remove()
        else:
            if len(buf) == 0:
                self.remove()
            else:
                # Parse incoming
                while len(self.buf_in) >= FMT_SIZE_TOSERVER:
                    packet = struct.unpack(FMT_TOSERVER, self.buf_in[:FMT_SIZE_TOSERVER])
                    self.handle_packet(packet)
                    self.buf_in = self.buf_in[FMT_SIZE_TOSERVER:]
    
    def handle_write(self):
        try:
            sent_bytes = self.socket.send(self.buf_out)
        except socket.error:
            self.remove()
        else:
            if sent_bytes == 0: 
                self.remove()
            else:
                self.buf_out = self.buf_out[sent_bytes:]
    
    def disconnect(self):
        self.send(0, 9, 0, 0)
        self.handle_write()
        self.socket.close()
        self.log("Gracefully disconnected by server")
    
    def remove(self):
        # Remove connection due to socket errors
        self.remove_from_map()
        if self in self.server.players:
            self.server.players.remove(self)
        self.log("Disconnected")
    
    def log(self, msg):
        print "[Player %s] %s" % (self.player_id or self.address[0], msg)
    
    def fileno(self):
        try:
            return self.socket.fileno()
        except socket.error:
            return 0

    def __repr__(self):
        return '<Player %s>' % self.player_id

class TronServer(object):
    def __init__(self, player_count, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #self.socket.setsockopt(socket.SOL_SOCKET, socket.TCP_NODELAY, 1)
        self.socket.bind(('', port))
        self.socket.listen(3)

        self.players = []
        self.player_count = player_count
        self.game_state = "init"
        self.map = {}
        self.width = 0
        self.height = 0

        print "Serving Tron at port %d (TCP)." % port
        print "At your service. Waiting for %s player(s) now." % player_count

    def broadcast(self, player_id, cmd, x, y):
        for player in self.players:
            player.send(player_id, cmd, x, y)

    def serve(self):
        while True:
            rlist = [self.socket, ] + self.players
            wlist = filter(lambda f: len(f.buf_out) > 0, self.players)
            xlist = self.players
            worked = False
            r = select.select(rlist, wlist, xlist, .3)
            #print "Selecting:", r
            for s in r[0]:
                worked = True
                # data available / new client!
                if s == self.socket:
                    conn, address = self.socket.accept()
                    player = Player(self, conn, address)
                    if self.game_state != "init":
                        player.log("Game is running, disconnecting...")
                        player.send(0, 11, 0, 0) # Game is running
                        player.handle_write()
                        player.disconnect()
                        del player
                    elif len(self.players) >= self.player_count:
                        player.log("Server is full, disconnecting...")
                        player.send(0, 10, 0, 0) # Server full
                        player.handle_write()
                        player.disconnect()
                        del player
                    else:
                        self.players.append(player)
                        player.send(0, 0, 0, 0) # Please gief player ID!
                else:
                    s.handle_read()
            
            for s in r[1]:
                worked = True
                # data write
                s.handle_write()
            
            if r[2]:
                worked = True
                raise NotImplementedError('Not yet implemented. Huh?')
            
            # Is only one playing player left? Let him win the round.
            if self.game_state == "running":
                not_crashed_players = filter(lambda p: not p.crashed, self.players)
                if len(not_crashed_players) == 1 and len(self.players) > 1:
                    self.broadcast(not_crashed_players[0].player_id, 4, 0, 0)
                    continue
            
            if not worked:
                # All players crashed? Disconnect them after 3 seconds idle time
                if len(self.players) > 0 and \
                    len(filter(lambda p: not p.crashed, self.players)) == 0:
                    for player in self.players:
                        if (time.time() - player.last_activity) >= 3:
                            player.disconnect()
                            player.remove()
                    #continue
                
                # No players online? Reset game.
                if len(self.players) == 0 and self.game_state != "init":
                    self.game_state = "init"
                    self.map = {}
                    print "No players online, resetting game. Ready!"
                
                # Check for game start
                if self.game_state == "init":
                    if len(self.players) == self.player_count:
                        # TODO: Check wheter every player has a Player ID!
                        
                        # Determine minimal tty
                        min_x = self.players[0].width
                        min_y = self.players[0].height
                        
                        for player in self.players[1:]:
                            if player.width < min_x:
                                min_x = player.width
                            if player.height < min_y:
                                min_y = player.height
                        
                        self.width = min_x
                        self.height = min_y
                        
                        # Go and start the game!
                        print "Game starts in %s seconds." % settings.SECONDS 
                        self.broadcast(settings.SECONDS, 1, min_x, min_y) # Start game in 5 secs
                        self.game_state = "running"
                        
                        # Tell the current speed
                        self.broadcast(0, 20, settings.SPEED_NORMAL, 0)
                        
                        # Nitro tank 100%
                        self.broadcast(0, 21, 100, 0)

    def stop(self):
        print "Disconnecting all players..."
        # Closing all client connections
        for player in self.players:
            player.disconnect()
        print "Disconnected."
        
        self.socket.close()
        print "Server halted."
