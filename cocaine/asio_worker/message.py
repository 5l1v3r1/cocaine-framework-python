# encoding: utf-8
#
#    Copyright (c) 2011-2013 Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    Cocaine is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>. 
#


import msgpack

from itertools import izip

#
#   Answer to C++ templates
#

PROTOCOL_LIST = (
    "rpc::handshake",   #0
    "rpc::heartbeat",   #1
    "rpc::terminate",   #2
    "rpc::invoke",      #3
    "rpc::chunk",       #4
    "rpc::error",       #5
    "rpc::choke",       #6
    )

PROTOCOL = {
    "rpc::handshake": {
        "id" : PROTOCOL_LIST.index("rpc::handshake"),
        "tuple_type": ("unique_id")
    },
    "rpc::heartbeat": {
        "id" : PROTOCOL_LIST.index("rpc::heartbeat"),
        "tuple_type": ()
    },
    "rpc::terminate"  : {
        "id" : PROTOCOL_LIST.index("rpc::terminate"),
        "tuple_type": ("reason", "message")
    },
    "rpc::invoke"   : {
        "id" : PROTOCOL_LIST.index("rpc::invoke"),
        "tuple_type": ("session", "event")
    },
    "rpc::chunk"    : {
        "id" : PROTOCOL_LIST.index("rpc::chunk"),
        "tuple_type": ("session", "data")
    },
    "rpc::error"    : {
        "id" : PROTOCOL_LIST.index("rpc::error"),
        "tuple_type": ("session", "code", "message")
    },
    "rpc::choke"    : {
        "id" : PROTOCOL_LIST.index("rpc::choke"),
        "tuple_type": ("session",)
    }
}

def closure(m_id, args):
    def _wrapper():
        return ((m_id, args))
    return _wrapper

class MessageInit(type):

    def __call__(cls, rpc_tag, *tuple_types):
        obj_dict = PROTOCOL[rpc_tag]
        msg = object.__new__(cls)
        msg.__init__()
        setattr(msg, "id", obj_dict["id"])
        [setattr(msg, attr, value) for attr, value in izip(obj_dict["tuple_type"], tuple_types)]
        setattr(msg, "pack", closure(msg.id, tuple_types))
        return msg

class Message(object):
    __metaclass__ = MessageInit

    @staticmethod
    def initialize(unpacked_data):
        try:
            _id = unpacked_data[0]
            args = unpacked_data[1] #if unpacked_data[1] is not None else list()
            return Message(PROTOCOL_LIST[_id], *args)
        except Exception as err:
            #print str(err)
            return None