#http://ipython.org/ipython-doc/3/development/messaging.html
#http://pydoc.net/Python/magni/1.4.0/magni.tests.ipynb_examples/

"""..
    Copyright (c) 2014-2016, Magni developers.
    All rights reserved.
    See LICENSE.rst for further information.

Module for wrapping the Magni IPython Notebook examples.

**This module is based on the "ipnbdoctest.py" script by Benjamin
Ragan-Kelley (MinRK)**, source: https://gist.github.com/minrk/2620735.

This assumes comparison of IPython Notebooks in nbformat.v3

"""

from __future__ import division, print_function
import base64
import contextlib
from datetime import datetime
from distutils.version import StrictVersion
import os
import shutil
import subprocess
import unittest
import types
import warnings
try:
    from Queue import Empty  # Python 2
except ImportError:
    from queue import Empty  # Python 3
try:
    from StringIO import StringIO as BytesIO  # Python 2
except ImportError:
    from io import BytesIO  # Python 3

#import numpy as np
#import scipy.misc

#import magni

# The great "support IPython 2, 3, 4" strat begins
try:
    import jupyter
except ImportError:
    jupyter_era = False
else:
    jupyter_era = True

if jupyter_era:
    # Jupyter / IPython 4.x
    from jupyter_client import KernelManager
    from nbformat import reads, NotebookNode

    def mod_reads(file_):
        return reads(file_, 3)  # Read notebooks as v3

else:
    from IPython.kernel import KernelManager
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        try:
            # IPython 2.x
            from IPython.nbformat.current import reads, NotebookNode

            def mod_reads(file_):
                return reads(file_, 'json')

        except UserWarning:
            # IPython 3.x
            from IPython.nbformat import reads, NotebookNode

            def mod_reads(file_):
                return reads(file_, 3)  # Read notebooks as v3

# End of the great "support IPython 2, 3, 4" strat

# Test for freetype library version
try:
    if StrictVersion(
            subprocess.check_output(
                ['freetype-config', '--ftversion']).decode().strip()
            ) <= StrictVersion('2.5.2'):
        _skip_display_data_tests = False
    else:
        _skip_display_data_tests = True
except OSError:
    _skip_display_data_tests = True

if _skip_display_data_tests:
    warnings.warn('Skipping display data ipynb tests.', RuntimeWarning)

def _check_ipynb():
    kernel_manager = KernelManager()
    kernel_manager.start_kernel()
    kernel_client = kernel_manager.client()
    kernel_client.start_channels()

    try:
        # IPython 3.x
        kernel_client.wait_for_ready()
        iopub = kernel_client
        shell = kernel_client
    except AttributeError:
        # Ipython 2.x
        # Based on https://github.com/paulgb/runipy/pull/49/files
        iopub = kernel_client.iopub_channel
        shell = kernel_client.shell_channel
        shell.get_shell_msg = shell.get_msg
        iopub.get_iopub_msg = iopub.get_msg

    successes = 0
    failures = 0
    errors = 0

    report = ''
    _execute_cell("print('Hello World')", shell, iopub, timeout=1)

    kernel_client.stop_channels()
    kernel_manager.shutdown_kernel()

    passed = not (failures or errors)

    print(report)

def _execute_cell(code, shell, iopub, timeout=300):
    """
    Execute an IPython Notebook Cell and return the cell output.

    Parameters
    ----------
    cell : str
        The code to be executed in a python kernel
    shell : IPython.kernel.blocking.channels.BlockingShellChannel
        The shell channel which the cell is submitted to for execution.
    iopub : IPython.kernel.blocking.channels.BlockingIOPubChannel
        The iopub channel used to retrieve the result of the execution.
    timeout : int
        The number of seconds to wait for the execution to finish before giving
        up.

    Returns
    -------
    cell_outputs : list
        The list of NotebookNodes holding the result of the execution.

    """

    # Execute input
    #shell.execute("10+20")
    shell.execute("import time\ntime.sleep(10)\nprint(112341234)")
    shell.execute("1+2")

    cell_outputs = list()

    # Poll for iopub messages until no more messages are available
    while True:
        try:
            exe_result = shell.get_shell_msg(timeout=timeout)
            print('exe_result')
            print(exe_result)
            print('')
            if exe_result['content']['status'] == 'error':
                print('-----------------------crap---------------------')
                raise RuntimeError('Failed to execute cell due to error: {!r}'.format(
                    str(exe_result['content']['evalue'])))
        except Empty:
            print('quue empty, try again')
            pass

        print('\n\n-------------------------------------------------\ntrying\n----------------------------------\n')
        try:
            msg = iopub.get_iopub_msg(timeout=0.5)
            print('get_iopub_msg')
            print('msg')
            print(msg)
            print('')
        except Empty:
            print('get_iopub_msg is empty--------------------------------------')
            pass

        msg_type = msg['msg_type']
        if msg_type in ('status', 'pyin', 'execute_input', 'execute_result'):
            continue

        content = msg['content']
        node = NotebookNode(output_type=msg_type)

        if msg_type == 'stream':
            node.stream = content['name']
            if 'text' in content:
                # v4 notebook format
                node.text = content['text']
            else:
                # v3 notebook format
                node.text = content['data']
        elif msg_type in ('display_data', 'pyout'):
            node['metadata'] = content['metadata']
            for mime, data in content['data'].items():
                attr = mime.split('/')[-1].lower()
                attr = attr.replace('+xml', '').replace('plain', 'text')
                setattr(node, attr, data)
            if msg_type == 'pyout':
                node.prompt_number = content['execution_count']
        elif msg_type == 'pyerr':
            node.ename = content['ename']
            node.evalue = content['evalue']
            node.traceback = content['traceback']
        else:
            raise RuntimeError('Unhandled iopub message of type: {}'.format(
                msg_type))

        cell_outputs.append(node)

    return cell_outputs

_check_ipynb()