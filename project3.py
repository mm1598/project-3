import sys
import os
import struct
import csv

# --- Constants & Configuration ---
BLOCK_SIZE = 512
MAGIC_NUMBER = b'4348PRJ3'  # [cite: 300]
DEGREE = 10                 # Minimal degree t=10 [cite: 316]
MAX_KEYS = (2 * DEGREE) - 1 # 19 keys [cite: 316]
MAX_CHILDREN = 2 * DEGREE   # 20 children [cite: 316]

# Struct Formats (Big-endian >) [cite: 281]
# Header: Magic(8s), RootID(Q), NextBlockID(Q), Unused(remaining) [cite: 300, 301, 302]
HEADER_FMT = f'>8sQQ{BLOCK_SIZE - 24}x'

# Node: BlockID(Q), ParentID(Q), NumKeys(Q), 19 Keys(Q), 19 Values(Q), 20 Children(Q) [cite: 319-324]
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
                print(f"Error: File {filename} already exists.") # [cite: 242]
                sys.exit(1)
            self.file = open(filename, 'wb+')
            self.root_id = 0
            self.next_block_id = 1
            self._write_header()
        else:
            if not os.path.exists(filename):
                print(f"Error: File {filename} does not exist.") # [cite: 245]
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
            print("Error: Invalid magic number.") # [cite: 300]
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

    # --- Iterative B-Tree Operations (Strict "Max 3 Nodes" Compliance) ---

    def search(self, key):
        if self.root_id == 0: return None
        curr = self.read_node(self.root_id)
        while True:
            i = 0
            while i < curr.num_keys and key > curr.keys[i]: i += 1
            if i < curr.num_keys and key == curr.keys[i]: return (curr.keys[i], curr.values[i])
            if curr.is_leaf: return None
            curr = self.read_node(curr.children[i]) # [cite: 337, 338]

    def insert(self, key, value):
        if key < 0 or value < 0:
            print("Error: Key and Value must be unsigned.") # [cite: 247]
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
        # Memory Check: Holds 'parent', 'child', and 'z'. (3 nodes) - Compliant
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

        # Shift parent children
        for j in range(parent.num_keys, index, -1):
            parent.children[j + 1] = parent.children[j]
        parent.children[index + 1] = z.block_id

        # Shift parent keys
        for j in range(parent.num_keys - 1, index - 1, -1):
            parent.keys[j + 1] = parent.keys[j]
            parent.values[j + 1] = parent.values[j]

        # Move median key to parent
        parent.keys[index] = child.keys[t - 1]
        parent.values[index] = child.values[t - 1]
        parent.num_keys += 1
        
        child.keys[t - 1] = 0
        child.values[t - 1] = 0

        self.write_node(child)
        self.write_node(z)
        self.write_node(parent)

    def insert_non_full_iterative(self, curr, key, value):
        # Iterative approach avoids stack buildup
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
                
                # Move down to child, releasing 'curr' from memory
                curr = child 

    def traverse(self, node_id, callback):
        # Iterative In-Order Traversal using Stack of IDs
        if node_id == 0: return
        stack = [] # Stores (block_id, index_of_child_processed)
        curr_id = node_id
        
        while curr_id != 0 or stack:
            if curr_id != 0:
                stack.append((curr_id, 0)) 
                # Peek to check leaf status
                node = self.read_node(curr_id)
                curr_id = node.children[0] if not node.is_leaf else 0
            else:
                parent_id, idx = stack.pop()
                node = self.read_node(parent_id)
                
                if idx < node.num_keys:
                    callback(node.keys[idx], node.values[idx])
                    # After printing key[idx], we need to visit child[idx+1]
                    stack.append((parent_id, idx + 1))
                    if not node.is_leaf:
                        curr_id = node.children[idx + 1]

# --- CLI Handlers ---

def cmd_create(args):
    if len(args) != 2:
        print("Usage: project3 create <filename>")
        return
    idx = IndexFile(args[1], mode='create')
    idx.close()

def cmd_insert(args):
    if len(args) != 4:
        print("Usage: project3 insert <filename> <key> <value>")
        return
    idx = IndexFile(args[1])
    try:
        key, val = int(args[2]), int(args[3])
        idx.insert(key, val)
    except ValueError:
        print("Error: Key and Value must be integers.")
    finally:
        idx.close()

def cmd_search(args):
    if len(args) != 3:
        print("Usage: project3 search <filename> <key>")
        return
    idx = IndexFile(args[1])
    try:
        result = idx.search(int(args[2]))
        if result: print(f"{result[0]} {result[1]}")
        else: print("Error: Key not found.")
    except ValueError:
        print("Error: Key must be integer.")
    finally:
        idx.close()

def cmd_load(args):
    if len(args) != 3:
        print("Usage: project3 load <filename> <csv_file>")
        return
    if not os.path.exists(args[2]):
        print(f"Error: File {args[2]} does not exist.")
        return
    idx = IndexFile(args[1])
    try:
        with open(args[2], 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    idx.insert(int(row[0]), int(row[1]))
    except ValueError:
        print("Error: CSV must contain integers.")
    finally:
        idx.close()

def cmd_print(args):
    if len(args) != 2:
        print("Usage: project3 print <filename>")
        return
    idx = IndexFile(args[1])
    idx.traverse(idx.root_id, lambda k, v: print(f"{k} {v}"))
    idx.close()

def cmd_extract(args):
    if len(args) != 3:
        print("Usage: project3 extract <filename> <output_csv>")
        return
    if os.path.exists(args[2]):
        print(f"Error: File {args[2]} already exists.")
        return
    idx = IndexFile(args[1])
    try:
        with open(args[2], 'w', newline='') as f:
            writer = csv.writer(f)
            idx.traverse(idx.root_id, lambda k, v: writer.writerow([k, v]))
    finally:
        idx.close()

def main():
    if len(sys.argv) < 2:
        print("Usage: project3 <command> [args...]")
        return
    command = sys.argv[1].lower()
    commands = {'create': cmd_create, 'insert': cmd_insert, 'search': cmd_search, 
                'load': cmd_load, 'print': cmd_print, 'extract': cmd_extract}
    if command in commands:
        commands[command](sys.argv[1:])
    else:
        print(f"Error: Unknown command '{command}'")

if __name__ == "__main__":
    main()