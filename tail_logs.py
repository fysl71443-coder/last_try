#!/usr/bin/env python3
"""
Tail the local error log with optional follow mode
Usage:
  python tail_logs.py              # show last 200 lines
  python tail_logs.py -n 400       # show last 400 lines
  python tail_logs.py -f           # follow (like tail -f)
"""
import argparse
import os
import sys
import time

LOG_PATH = os.path.join('logs', 'local-errors.log')

def read_last_lines(path, n=200):
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = -1024
            data = b''
            while n > 0 and -block < size:
                f.seek(block, os.SEEK_END)
                data = f.read(-block) + data
                n -= data.count(b'\n')
                block *= 2
            return b"\n".join(data.splitlines()[-n:]).decode('utf-8', errors='replace')
    except FileNotFoundError:
        return f"Log file not found: {path}"
    except Exception as e:
        return f"Error reading log: {e}"

def follow(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                sys.stdout.write(line)
                sys.stdout.flush()
    except FileNotFoundError:
        print(f"Log file not found: {path}")
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', type=int, default=200)
    parser.add_argument('-f', action='store_true')
    args = parser.parse_args()
    if args.f:
        follow(LOG_PATH)
    else:
        print(read_last_lines(LOG_PATH, args.n))

