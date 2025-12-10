import sys
import os
import struct
import csv

# --- Constants & Configuration ---
BLOCK_SIZE = 512
MAGIC_NUMBER = b'4348PRJ3'  #
DEGREE = 10                 # Minimal degree t=10
MAX_KEYS = (2 * DEGREE) - 1 # 19 keys
MAX_CHILDREN = 2 * DEGREE   # 20 children

# Struct Formats (Big-endian >)
# Header: Magic(8s), RootID(Q), NextBlockID(Q), Unused(remaining)
HEADER_FMT = f'>8sQQ{BLOCK_SIZE - 24}x'

# Node: BlockID(Q), ParentID(Q), NumKeys(Q), 19 Keys(Q), 19 Values(Q), 20 Children(Q)
NODE_FMT = f'>QQQ{MAX_KEYS}Q{MAX_KEYS}Q{MAX_CHILDREN}Q'
NODE_HEADER_SIZE = 24 
NODE_DATA_SIZE = (MAX_KEYS * 8) + (MAX_KEYS * 8) + (MAX_CHILDREN * 8) # 152 + 152 + 160
PADDING_SIZE = BLOCK_SIZE - (NODE_HEADER_SIZE + NODE_DATA_SIZE)

class BTreeNode:
    def __init__(self):
        self.block_id = 0
        self.parent_id = 0
        self.num_keys = 0
        self.keys = [0] * MAX_KEYS
        self.values = [0] * MAX_KEYS
        self.children = [0] * MAX_CHILDREN

    @property
    def is_leaf(self):
        return self.children[0] == 0

    def serialize(self):
        return struct.pack(NODE_FMT, self.block_id, self.parent_id, self.num_keys, *self.keys, *self.values, *self.children) + (b'\x00' * PADDING_SIZE)

    @classmethod
    def deserialize(cls, data):
        node = cls()
        unpacked = struct.unpack(NODE_FMT, data[:BLOCK_SIZE - PADDING_SIZE])
        node.block_id, node.parent_id, node.num_keys = unpacked[0:3]
        node.keys = list(unpacked[3:3+MAX_KEYS])
        node.values = list(unpacked[3+MAX_KEYS:3+2*MAX_KEYS])
        node.children = list(unpacked[3+2*MAX_KEYS:])
        return node
    class IndexFile:
    def __init__(self, filename, mode='r+b'):
        self.filename = filename
        if mode == 'create':
            if os.path.exists(filename):
                print(f"Error: File {filename} already exists.")
                sys.exit(1)
            self.file = open(filename, 'wb+')
            self.root_id = 0
            self.next_block_id = 1
            self._write_header()
        else:
            if not os.path.exists(filename):
                print(f"Error: File {filename} does not exist.")
                sys.exit(1)
            self.file = open(filename, 'r+b')
            self._read_header()

    def _write_header(self):
        self.file.seek(0)
        self.file.write(struct.pack(HEADER_FMT, MAGIC_NUMBER, self.root_id, self.next_block_id))

    def _read_header(self):
        self.file.seek(0)
        data = self.file.read(BLOCK_SIZE)
        if len(data) < BLOCK_SIZE:
             print("Error: Invalid index file.")
             sys.exit(1)
        try:
            magic, root, next_id = struct.unpack(HEADER_FMT, data)
        except struct.error:
             print("Error: Invalid header.")
             sys.exit(1)
        if magic != MAGIC_NUMBER:
            print("Error: Invalid magic number.")
            sys.exit(1)
        self.root_id = root
        self.next_block_id = next_id

    def read_node(self, block_id):
        if block_id == 0: return None
        self.file.seek(block_id * BLOCK_SIZE)
        return BTreeNode.deserialize(self.file.read(BLOCK_SIZE))

    def write_node(self, node):
        self.file.seek(node.block_id * BLOCK_SIZE)
        self.file.write(node.serialize())

    def allocate_node(self):
        node = BTreeNode()
        node.block_id = self.next_block_id
        self.next_block_id += 1
        self._write_header()
        return node

    def close(self):
        self.file.close()