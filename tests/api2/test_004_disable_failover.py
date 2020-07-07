#!/usr/bin/env python3

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST
from auto_config import ha

pytestmark = pytest.mark.skipif(not ha, reason="Skipping test for Core and Scale")


def test_01_disable_failover():
    payload = {
        "disabled": True
    }
    results = POST('/failover/', payload, controller_a=ha)
    assert results.status_code == 200, results.text
