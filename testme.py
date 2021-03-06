import subprocess
import telnetlib
import time
import traceback
import os
import sys

TEST_PORT = 1234

# These values control how many times the test client will try to connect to the server before giving up.
# The server takes time to start up, and the easiest way to account for that is just keep trying to connect for it a little bit until we get a link.
CONNECT_TRY_SLEEP_INTERVAL = 0.2
CONNECT_TRIES = 5

# (https://stackoverflow.com/questions/287871/print-in-terminal-with-colors)
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def run_test(filename):
    svr = subprocess.Popen(['python3', 'mica', '--port', str(TEST_PORT), '--print-io', ':memory:'])
    time.sleep(0.1)
    assert svr.poll() is None

    # Try to connect for a bit, but give up eventually.
    tries = CONNECT_TRIES
    while True:
        try:
            t = telnetlib.Telnet()
            t.open("localhost", TEST_PORT)
            break
        except ConnectionRefusedError:
            time.sleep(CONNECT_TRY_SLEEP_INTERVAL)
            tries -= 1
            if tries == 0:
                svr.kill()
                raise

    # Read in the test, write the '>'-prefixed commands to the server, and check that we receive something that equals any line that isn't '>'-prefixed before continuing.
    try:
        with open(filename, 'r') as file:
            for line in file.readlines():
                line = line.strip()
                if len(line) < 1:
                    continue
                if line[0] == '>':
                    # It's a good idea to consume old data that might be left in the buffer before we do anything. This ensures that a previous command's output won't be tested against what's expected from the most recent command.
                    t.read_very_eager()
                    t.write(line[1:].encode("utf-8") + b'\n')
                else:
                    line = line.encode("utf-8")
                    results = t.read_until(line, 1.0)
                    if line not in results:
                        print("test> expected %s, got %s" % (repr(line), repr(results)))
                        t.close()
                        svr.kill()
                        time.sleep(0.1)
                        return (False, "%s != %s" % (repr(line), repr(results)))
    except:
        print("test> unhandled exception...")
        t.close()
        svr.kill()
        print(traceback.format_exc(chain=True))
        return (False, "Exception in test framework")

    # Try to tear things down gracefully.
    # Sometimes this doesn't work and you're left with a hanging process. :/
    t.close()
    svr.kill()
    return (True, None)

def files(dir):
    # https://stackoverflow.com/questions/3207219/how-do-i-list-all-files-of-a-directory
    return [f for f in os.listdir(dir) if os.path.isfile(os.path.join(dir, f))]

results = {}

if len(sys.argv) > 1:
    to_run = sys.argv[1:]
else:
    to_run = [os.path.join("tests", x) for x in files("tests")]

for file in to_run:
    if os.path.exists(file) and os.path.isfile(file):
        results[file] = run_test(file)
    else:
        print("File not found, or is a directory: %s" % file)
        results[file] = (False, "file not found")
    print()

print("FINAL RESULTS:\n--------------")
for (filename, r) in results.items():
    (status, msg) = r
    if status:
        print(("%s> " + bcolors.OKGREEN + "OK" + bcolors.ENDC) % filename)
    else:
        print(("%s> " + bcolors.FAIL + "NOT OK" + bcolors.ENDC + " (%s)") % (filename, msg))
