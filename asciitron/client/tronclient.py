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

import os
import sys
import time
import curses
import socket
import struct
import random
import threading
import Queue

from ..common import *

random.seed()

stdscr = None

class Network(object):
	def __init__(self, game, hostname, player_id, port):
		self.player_id = player_id
		self.game = game
		self.hostname = hostname
		self.port = port
		
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		
		self.buf_in = ""
		self.connected = False

		self.handler_thread = threading.Thread(target=self.handler_loop)
	
	def connect(self):
		try:
			self.socket.connect((self.hostname, self.port))
		except socket.error:
			self.connected = False
		else:
			self.connected = True

		return self.connected
	
	def disconnect(self):
		try:
			self.socket.close()
		except socket.error:
			pass
		self.connected = False
	
	def handle_packet(self, packet):
		player_id, cmd, x, y, speed, nitro, misc = packet
		
		# Update speed
		self.game.speed = speed
		self.game.nitrotank = nitro
		#stdscr.addstr("Network packet received (pno=%s, cmd=%s, x=%s, y=%s)!\n" % (player_id, cmd, x, y))
		#stdscr.refresh()
		
		if cmd == 0: # Hello, answering with player id
			self.send(0, self.game.WIDTH, self.game.HEIGHT, self.player_id)
		elif cmd == 1: # Game start in X seconds!
			self.game.x = random.randint(int(x*0.1), int(x*0.9))
			self.game.y = random.randint(int(y*0.1), int(y*0.9))
			
			self.game.gamepad.height = y
			self.game.gamepad.width = x
			
			# Start game countdown
			for sec in xrange(player_id, 0, -1):
				BANNER = "Game starts in %s seconds..." % sec
				stdscr.addstr(self.game.HEIGHT / 2,
							  self.game.WIDTH / 2 - len(BANNER) / 2, 
							  BANNER)
				stdscr.refresh()
				if self.game.beep:
					curses.beep()
				time.sleep(1)

			# Draw borders
			stdscr.clear()
			stdscr.addch(0, 0, curses.ACS_ULCORNER) # upper left corner
			stdscr.hline(0, 1, curses.ACS_HLINE, x-2) # upper horizontal line
			stdscr.addch(0, x-1, curses.ACS_URCORNER) # upper right corner
			stdscr.vline(1, x-1, curses.ACS_VLINE, y-2) # right vertical line
			stdscr.insch(y-1, x-1, curses.ACS_LRCORNER) # lower right corner (insch has to be used for this, because addch would throw an exception)
			stdscr.hline(y-1, 1, curses.ACS_HLINE, x-2) # lower horizontal line
			stdscr.addch(y-1, 0, curses.ACS_LLCORNER) # lower left corner
			stdscr.vline(1, 0, curses.ACS_VLINE, y-2) # left vertical line
			stdscr.refresh()

		elif cmd == 2: # Set position from player
			try:
				player_id = int(player_id)
			except ValueError:
				# ignore erroneous player id (e. g. because of a transmission error)
				return
			self.game.gamepad.dispatcher_queue.put((x, y, player_id))
		elif cmd == 3: # Crash of Player X
			self.game.check_crash(player_id)
		elif cmd == 4: # Player X won
			self.game.check_win(player_id)
		elif cmd == 5: # Remove player X from map
			self.game.remove_from_map(player_id)
		elif cmd == 9: # Graceful disconnect
			# TODO: Message ausgeben?
			self.disconnect()
			sys.exit(0)
		elif cmd == 10: # Server full
			stdscr.addstr("Server is full! Press any key.\n")
			stdscr.refresh()
			stdscr.getkey()
			sys.exit(0)
		elif cmd == 11: # Game running
			stdscr.addstr("There is still a game running! Wait! Press any key.\n")
			stdscr.refresh()
			stdscr.getkey()
			sys.exit(0)
		elif cmd == 12: # Player ID already taken
			stdscr.addstr("Player ID already taken - please change! Press any key.\n")
			stdscr.refresh()
			stdscr.getkey()
			sys.exit(0)
		elif cmd == 13: # Invalid Player ID
			stdscr.addstr("Invalid Player ID (only one digit is allowed)! Press any key.\n")
			stdscr.refresh()
			stdscr.getkey()
			sys.exit(0)
		elif cmd == 20: # Set new speed
			self.game.speed = x

	def handle(self, bulk=False):
		if not self.connected: return False

		try:
			buf = self.socket.recv(bulk and 8192 or FMT_SIZE_TOPLAYER)
		except socket.error:
			self.disconnect()
			return False
		else:
			if len(buf) == 0:
				self.disconnect()
				return False
			else:
				self.buf_in += buf

		
		# only for debugging purposes: Simulate lag of 50ms
		#if len(self.buf_in) >= FMT_SIZE_TOPLAYER:
		#	time.sleep(0.05)		
		
		while len(self.buf_in) >= FMT_SIZE_TOPLAYER:
			packet = struct.unpack(FMT_TOPLAYER, self.buf_in[:FMT_SIZE_TOPLAYER])
			self.handle_packet(packet)
			self.buf_in = self.buf_in[FMT_SIZE_TOPLAYER:]
		
		return True

	def send(self, cmd, x, y, misc=0):
		if not self.connected: return False
		try:
			sent_bytes = self.socket.send(struct.pack(FMT_TOSERVER, cmd, x, y, misc))
		except (socket.error, struct.error):
			self.disconnect()
			return False
		else:
			if sent_bytes == 0:
				self.disconnect()
				return False
			else:
				return True
	
	def tell(self, x, y):
		self.send(2, x, y)
	
	def handler_loop(self):
		while self.connected:
			self.handle(bulk=True)
	
	def start(self):
		self.handler_thread.daemon = True
		self.handler_thread.start()

class Gamepad(object):
	def __init__(self, tron, height, width):
		self.tron = tron
		self.height = height
		self.width = width
		
		self.dispatcher_queue = Queue.Queue()
		self.dispatcher_thread = threading.Thread(target=self.position_dispatcher)
		self.dispatcher_thread.daemon = True
		self.dispatcher_thread.start()
		
		self.draw_lock = threading.Lock()

	def position_dispatcher(self):
		while True:
			try:
				x, y, player_id = self.dispatcher_queue.get(True, 1)
			except Queue.Empty:
				continue 
			
			self.draw_player(x, y, player_id)
			
			# Add position to map for further checks 
			# e. g. local crash/boundary checks (instead of server ones) or 
			# removing a player from the map
			if player_id == 0:
				del self.tron.map[(x, y)]
			else:
				self.tron.map[(x, y)] = player_id
	
	def draw_player(self, x, y, char='*'):
		char = str(char)
		
		if len(char) != 1:
			char = '?'
		
		if ord(char) < 33 or ord(char) > 125:
			char = 'E'
		
		# Empty field (for crashed players)
		if char == '0':
			char = ' '
		
		# determine color for player
		color = curses.COLOR_BLACK
		if char != '*' and False: # Exclude '*'
			if self.tron.player_colors.has_key(char):
				color = self.tron.player_colors[char]
			else:
				if len(self.tron.available_colors) > 0:
					color = random.choice(self.tron.available_colors)
					del self.tron.available_colors[self.tron.available_colors.index(color)]
					self.tron.player_colors[char] = color
		
		with self.draw_lock:
			try:
				stdscr.addch(y, x, ord(char))
			except:
				pass
			stdscr.refresh()

class TronClient(object):
	class Direction:
		LEFT, RIGHT, UP, DOWN = range(4)

	#HEIGHT, WIDTH = 0, 0

	def __init__(self, hostname, player_id, port, beep):
		global stdscr

		os.environ['ESCDELAY'] = '0'
		stdscr = curses.initscr()
		curses.start_color()
		curses.noecho()
		curses.curs_set(0)
		stdscr.keypad(1)
		
		self.beep = beep
		self.HEIGHT, self.WIDTH = stdscr.getmaxyx()
		self.gamepad = Gamepad(self, self.HEIGHT, self.WIDTH)
		self.direction = self.Direction.RIGHT
		self.x = 0
		self.y = 0
		self.time_normalizer = float(self.HEIGHT) / self.WIDTH
		self.draw_thread = None
		self.collided = False
		self.player_id = player_id
		self.network = Network(self, hostname, player_id, port)
		
		self.available_colors = [curses.COLOR_BLUE, curses.COLOR_CYAN, 
								 curses.COLOR_YELLOW, curses.COLOR_GREEN]
		self.player_colors = {}
		self.map = {} # Contains a map: (x, y) -> player-id
		self.speed = 120 # Current speed of the player in ms (1000ms = 1s)
		self.nitrotank = 100 # Current status of nitro tank in percent
	
	def stop(self):
		curses.endwin()

	def change_direction(self, key):
		if key in [curses.KEY_DOWN, ord('s'), ord('j')]:
			if self.direction in [self.Direction.LEFT, self.Direction.RIGHT]:
				self.direction = self.Direction.DOWN
		elif key in [curses.KEY_UP, ord('w'), ord('k')]:
			if self.direction in [self.Direction.LEFT, self.Direction.RIGHT]:
				self.direction = self.Direction.UP
		elif key in [curses.KEY_LEFT, ord('a'), ord('h')]:
			if self.direction in [self.Direction.UP, self.Direction.DOWN]:
				self.direction = self.Direction.LEFT
		elif key in [curses.KEY_RIGHT, ord('d'), ord('l')]:
			if self.direction in [self.Direction.UP, self.Direction.DOWN]:
				self.direction = self.Direction.RIGHT

	def move_player(self):
		if self.direction == self.Direction.LEFT:
			self.x -= 1
		if self.direction == self.Direction.RIGHT:
			self.x += 1
		if self.direction == self.Direction.UP:
			self.y -= 1
		if self.direction == self.Direction.DOWN:
			self.y += 1
		
		# Check for collision!
		#if self.map.has_key((self.x, self.y)) or \
		#	self.x <= 0 or self.x >= self.gamepad.width - 1 or \
		#	self.y <= 0 or self.y >= self.gamepad.height - 1:
		#	self.collided = True

	def remove_from_map(self, player_id):
		coords = filter(lambda f: f[1] == player_id, self.map.items())
		for coord, _ in coords:
			self.gamepad.dispatcher_queue.put((coord[0], coord[1], '0'))
			del self.map[coord]

	def check_crash(self, player_id):
		"""
		Whenever the server tells the game a player crashed,
		this method will be called to take further action.
		"""
		
		# Go and remove the snake
		self.remove_from_map(player_id)

		if self.player_id == player_id:
			self.collided = True
			
			BANNER = "Uhh, you booomed! :-("
			with self.gamepad.draw_lock:
				win = curses.newwin(3, 4+len(BANNER), 5, 5)
				win.box()
				win.addstr(1, 2, BANNER)
				win.refresh()
		else:
			with self.gamepad.draw_lock:
				stdscr.addstr(0, 10, "Player %s boomed." % player_id)
				stdscr.refresh()
	
	def check_win(self, player_id):
		"""
		Whenever the server tells the game a player won,
		this method will be called to take further action.
		"""
		self.collided = True
		if self.player_id == player_id:
			# We won!
			BANNER = "Congrats, you won! :-)"
		else:
			# Another player won
			BANNER = "Player %s won, you lost!" % player_id
		
		with self.gamepad.draw_lock:
			win = curses.newwin(3, 4+len(BANNER), 5, 5) 
			win.box()
			win.addstr(1, 2, BANNER)
			win.refresh()
			stdscr.refresh()
		time.sleep(3)
		
		self.network.disconnect()

	def nitro(self):
		# Activate Nitro!
		self.network.send(21, 0, 0)

	def run(self):
		retries = 0	
		while True:
			try:
				if not self.network.connect():
					# Connection failed, retrying...
					retries += 1
					stdscr.addstr(0, 0, "Server unreachable, retrying (#%s)...\n" %
								  retries)
					stdscr.refresh()
					time.sleep(1)
				else:
					# Game connected to the game server
					
					# Wait for the welcome package
					self.network.handle()
					
					stdscr.addstr("Connected, waiting for all players...\n")
					stdscr.refresh()
					
					# Wait for the server to start the game ("Start-Package", 
					# which includes several parameters such as the countdown seconds) 
					self.network.handle()
					
					# Go start the network dispatch loop (in it's own thread)
					self.network.start()
					
					# And now leave this setup loop
					break
			except KeyboardInterrupt:
				return False

		# Enter game loop
		stdscr.timeout(0)
		while self.network.connected:
			
			speed = self.speed / 1000.0 # ms -> seconds
			
			try:
				c = stdscr.getch()
			except KeyboardInterrupt:
				return False

			if c == 27: # Escape -> Quit game
				return True
			elif c == 110: # "n" = NitroSpeed
				self.nitro()

			if not self.collided:
				self.change_direction(c)			# Change direction of player according to keypress
				self.move_player()					# Move player
				self.network.tell(self.x, self.y)	# Tell server new player position
			
				# Add the new position to the gamepad dispatcher queue to 
				# get the * drawn
				self.gamepad.dispatcher_queue.put((self.x, self.y, '*'))

				# Normalize speed depending on the direction
				if self.direction in [curses.KEY_LEFT, curses.KEY_RIGHT]:
					speed *= self.time_normalizer
			
			with self.gamepad.draw_lock:
				try:
					stdscr.addstr(self.gamepad.height - 1, 5, 
							 "Speed: %4d  Nitro tank: %3d%%" % 
							 (100.0/speed, self.nitrotank))
					stdscr.refresh()
				except:
					pass
			time.sleep(speed)

		return True