# =============================================================================
# Copyright [2013] [cloudnull]
# License Information :
# This software has no warranty, it is provided 'as is'. It is your
# responsibility to validate the behavior of the routines and its accuracy
# using the code provided. Consult the GNU General Public license for further
# details (see GNU General Public License).
# http://www.gnu.org/licenses/gpl.html
# =============================================================================

import inspect
import multiprocessing
import Queue
import sys
import time

import skylab as sk


def basic_queue(iters=None):
    """Uses a manager Queue, from multiprocessing.

    All jobs will be added to the queue for processing.
    :param iters:
    """

    worker_q = multiprocessing.Queue()
    if iters is not None:
        for _dt in iters:
            worker_q.put(_dt)
    return worker_q


def get_from_q(queue):
    """Returns the file or a sentinel value.

    :param queue:
    :return item|None:
    """

    try:
        wfile = queue.get(timeout=5)
    except Queue.Empty:
        return None
    else:
        return wfile


def worker_proc(kwargs, threads=10):
    """Requires the job_action and num_jobs variables for functionality.

    All threads produced by the worker are limited by the number of concurrency
    specified by the user. The Threads are all made active prior to them
    processing jobs.
    """

    jobs = [multiprocessing.Process(target=doerator,
                                    args=tuple([kwargs]))
            for _ in xrange(threads)]

    join_jobs = []
    for _job in jobs:
        time.sleep(.1)
        join_jobs.append(_job)
        _job.start()

    for job in join_jobs:
        job.join()


def doerator(kwargs):
    """Do Jobs until done."""

    while True:
        # Get the file that we want to work with
        queue = kwargs.get('queue')
        job_action = kwargs.get('job_action')

        target = get_from_q(queue=queue)

        # If Work is None return None
        if target is None:
            break
        else:
            kwargs['target'] = target

        job_kwargs = {}
        for kwarg in inspect.getargspec(job_action).args:
            if kwarg in kwargs:
                job_kwargs[kwarg] = kwargs[kwarg]

        # Do the job that was provided
        job_action(**job_kwargs)


def retryloop(attempts, timeout=None, delay=None, backoff=1):
    """Enter the amount of retries you want to perform.

    The timeout allows the application to quit on "X".
    delay allows the loop to wait on fail. Useful for making REST calls.

    ACTIVE STATE retry loop
    http://code.activestate.com/recipes/578163-retry-loop/

    Example:
        Function for retring an action.
        for retry in retryloop(attempts=10, timeout=30, delay=1, backoff=1):
            something
            if somecondition:
                retry()

    :param attempts:
    :param timeout:
    :param delay:
    :param backoff:
    """

    starttime = time.time()
    success = set()
    for _ in range(attempts):
        success.add(True)
        yield success.clear

        if success:
            return

        duration = time.time() - starttime
        if timeout is not None and duration > timeout:
            break

        if delay:
            time.sleep(delay)
            delay *= backoff
    else:
        raise sk.RetryError('Failed to process Job...')


class IndicatorThread(object):
    """Creates a visual indicator while normally performing actions."""

    def __init__(self, work_q=None, system=True, debug=False):
        """System Operations Available on Load.

        :param work_q:
        :param system:
        """

        self.debug = debug
        self.work_q = work_q
        self.system = system
        self.job = None

    def __enter__(self):
        if self.debug is False:
            self.indicator_thread()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.debug is False:
            self.job.terminate()
            print('Done.')

    def indicator(self):
        """Produce the spinner."""

        while self.system:
            busy_chars = ['|', '/', '-', '\\']
            for bc in busy_chars:
                # Fixes Errors with OS X due to no sem_getvalue support
                if self.work_q is not None:
                    if not sys.platform.startswith('darwin'):
                        size = self.work_q.qsize()
                        if size > 0:
                            note = 'Number of Jobs in Queue = %s ' % size
                        else:
                            note = 'Please Wait... '
                    else:
                        note = 'Please Wait... '
                else:
                    note = 'Please Wait... '

                sys.stdout.write('\rProcessing - [ %s ] - %s' % (bc, note))
                sys.stdout.flush()

                time.sleep(.1)
                self.system = self.system

    def indicator_thread(self):
        """indicate that we are performing work in a thread."""

        self.job = multiprocessing.Process(target=self.indicator)
        self.job.start()
        return self.job
