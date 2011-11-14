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

import struct

FMT_TOPLAYER = "hhiihBh" # player-no, cmd-no, x, y, speed, nitrotank, misc
FMT_SIZE_TOPLAYER = struct.calcsize(FMT_TOPLAYER)

FMT_TOSERVER = "hiih" # cmd-no, x, y, misc
FMT_SIZE_TOSERVER = struct.calcsize(FMT_TOSERVER)
