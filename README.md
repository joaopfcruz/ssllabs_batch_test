# ssllabs_batch_test
A simple script to test a list of domains using SSLLabs API

Takes a file with a list of domains (one per line) and outputs a .json file per domain with the results from SSLLabs.

% python3 ssllabs_batch_test.py -h
Usage: ssllabs_batch_test.py [options]

Options:
  -h, --help  show this help message and exit
  -l IN_FILE  File with a list of endpoints to test
  -q          Quiet mode (don't output to stdout)
  -v          Verbose (debug) mode
  
  
Example:
% python3 ssllabs_batch_test.py -l list.txt
