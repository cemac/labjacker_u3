# -*- coding: utf-8 -*-
"""
dummy U3 class for testing
"""

import random

class U3(object):
    """
    U3 device
    """
    def __init__(self, autoOpen=True, dev_connected=True):
        if not dev_connected:
            raise Exception
        self.device_properties = {
            'FirmwareVersion': '1.46',
            'BootloaderVersion': '0.27',
            'HardwareVersion': '1.30',
            'SerialNumber': 320048582,
            'ProductID': 3,
            'LocalID': 1,
            'TimerCounterMask': 64,
            'FIOAnalog': 15,
            'FIODirection': 0,
            'FIOState': 240,
            'EIOAnalog': 0,
            'EIODirection': 0,
            'EIOState': 255,
            'CIODirection': 0,
            'CIOState': 15,
            'DAC1Enable': 1,
            'DAC0': 0,
            'DAC1': 0,
            'TimerClockConfig': 2,
            'TimerClockDivisor': 256,
            'CompatibilityOptions': 0,
            'VersionInfo': 18,
            'DeviceName': 'U3-HV'
        }
        self.fio_state = {
            1: 1,
            2: 1,
            3: 1,
            4: 1,
            5: 1,
            6: 1,
            7: 1,
            8: 1
        }

    def __repr__(self):
        sn = self.device_properties['SerialNumber']
        rep = '<U3 device, serial number: {0}>'.format(sn)
        return rep

    @staticmethod
    def open():
        return True

    @staticmethod
    def close():
        return True

    def configU3(self):
        return self.device_properties

    @staticmethod
    def getAIN(ain_id):
        ain_value = random.uniform(0.0, 5.0)
        return ain_value

    def getFIOState(self, fio_id):
        return self.fio_state[fio_id]

    def setFIOState(self, fio_id, state):
        self.fio_state[fio_id] = state

    @staticmethod
    def getTemperature():
        temp_value = random.uniform(295.0, 305.0)
        return temp_value
