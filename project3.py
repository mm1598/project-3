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
    def search(self, key):
        if self.root_id == 0: return None
        curr = self.read_node(self.root_id)
        while True:
            i = 0
            while i < curr.num_keys and key > curr.keys[i]: i += 1
            if i < curr.num_keys and key == curr.keys[i]: return (curr.keys[i], curr.values[i])
            if curr.is_leaf: return None
            curr = self.read_node(curr.children[i])

    def insert(self, key, value):
        if key < 0 or value < 0:
            print("Error: Key and Value must be unsigned.")
            return

        if self.search(key):
            print(f"Error: Key {key} already exists.")
            return

        if self.root_id == 0:
            root = self.allocate_node()
            root.num_keys = 1
            root.keys[0] = key
            root.values[0] = value
            self.root_id = root.block_id
            self.write_node(root)
            self._write_header()
            return

        root = self.read_node(self.root_id)
        if root.num_keys == MAX_KEYS:
            new_root = self.allocate_node()
            new_root.children[0] = self.root_id
            root.parent_id = new_root.block_id
            self.write_node(root)
            self.root_id = new_root.block_id
            self._write_header()
            self.split_child(new_root, 0, root)
            self.insert_non_full_iterative(new_root, key, value)
        else:
            self.insert_non_full_iterative(root, key, value)

    def split_child(self, parent, index, child):
        z = self.allocate_node()
        z.parent_id = parent.block_id
        t = DEGREE
        
        # Move keys t..2t-2 to Z
        z.num_keys = t - 1
        for j in range(t - 1):
            z.keys[j] = child.keys[j + t]
            z.values[j] = child.values[j + t]
            child.keys[j + t] = 0
            child.values[j + t] = 0

        # Move children t..2t-1 to Z
        if not child.is_leaf:
            for j in range(t):
                z.children[j] = child.children[j + t]
                if z.children[j] != 0:
                    # Transiently load grandchild to update parent pointer
                    gc = self.read_node(z.children[j])
                    gc.parent_id = z.block_id
                    self.write_node(gc)
                child.children[j + t] = 0

        child.num_keys = t - 1

        for j in range(parent.num_keys, index, -1):
            parent.children[j + 1] = parent.children[j]
        parent.children[index + 1] = z.block_id

        for j in range(parent.num_keys - 1, index - 1, -1):
            parent.keys[j + 1] = parent.keys[j]
            parent.values[j + 1] = parent.values[j]

        parent.keys[index] = child.keys[t - 1]
        parent.values[index] = child.values[t - 1]
        parent.num_keys += 1
        
        child.keys[t - 1] = 0
        child.values[t - 1] = 0

        self.write_node(child)
        self.write_node(z)
        self.write_node(parent)

    def insert_non_full_iterative(self, curr, key, value):
        while True:
            i = curr.num_keys - 1
            if curr.is_leaf:
                while i >= 0 and key < curr.keys[i]:
                    curr.keys[i + 1] = curr.keys[i]
                    curr.values[i + 1] = curr.values[i]
                    i -= 1
                curr.keys[i + 1] = key
                curr.values[i + 1] = value
                curr.num_keys += 1
                self.write_node(curr)
                return
            else:
                while i >= 0 and key < curr.keys[i]:
                    i -= 1
                i += 1
                
                child_id = curr.children[i]
                child = self.read_node(child_id)
                
                if child.num_keys == MAX_KEYS:
                    self.split_child(curr, i, child)
                    if key > curr.keys[i]:
                        i += 1
                    child = self.read_node(curr.children[i])
                
                curr = child