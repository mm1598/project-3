###############################################################################
# Project 3: Index Manager (B-Tree)
# Name:   Marc Manoj
# NetID:  MMM220012
# Class:  CS4348 - Operating Systems Concepts
# Date:   Fall 2025
###############################################################################

-------------------------------------------------------------------------------
1. DESCRIPTION
-------------------------------------------------------------------------------
This program implements an interactive B-Tree index manager. It stores key/value
pairs in a binary file using a strict B-Tree structure (Degree t=10).

The program manages the index file in 512-byte blocks and ensures that no more
than 3 nodes are ever loaded into memory simultaneously, adhering to strict
memory constraints.

Features:
- Create new index files with a valid header.
- Insert key/value pairs (unsigned integers).
- Search for existing keys.
- Print all keys in the index (in-order traversal).
- Load/Extract data to and from CSV files.

-------------------------------------------------------------------------------
2. REQUIREMENTS & ENVIRONMENT
-------------------------------------------------------------------------------
- Language: Python 3.x
- Dependencies: Standard Library only (struct, sys, os, csv)
- OS: Compatible with Linux, macOS, and Windows.

-------------------------------------------------------------------------------
3. HOW TO RUN
-------------------------------------------------------------------------------
The program is a single file script: `project3.py`.

Execution Method 1 (Standard Python):
   $ python3 project3.py <command> [arguments]

Execution Method 2 (Executable Script on Linux/Mac):
   $ chmod +x project3.py
   $ ./project3.py <command> [arguments]

-------------------------------------------------------------------------------
4. COMMAND USAGE
-------------------------------------------------------------------------------
All commands are case-insensitive.

1. CREATE a new index file:
   Usage: project3 create <index_filename>
   Example: python3 project3.py create test.idx

2. INSERT a key/value pair:
   Usage: project3 insert <index_filename> <key> <value>
   Note: Key and Value must be unsigned integers.
   Example: python3 project3.py insert test.idx 15 100

3. SEARCH for a key:
   Usage: project3 search <index_filename> <key>
   Example: python3 project3.py search test.idx 15
   Output: Prints "Key Value" if found, or an error message.

4. PRINT all entries:
   Usage: project3 print <index_filename>
   Example: python3 project3.py print test.idx
   Output: Prints all key/value pairs in increasing order.

5. LOAD from CSV:
   Usage: project3 load <index_filename> <input_csv>
   Example: python3 project3.py load test.idx input.csv

6. EXTRACT to CSV:
   Usage: project3 extract <index_filename> <output_csv>
   Example: python3 project3.py extract test.idx output.csv

-------------------------------------------------------------------------------
5. DESIGN & IMPLEMENTATION NOTES
-------------------------------------------------------------------------------
This implementation strictly follows the Project 3 specifications:

A. FILE FORMAT:
   - [cite_start]Block Size: 512 bytes[cite: 50].
   - [cite_start]Byte Order: Big-Endian for all integers[cite: 56].
   - [cite_start]Magic Number: b'4348PRJ3' stored in the header[cite: 75].

B. B-TREE PROPERTIES:
   - Degree (t): 10.
   - Max Keys per Node: 19 (2t - 1).
   - Max Children per Node: 20 (2t).

C. MEMORY MANAGEMENT (CRITICAL):
   - [cite_start]The requirement "never have more than 3 nodes in memory" [cite: 13] is met
     by avoiding recursion for complex operations.
   - The `insert` and `split` logic is iterative or carefully scoped to only
     hold references to `parent`, `child`, and `new_child` nodes at any one time.
   - Traversal (Print/Extract) uses an iterative stack-based approach storing
     only Block IDs, loading nodes one by one to ensure strictly minimal memory usage.