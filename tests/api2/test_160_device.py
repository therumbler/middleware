#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST
from auto_config import ha, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')
global all_results
all_results = {}
disk_list = list(POST('/device/get_info/', 'DISK', controller_a=ha).json().keys())


@pytest.mark.parametrize('dtype', ['SERIAL', 'DISK'])
def test_01_get_device_info(dtype):
    results = POST('/device/get_info/', dtype)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), (list, dict)) is True, results.text
    global all_results
    all_results[dtype] = results


def test_02_look_at_device_serial():
    results = all_results['SERIAL']
    assert results.json()[0]['drivername'] == 'uart', results.text
    assert results.json()[1]['drivername'] == 'uart', results.text


@pytest.mark.parametrize('disk', disk_list)
def test_03_look_at_device_disk(disk):
    results = all_results['DISK']
    assert results.json()[disk]['name'] == disk, results.text
