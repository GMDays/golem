# TestSession
class TestSession:
    def __init__(self, opts, script):
        self.step = -1
        self.script = script
        self._opts = opts
        self._last_step = len(script)

        self._proc_tester = []
        self._expect_lines = []
        self.log = []

        self.next_step()
        print('DEBUG: Test session created')

    def tick(self):
        ticks = len(self._proc_tester)
        channel = 0

        while channel < ticks:

            exit_code, tmp_err, tmp_out = self._proc_tester[channel].tick()
            print('DEBUG: Got lines: err=' + str(len(tmp_err)) + ' out=' + str(len(tmp_out)) + ', code='+str(exit_code))
            # expect stuff
            self._expect_lines[channel].feed(tmp_err, tmp_out)
            # store stuff
            _log = self.log[channel][self.step]
            _log.err += tmp_err
            _log.out += tmp_out
            _log.exit_code = exit_code
            self.test_step(channel)
            channel += 1
        return exit_code

    def test_step(self, channel):
        print('DEBUG: test_step()')
        _step = self.script[self.step]
        _log = self.log[channel][self.step]
        _expect_lines = self._expect_lines[channel]

        if _step['done'] == 'err':
            print('DEBUG: Testing err...')
            print('DEBUG: ' + str(len(_expect_lines.exp_err)))
            print('DEBUG: ' + str(_expect_lines.check_err_exp))
            if len(_expect_lines.exp_err) == _expect_lines.check_err_exp:
                print('DEBUG: Expected err matches, next step')
                self.next_step()
            else:
                print('DEBUG: Not all lines are found yet, waiting...')

        elif _step['done'] == 'out':
            print('DEBUG: Testing out...')
            print('DEBUG: ' + str(len(_expect_lines.exp_out)))
            print('DEBUG: ' + str(_expect_lines.check_out_exp))
            if len(_expect_lines.exp_out) == _expect_lines.check_out_exp:
                print('DEBUG: Expected out matches, next step')
                self.next_step()
            else:
                print('DEBUG: Not all lines are found yet, waiting...')

        elif _step['done'][:4] == 'exit':
            print('DEBUG: Testing exit...')
            if _log.exit_code is None:
                print('DEBUG: No exit yet, waiting...')
            elif _log.exit_code == int(_step['done'][1:0]):
                print('DEBUG: Exit code matches, next step')
                self.next_step()
            else:
                print('F: Exit code does not match expected for this step')


    def next_step(self):
        print('DEBUG: next_step() ' + str(self.step))
        if self._last_step <= self.step + 1:
            print('DEBUG: No more steps')
            return
        # Increment the step
        self.step += 1
        _step = self.script[self.step]
        channel = int(_step['channel']) if 'channel' in _step else 0

        # Create new instance of test_log
        if len(self.log) < channel + 1:
            self.log.append([])
        self.log[channel].append(TestLog())
        print('DEBUG: updated step to ' + str(self.step))

        if _step['type'] == 'cmd':
            # TODO: ensure channel no is correct
            self._proc_tester.append(ProcTester(self._opts, _step['cmd']))
            self._expect_lines.append(ExpectLines(_step['err'], _step['out']))
        elif _step['type'] == 'signal':
            if self._proc_tester[channel] is None:
                raise "Can not send signal when there is no proc_tester"

            self._expect_lines[channel] = ExpectLines(_step['err'], _step['out'])
            self._proc_tester[channel].signal(int(_step['signal']))


    def report(self):
        print('DEBUG: report()')
        ticks = len(self._expect_lines)
        channel = 0

        result = []

        while channel < ticks:
            self._expect_lines[channel].report()

            _log = self.log[channel][self.step]
            log_err = _log.err
            log_out = _log.out

            print("DEBUG: OUT:" + str(len(log_out)))
            print(log_out)
            print("DEBUG: ERR:" + str(len(log_err)))
            print(log_err)
            result.append( (_log.exit_code, log_err, log_out) )
            channel += 1

        return result

    def quit(self):
        ticks = len(self._proc_tester)
        channel = 0

        while channel < ticks:
            self._proc_tester[channel].quit()
            channel += 1

class TestLog:
    def __init__(self):
        self.err = []
        self.out = []
        self.exit_code = None

# ProcTester
import subprocess
import time

def _clean_line(line):
    print('DEBUG: Clean line=' + line)
    return line.strip()

def _empty_stream(_out, _in):
    #print('DEBUG: _empty_stream() START')
    line = _in.readline(0.1)
    while line and len(line) > 0:
        #print('DEBUG: _empty_stream() loop: ' + line)
        _out.append(_clean_line(line))
        line = _in.readline(0.1)
    #print('DEBUG: _empty_stream() END')

class ProcTester:

    def __init__(self, opts, args):
        try:
            self.proc = subprocess.Popen(
                args,
                bufsize=1,
                cwd=opts['cwd'],
                universal_newlines=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)

            self.out = NonBlockingStreamReader(self.proc.stdout)
            self.err = NonBlockingStreamReader(self.proc.stderr)
        except Exception as e:
            print("ERROR" + str(e))

    def tick(self):
        log_err = []
        log_out = []

        # streams to logs
        _empty_stream(log_err, self.err)
        _empty_stream(log_out, self.out)

        exit_code = self.proc.poll()
        return exit_code, log_err, log_out

    def signal(self, signal):
        self.proc.send_signal(signal)

    def quit(self):
        self.out.quit()
        self.err.quit()
        self.proc.kill()

# ExpectLines
class ExpectLines:

    def __init__(self, err, out):
        self.exp_err = err
        self.exp_out = out

        self.check_err_exp = 0
        self.check_out_exp = 0

    def feed(self, log_err, log_out):
        print('DEBUG: feed()')

        self.check_err_log = 0
        self.check_out_log = 0

        while len(log_err) > self.check_err_log and len(self.exp_err) > self.check_err_exp:
            if self.exp_err:
                cur_err = log_err[self.check_err_log]
                print("DEBUG: compare")
                print(cur_err)
                print(self.exp_err[self.check_err_exp])
                if cur_err == self.exp_err[self.check_err_exp]:
                    # foundd expected line
                    self.check_err_exp+=1
            self.check_err_log+=1

        while len(log_out) > self.check_out_log and len(self.exp_out) > self.check_out_exp:
            # print("DEBUG: Checking log line: " + str(self.check_out_log))
            if self.exp_out:
                cur_out = log_out[self.check_out_log]
                print("DEBUG: compare")
                print(cur_out)
                print(self.exp_out[self.check_out_exp])
                if cur_out == self.exp_out[self.check_out_exp]:
                    # foundd expected line
                    print("P: Found match '{}'".format(cur_out))
                    self.check_out_exp+=1
            self.check_out_log+=1

    def report(self):
        assert self.check_out_exp == len(self.exp_out)
        print("P: All expected out lines have been found")

        assert self.check_err_exp == len(self.exp_err)
        print("P: All expected err lines have been found")

from threading import Thread
from queue import Queue, Empty

class NonBlockingStreamReader:

    def __init__(self, stream):
        '''
        stream: the stream to read from.
                Usually a process' stdout or stderr.
        '''

        self._s = stream
        self._q = Queue()

        def _populateQueue(stream, queue):
            '''
            Collect lines from 'stream' and put them in 'quque'.
            '''

            while True:
                line = stream.readline()
                if line:
                    queue.put(line)
                else:
                    raise UnexpectedEndOfStream

        self._t = Thread(target = _populateQueue,
                args = (self._s, self._q))
        self._t.daemon = True
        self._t.start() #start collecting lines from the stream

    def readline(self, timeout = None):
        try:
            return self._q.get(block = timeout is not None,
                    timeout = timeout)
        except Empty:
            return None

    def quit(self):
        # TODO: stop thread cleanly?
        # self._t.stop()
        print('DEBUG: Not implemented yet')

class UnexpectedEndOfStream(Exception): pass

from unittest import TestCase

class CleanupFixture(TestCase):
    def __init__(self, *args, **kwargs):
        self._tests = []
        super().__init__(*args, **kwargs)

    def tearDown(self):
        for test in self._tests:
            test.quit()