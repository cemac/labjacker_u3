# -*- coding: utf-8 -*-
"""
LabJacker U3

QT UI application to connect to U3 device and run a specific sequence of
commands.

U3 status is periodically logged to the specified log filewhere required.
"""

# Standard lib imports:
import datetime
import os
import re
import sys
import time
# Third party imports:
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QApplication, QFileDialog, QFrame, QGridLayout,
                             QInputDialog, QLabel, QMessageBox, QPushButton,
                             QTextEdit, QVBoxLayout, QWidget)
import u3

# App name and version:
APP_NAME = 'LabJacker U3'
APP_VERSION = '0.0.1'

def connect_u3():
    """
    connect_u3

    Function to connection to LabJack U3 device.
    This will return the U3() object if successful, otherwise None will be
    returned
    """
    # Try to connect to the U3 device:
    try:
        u3_dev = u3.U3()
    # If that fails ... :
    except:
        # Create an alert window:
        alert = QMessageBox()
        alert.setWindowTitle(APP_NAME)
        alert.setText('Failed to connect to U3 device')
        alert.exec_()
        # Set u3_dev to None:
        u3_dev = None
    # Return u3_dev:
    return u3_dev

def get_calibration(config_dir=None, config_file='calibration.txt'):
    """
    get_calibration

    Read in calibration values from configuration file
    Returns a dict of values if successful, else returns None
    """
    # Expect to find calibration in same directory as executable, if no
    # config_dir is specified:
    if not config_dir:
        config_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
    # Full path to config file:
    config_path = os.path.sep.join([config_dir, config_file])
    # Check config file exists:
    if not os.path.exists(config_path):
        return None
    # Init calibration dict:
    calibration = {}
    # Try to read config file:
    try:
        with open(config_path, 'r') as cf:
            for cl in cf.readlines():
                if re.match(r'^\s?p\s?=\s?', cl):
                    calibration['pres'] = cl.split('=')[1].strip()
    except:
        return None
    # Return the calibration:
    return calibration

class LabJackerSeq(QThread):
    """
    LabJackerSeq

    Qthread class used to define and run a sequence of events
    """
    # Signals used by this class ...
    # Log file selecting / setting:
    set_log_file = pyqtSignal()
    # Sample name setting:
    set_sample_name = pyqtSignal()
    # Sequence step interval setting:
    set_seq_int = pyqtSignal()
    # Sequence loop count setting:
    set_loop_count = pyqtSignal()
    # State logging:
    log_state = pyqtSignal(str)
    # Toggle FIO state:
    toggle_fio = pyqtSignal(int)
    # Toggle run state:
    toggle_run = pyqtSignal(bool)
    # Log a message:
    log_msg = pyqtSignal(str)
    # Display an alert:
    display_alert = pyqtSignal(str)

    def __init__(self, io_labels, io_states, status):
        # Init QThread first:
        QThread.__init__(self)
        # Init quit state to False:
        self.quit = False
        # Date format used for logging:
        self.date_format = '%Y-%m-%d %H:%M:%S'
        # Get the IO labels and states information:
        self.io_labels = io_labels
        self.io_states = io_states
        # Device status:
        self.status = status
        # Sequence log file:
        self.log_file = None
        # Sequence sample name:
        self.sample_name = None
        # Sequence step interval:
        self.seq_int = None
        # Sequence loop count:
        self.loop_count = None
        # Required initial conditions for sequence to run:
        self.init_cond = {
            'fio4': 1,
            'fio5': 1,
            'fio6': 1,
            'fio7': 1
        }
        # The sequence to run. Iinit as None:
        self.seq = None

    def get_timestamp(self):
        """
        get_timestamp

        Get the current time and return in required format
        """
        # Get the current datetime:
        current_date = datetime.datetime.now()
        # Format as defined in self.date_format:
        date_str = datetime.datetime.strftime(current_date, self.date_format)
        # Return the formatted date:
        return date_str

    def run_command(self, command):
        """
        run_command

        Run a command in the sequence
        """
        # If we are not quitting:
        if not self.quit:
            # Command is first element:
            seq_cmd = command[0]
            # Log message is second element:
            seq_msg = command[1]
            # Whether the state should be logged to file at this point:
            log_state = command[2]
            # Get the current timestamp:
            seq_time = self.get_timestamp()
            # Create and display log meesage:
            log_msg = '{0} : {1}'.format(seq_time, seq_msg)
            self.log_msg.emit(log_msg)
            # If the state should be logged to file, log before changing
            # things ... :
            if log_state:
                # Log the state to file:
                self.log_state.emit(seq_time)
            # Use eval() to run the command:
            eval(seq_cmd)

    def display_state_error(self):
        """
        display_state_error

        If the current state does not match the required initial state,
        display an alert
        """
        # Init a list for storing required state information:
        req_state = []
        # For each element in required initial state:
        for i in self.init_cond:
            # Get the friendly labels for the IO port and state:
            fio_label = self.io_labels[i]
            fio_init_cond = self.init_cond[i]
            fio_req_state = self.io_states[i][fio_init_cond]
            # Add to list:
            req_state.append('  {0} : {1}'.format(fio_label, fio_req_state))
        # Join the states with line breaks:
        req_state_txt = '\n'.join(req_state)
        # Create the alert message:
        alert_msg = 'Required initial state:    \n\n{0}'.format(req_state_txt)
        # Emit the alert message:
        self.display_alert.emit(alert_msg)

    def check_init_state(self):
        """
        check_init_state

        Check the initial device state:
        """
        # Loop through required initial conditions:
        for i in self.init_cond:
            # Get required state and current state:
            req_state = self.init_cond[i]
            cur_state = self.status[i]
            # If required state does not match current state:
            if req_state != cur_state:
                # Stop running the sequence:
                self.toggle_run.emit(True)
                # Display an alert:
                self.display_state_error()
                # Log a message:
                seq_time = self.get_timestamp()
                seq_msg = 'valve states do not match required initial state'
                log_msg = '{0} : {1}'.format(seq_time, seq_msg)
                self.log_msg.emit(log_msg)
                # Return False:
                return False
        # All fine, return True:
        return True

    def set_sequence(self):
        """
        Set up the sequence fo commands to run
        """
        # Define the sequence of events:
        sleep_str = 'time.sleep({0})'.format(self.seq_int)
        wait_str = 'waiting for {0} seconds'.format(self.seq_int)
        self.seq = [
            ['time.sleep(0)', 'sequence starting ...', True],
            ['self.toggle_fio.emit(5)', 'opening valve 2', False],
            ['self.toggle_fio.emit(6)', 'opening valve 3', False],
            ['self.toggle_fio.emit(7)', 'opening valve 4', False],
            [sleep_str, wait_str, False],
            ['self.toggle_fio.emit(5)', 'closing valve 2', True],
            ['self.toggle_fio.emit(7)', 'closing valve 4', False],
            ['self.toggle_fio.emit(4)', 'opening valve 1', False],
            [sleep_str, wait_str, False],
            ['self.toggle_fio.emit(4)', 'closing valve 1', True],
            [sleep_str, wait_str, False],
            ['self.toggle_fio.emit(5)', 'opening valve 2', True],
            [sleep_str, wait_str, False],
            ['self.toggle_fio.emit(7)', 'opening valve 4', True],
            [sleep_str, wait_str, False],
            ['self.toggle_fio.emit(5)', 'closing valve 2', True],
            ['self.toggle_fio.emit(6)', 'closing valve 3', False],
            ['self.toggle_fio.emit(7)', 'closing valve 4', False]
        ]

    def run(self):
        """
        run

        Run the sequence
        """
        # Check initial state meets required initial state:
        if self.check_init_state():
            # Require log file to be selected first:
            self.set_log_file.emit()
            # Wait for log file to be set by user:
            while self.log_file is None:
                time.sleep(0.1)
            # If no log file was selected, give up:
            if not self.log_file:
                self.run_command(['self.toggle_run.emit(True)',
                                  'no output file specified. not starting',
                                  False])
                return
            # Require sample name to be set:
            self.set_sample_name.emit()
            # Wait for log file to be set by user:
            while self.sample_name is None:
                time.sleep(0.1)
            # If no sample name was set, give up:
            if not self.sample_name:
                self.run_command(['self.toggle_run.emit(True)',
                                  'no sample name specified. not starting',
                                  False])
                return
            # Require sequence interval to be set:
            self.set_seq_int.emit()
            # Wait for time step interval to be set by user:
            while self.seq_int is None:
                time.sleep(0.1)
            # If no sequence interval was set, give up:
            if not self.seq_int:
                log_msg = 'no time step interval specified. not starting'
                self.run_command(['self.toggle_run.emit(True)',
                                  log_msg,
                                  False])
                return
            # Require loop count to be set:
            self.set_loop_count.emit()
            # Wait for loop count to be set by user:
            while self.loop_count is None:
                time.sleep(0.1)
            # If no loop count was set, give up:
            if not self.loop_count:
                log_msg = 'no loop count specified. not starting'
                self.run_command(['self.toggle_run.emit(True)',
                                  log_msg,
                                  False])
                return
            # Set up the sequence:
            self.set_sequence()
            # Loop over sequence as many times as required:
            for i in range(self.loop_count):
                # If we are not quitting ... :
                if not self.quit:
                    # Log the loop number:
                    seq_time = self.get_timestamp()
                    seq_msg = 'starting sequence loop {0} of {1}'
                    seq_msg = seq_msg.format(i + 1, self.loop_count)
                    log_msg = '{0} : {1}'.format(seq_time, seq_msg)
                    self.log_msg.emit(log_msg)
                    # Run through the commands in the sequence:
                    for j in self.seq:
                        self.run_command(j)
            # Log completion:
            self.run_command(['self.toggle_run.emit(True)', 'finished', False])

class LabJackerPoll(QThread):
    """
    LabJackerPoll

    Qthread class used for polling LabJack temperature and AIN values.
    """
    # Define signals used to emit instructions to update temperature and AIN
    # information:
    update_temp = pyqtSignal()
    update_ain = pyqtSignal()

    def __init__(self, poll_type='temp', poll_int=0.5):
        # Qthread init:
        QThread.__init__(self)
        # Store information about what is being polled:
        self.poll_type = poll_type
        self.poll_int = poll_int

    def run(self):
        """
        run

        The run method just loops forever emitting the appropriate signal to
        update temperature / AIN information at the requested interval.
        """
        while True:
            if self.poll_type == 'temp':
                self.update_temp.emit()
            elif self.poll_type == 'ain':
                self.update_ain.emit()
            time.sleep(self.poll_int)

class LabJackerUI(QWidget):
    """
    LabJackerUI

    Main QWidget class for the application. Creates the UI, spawns the various
    threads for polling and running the sequence, etc.
    """
    def __init__(self):
        # Run parent init first:
        super().__init__()
        # Defaultr calibration values:
        self.calibration_default = {'pres': '(5.0221 * v) - 24.036'}
        self.calibration = None
        # Set the initial working directory to the user home directory:
        self.working_dir = os.path.expanduser('~')
        # Log file location:
        self.log_file = None
        # Sample name:
        self.sample_name = 'sample_name'
        # Sequence time step interval:
        self.seq_int = 180
        # Sequence loop count:
        self.loop_count = 6
        # Information about the U3 device which is being used:
        self.u3 = {
            'dev': None,
            'connected': False,
            'config': None
        }
        # UI Window properties:
        self.window_properties = {
            'width': 650,
            'height': 600,
            'grid_spacing': 5
        }
        # Labels for the U3 inputs and outputs:
        self.io_labels = {
            'ain0': 'Voltage 0',
            'ain1': 'Voltage 1',
            'vd': 'Voltage Diff',
            'pres': 'Pressure',
            'fio4': 'Valve 1',
            'fio5': 'Valve 2',
            'fio6': 'Valve 3',
            'fio7': 'Valve 4'
        }
        # Friendly labels for the FIO states:
        self.io_states = {
            'fio4' : {
                0 : 'Open',
                1 : 'Closed'
            },
            'fio5' : {
                0 : 'Open',
                1 : 'Closed'
            },
            'fio6' : {
                0 : 'Open',
                1 : 'Closed'
            },
            'fio7' : {
                0 : 'Open',
                1 : 'Closed'
            }
        }
        # Set up the UI layout:
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(self.window_properties['grid_spacing'])
        self.layout.setAlignment(Qt.AlignTop)
        # Define the fonts to use:
        self.fonts = {
            'standard': QFont(),
            'bold': QFont()
        }
        self.fonts['bold'].setBold(True)
        # UI Header area elements:
        self.header_area = {
            'frame': None,
            'grid': None,
            'label': None
        }
        # UI Status area elements:
        self.status_area = {
            'frame': None,
            'grid': None,
            'label_dev': None,
            'value_dev': None,
            'label_sn': None,
            'value_sn': None,
            'label_fw': None,
            'value_fw': None,
            'label_temp': None,
            'value_temp': None,
            'label_ain0': None,
            'value_ain0': None,
            'label_ain1': None,
            'value_ain1': None,
            'label_vd': None,
            'value_vd': None,
            'label_pres': None,
            'value_pres': None
        }
        # UI FIO header area elements:
        self.fio_header_area = {
            'frame': None,
            'grid': None,
            'label': None
        }
        # UI FIO area elements:
        self.fio_area = {
            'frame': None,
            'grid': None,
            'label_fio4': None,
            'value_fio4': None,
            'label_fio5': None,
            'value_fio5': None,
            'label_fio6': None,
            'value_fio6': None,
            'label_fio7': None,
            'value_fio7': None,
        }
        # UI Sequence header area elements:
        self.seq_header_area = {
            'frame': None,
            'grid': None,
            'label': None
        }
        # UI Sequence area elements:
        self.seq_area = {
            'frame': None,
            'grid': None,
            'text': None
        }
        # UI button elements:
        self.buttons = {
            'connect': None,
            'quit': None,
            'fio4': None,
            'fio5': None,
            'fio6': None,
            'fio7': None,
            'clear': None,
            'run': None
        }
        # Current status information:
        self.status = {
            'temp': None,
            'ain0': None,
            'ain1': None,
            'vd': None,
            'pres': None,
            'fio4': None,
            'fio5': None,
            'fio6': None,
            'fio7': None,
            'seq_running': False,
            'seq_thread': None,
            'temp_thread': None,
            'ain_thread': None
        }
        # Try to get calibration values:
        calibration = get_calibration()
        if calibration:
            self.calibration = calibration
        else:
            # Use default values:
            self.calibration = self.calibration_default
        # Init the UI:
        self.init_ui()

    def toggle_connect(self):
        """
        toggle_connect

        Connect / disconnect from U3 device
        """
        # If the device is currently connected ... :
        if self.u3['dev']:
            # Close the device:
            self.u3['dev'].close()
            # Update status information and UI:
            self.u3['dev'] = None
            self.u3['config'] = None
            self.u3['connected'] = False
            self.buttons['connect'].setText('Connect')
            self.status_area['value_dev'].setText('--')
            self.status_area['value_sn'].setText('--')
            self.status_area['value_fw'].setText('--')
            # If a sequence is currently running:
            if self.status['seq_running']:
                # Stop the sequence:
                self.toggle_run()
            # Disable the run button:
            self.buttons['run'].setEnabled(False)
            # Un-check connect button:
            self.buttons['connect'].setChecked(False)
        # Otherwise:
        else:
            # Connect to the U3 device and get the config information:
            self.u3['dev'] = connect_u3()
        # If the device is connected:
        if self.u3['dev']:
            # Gt the device config:
            self.u3['config'] = self.u3['dev'].configU3()
            # Set connect button to disconnect mode:
            self.buttons['connect'].setText('Disconnect')
            # Set status to connected:
            self.u3['connected'] = True
            # Enable the sequence run button:
            self.buttons['run'].setEnabled(True)
            # Check connect button:
            self.buttons['connect'].setChecked(True)
        else:
            # Un-check connect button:
            self.buttons['connect'].setChecked(False)
        # If we have the U3 config information:
        if self.u3['config']:
            # Update the device information in the UI:
            value_dev = str(self.u3['config']['DeviceName'])
            self.status_area['value_dev'].setText(value_dev)
            value_sn = str(self.u3['config']['SerialNumber'])
            self.status_area['value_sn'].setText(value_sn)
            value_fw = str(self.u3['config']['FirmwareVersion'])
            self.status_area['value_fw'].setText(value_fw)
        # Update the FIO statuses:
        self.update_fio_status(4)
        self.update_fio_status(5)
        self.update_fio_status(6)
        self.update_fio_status(7)

    @staticmethod
    def display_alert(alert_msg):
        """
        display_alert

        Display an alert message
        """
        # Create the QMessageBox:
        alert = QMessageBox()
        # Add a bit of redness to the acknowledgement button:
        alert.setStyleSheet('QPushButton {background-color: #ff3333;}')
        # Set the title and text of the alert:
        alert.setWindowTitle(APP_NAME)
        alert.setText(alert_msg)
        # Alert!:
        alert.exec_()

    def button_connect(self):
        """
        button_connect

        Create the connect / disconnect button
        """
        # Create the QPushButton:
        button_connect = QPushButton('', self)
        # The connect / disconnect button is 'checkable', i.e. a toggle
        # switch:
        button_connect.setCheckable(True)
        # If the U3 device is connected:
        if self.u3['dev']:
            # Button is in 'disconnect' state:
            button_connect.setText('Disconnect')
            button_connect.setChecked(True)
        else:
            # Otherwise button is in 'connect' state:
            button_connect.setText('Connect')
            button_connect.setChecked(False)
        # On button click, run toggle_connect() function:
        button_connect.clicked.connect(self.toggle_connect)
        # Return the button:
        return button_connect

    def button_quit(self):
        """
        button_quit

        Create the quit button
        """
        # Create the QPushButton:
        button_quit = QPushButton('Quit', self)
        # On click, run self.closeEvent() function to close application:
        button_quit.clicked.connect(self.closeEvent)
        # Return the button:
        return button_quit

    def add_header_area(self):
        """
        add_header_area

        Create the UI header area
        """
        # Create a QFrame for the area:
        self.header_area['frame'] = QFrame(self)
        header_frame = self.header_area['frame']
        # Create a grid layout:
        self.header_area['grid'] = QGridLayout(header_frame)
        header_grid = self.header_area['grid']
        # Set the grid spacing:
        header_grid.setSpacing(self.window_properties['grid_spacing'])
        # Calculate a column width:
        col_width = round(
            (self.window_properties['width'] -
             (4 * self.window_properties['grid_spacing'])) / 6
        )
        # Set the column widths:
        header_grid.setColumnMinimumWidth(0, col_width * 4)
        header_grid.setColumnMinimumWidth(1, col_width)
        header_grid.setColumnMinimumWidth(2, col_width)
        # Create a label for the header area:
        self.header_area['label'] = QLabel('U3 Status', self)
        header_label = self.header_area['label']
        header_label.setTextFormat(Qt.PlainText)
        header_label.setFont(self.fonts['bold'])
        header_grid.addWidget(header_label, 0, 0)
        # Create the connect / disconnect button:
        self.buttons['connect'] = self.button_connect()
        button_connect = self.buttons['connect']
        header_grid.addWidget(button_connect, 0, 1)
        # Create the quit button:
        self.buttons['quit'] = self.button_quit()
        button_quit = self.buttons['quit']
        header_grid.addWidget(button_quit, 0, 2)
        # Add the header area to the UI:
        self.layout.addWidget(header_frame)

    def add_status_area(self):
        """
        add_status_area

        Create the UI status area
        """
        # Create a Qframe for the area:
        self.status_area['frame'] = QFrame(self)
        status_frame = self.status_area['frame']
        status_frame.setFrameShape(QFrame.StyledPanel)
        status_frame.setFrameShadow(QFrame.Raised)
        # Create a grid layout:
        self.status_area['grid'] = QGridLayout(status_frame)
        status_grid = self.status_area['grid']
        status_grid.setSpacing(self.window_properties['grid_spacing'])
        # Calculate a column width:
        col_width = round(
            (self.window_properties['width'] -
             (3 * self.window_properties['grid_spacing'])) / 2
        )
        # Set the column width:
        status_grid.setColumnMinimumWidth(0, col_width)
        status_grid.setColumnMinimumWidth(1, col_width)
        # Create a device information label:
        self.status_area['label_dev'] = QLabel('Device Name', self)
        status_label_dev = self.status_area['label_dev']
        status_label_dev.setTextFormat(Qt.PlainText)
        status_label_dev.setAlignment(Qt.AlignLeft)
        status_label_dev.setFont(self.fonts['bold'])
        status_grid.addWidget(status_label_dev, 0, 0)
        # If we have a U3 config:
        if self.u3['config']:
            # Set the device name value:
            value_dev = str(self.u3['config']['DeviceName'])
            self.status_area['value_dev'] = QLabel(value_dev, self)
        else:
            # Else, leave empty:
            self.status_area['value_dev'] = QLabel('--', self)
        # Add the device information:
        status_value_dev = self.status_area['value_dev']
        status_value_dev.setTextFormat(Qt.PlainText)
        status_value_dev.setAlignment(Qt.AlignRight)
        status_grid.addWidget(status_value_dev, 0, 1)
        # Create a serial number label:
        self.status_area['label_sn'] = QLabel('Serial Number', self)
        status_label_sn = self.status_area['label_sn']
        status_label_sn.setTextFormat(Qt.PlainText)
        status_label_sn.setAlignment(Qt.AlignLeft)
        status_label_sn.setFont(self.fonts['bold'])
        status_grid.addWidget(status_label_sn, 1, 0)
        # If we have a U3 config:
        if self.u3['config']:
            # Set the serial number value:
            value_sn = str(self.u3['config']['SerialNumber'])
            self.status_area['value_sn'] = QLabel(value_sn, self)
        else:
            # Else, leave empty:
            self.status_area['value_sn'] = QLabel('--', self)
        # Add the serial number information:
        status_value_sn = self.status_area['value_sn']
        status_value_sn.setTextFormat(Qt.PlainText)
        status_value_sn.setAlignment(Qt.AlignRight)
        status_grid.addWidget(status_value_sn, 1, 1)
        # Create a firmware version label:
        self.status_area['label_fw'] = QLabel('Firmware Version', self)
        status_label_fw = self.status_area['label_fw']
        status_label_fw.setTextFormat(Qt.PlainText)
        status_label_fw.setAlignment(Qt.AlignLeft)
        status_label_fw.setFont(self.fonts['bold'])
        status_grid.addWidget(status_label_fw, 2, 0)
        # If we have a U3 config:
        if self.u3['config']:
            # Set the firmware version value:
            value_fw = str(self.u3['config']['FirmwareVersion'])
            self.status_area['value_fw'] = QLabel(value_fw, self)
        else:
            # Else, leave empty:
            self.status_area['value_fw'] = QLabel('--', self)
        # Add the firmware version information:
        status_value_fw = self.status_area['value_fw']
        status_value_fw.setTextFormat(Qt.PlainText)
        status_value_fw.setAlignment(Qt.AlignRight)
        status_grid.addWidget(status_value_fw, 2, 1)
        # Create a label for the temperature label:
        self.status_area['label_temp'] = QLabel('Temperature', self)
        status_label_temp = self.status_area['label_temp']
        status_label_temp.setTextFormat(Qt.PlainText)
        status_label_temp.setAlignment(Qt.AlignLeft)
        status_label_temp.setFont(self.fonts['bold'])
        status_grid.addWidget(status_label_temp, 3, 0)
        # Create a label for the temperature value:
        self.status_area['value_temp'] = QLabel('--', self)
        status_value_temp = self.status_area['value_temp']
        status_value_temp.setTextFormat(Qt.PlainText)
        status_value_temp.setAlignment(Qt.AlignRight)
        status_grid.addWidget(status_value_temp, 3, 1)
        # Create a label for the AIN0 label:
        self.status_area['label_ain0'] = QLabel(self.io_labels['ain0'], self)
        status_label_ain0 = self.status_area['label_ain0']
        status_label_ain0.setTextFormat(Qt.PlainText)
        status_label_ain0.setAlignment(Qt.AlignLeft)
        status_label_ain0.setFont(self.fonts['bold'])
        status_grid.addWidget(status_label_ain0, 4, 0)
        # Create a label for the AIN0 value:
        self.status_area['value_ain0'] = QLabel('--', self)
        status_value_ain0 = self.status_area['value_ain0']
        status_value_ain0.setTextFormat(Qt.PlainText)
        status_value_ain0.setAlignment(Qt.AlignRight)
        status_grid.addWidget(status_value_ain0, 4, 1)
        # Create a label for the AIN1 label:
        self.status_area['label_ain1'] = QLabel(self.io_labels['ain1'], self)
        status_label_ain1 = self.status_area['label_ain1']
        status_label_ain1.setTextFormat(Qt.PlainText)
        status_label_ain1.setAlignment(Qt.AlignLeft)
        status_label_ain1.setFont(self.fonts['bold'])
        status_grid.addWidget(status_label_ain1, 5, 0)
        # Create a label for the AIN1 value:
        self.status_area['value_ain1'] = QLabel('--', self)
        status_value_ain1 = self.status_area['value_ain1']
        status_value_ain1.setTextFormat(Qt.PlainText)
        status_value_ain1.setAlignment(Qt.AlignRight)
        status_grid.addWidget(status_value_ain1, 5, 1)
        # Create a label for the voltage diff label:
        self.status_area['label_vd'] = QLabel(self.io_labels['vd'], self)
        status_label_vd = self.status_area['label_vd']
        status_label_vd.setTextFormat(Qt.PlainText)
        status_label_vd.setAlignment(Qt.AlignLeft)
        status_label_vd.setFont(self.fonts['bold'])
        status_grid.addWidget(status_label_vd, 6, 0)
        # Create a label for the voltage diff value:
        self.status_area['value_vd'] = QLabel('--', self)
        status_value_vd = self.status_area['value_vd']
        status_value_vd.setTextFormat(Qt.PlainText)
        status_value_vd.setAlignment(Qt.AlignRight)
        status_grid.addWidget(status_value_vd, 6, 1)
        # Create a label for the Pressure label:
        self.status_area['label_pres'] = QLabel(self.io_labels['pres'], self)
        status_label_pres = self.status_area['label_pres']
        status_label_pres.setTextFormat(Qt.PlainText)
        status_label_pres.setAlignment(Qt.AlignLeft)
        status_label_pres.setFont(self.fonts['bold'])
        status_grid.addWidget(status_label_pres, 7, 0)
        # Create a label for the Pressure value:
        self.status_area['value_pres'] = QLabel('--', self)
        status_value_pres = self.status_area['value_pres']
        status_value_pres.setTextFormat(Qt.PlainText)
        status_value_pres.setAlignment(Qt.AlignRight)
        status_grid.addWidget(status_value_pres, 7, 1)
        # Add the status area to the UI:
        self.layout.addWidget(status_frame)

    def update_fio_status(self, fio_id):
        """
        update_fio_status

        Update the status information for a FIO port in the UI
        """
        # The FIO we are working with:
        fio_str = 'fio{0}'.format(fio_id)
        fio_value_key = 'value_{0}'.format(fio_str)
        # If the U3 device is connected:
        if self.u3['dev']:
            # Get the state and update the UI:
            fio_state = self.u3['dev'].getFIOState(fio_id)
            fio_label = self.io_states[fio_str][fio_state]
            self.fio_area[fio_value_key].setText(fio_label)
            self.status[fio_str] = fio_state
            # Enable the toggle button for this FIO if sequence is not
            # running:
            if self.buttons[fio_str] and not self.status['seq_running']:
                self.buttons[fio_str].setEnabled(True)
        else:
            # If no U3 connected, set the status to empty:
            self.fio_area[fio_value_key].setText('--')
            self.status[fio_str] = None
            # Disable the toggle button:
            if self.buttons[fio_str]:
                self.buttons[fio_str].setEnabled(False)

    def toggle_fio_state(self, fio_id):
        """
        toggle_fio_state

        Toggle the state of a FIO port
        """
        # If a U3 device is connected:
        if self.u3['dev']:
            # Get the current state:
            fio_state = self.u3['dev'].getFIOState(fio_id)
            # Work out what the new state will be:
            if fio_state:
                new_fio_state = 0
            else:
                new_fio_state = 1
            # Update the FIO state, and update the status in the UI:
            self.u3['dev'].setFIOState(fio_id, state=new_fio_state)
            self.update_fio_status(fio_id)

    def toggle_fio4_state(self):
        """
        toggle_fio4_state

        Toggle state of FIO 4
        """
        self.toggle_fio_state(4)

    def toggle_fio5_state(self):
        """
        toggle_fio5_state

        Toggle state of FIO 5
        """
        self.toggle_fio_state(5)

    def toggle_fio6_state(self):
        """
        toggle_fio6_state

        Toggle state of FIO 6
        """
        self.toggle_fio_state(6)

    def toggle_fio7_state(self):
        """
        toggle_fio7_state

        Toggle state of FIO 7
        """
        self.toggle_fio_state(7)

    def button_fio(self):
        """
        button_fio

        Create toggle button for a FIO port
        """
        # Create the QPushButton:
        button_fio = QPushButton('Toggle State', self)
        # Enable / disable button, dpeending on whether U3 device is
        # connected:
        if self.u3['dev']:
            button_fio.setEnabled(True)
        else:
            button_fio.setEnabled(False)
        # Return the button:
        return button_fio

    def add_fio_header_area(self):
        """
        add_fio_header_area

        Add FIO header area to the UI
        """
        # Create a frame for the area:
        self.fio_header_area['frame'] = QFrame(self)
        fio_header_frame = self.fio_header_area['frame']
        # Create a grid layout:
        self.fio_header_area['grid'] = QGridLayout(fio_header_frame)
        fio_header_grid = self.fio_header_area['grid']
        # Set a column width for the grid:
        fio_header_grid.setSpacing(self.window_properties['grid_spacing'])
        col_width = round(
            (self.window_properties['width'] -
             (3 * self.window_properties['grid_spacing'])) / 2
        )
        fio_header_grid.setColumnMinimumWidth(0, col_width)
        # Create a label for the area:
        self.fio_header_area['label'] = QLabel('Valve Status', self)
        fio_header_label = self.fio_header_area['label']
        fio_header_label.setTextFormat(Qt.PlainText)
        fio_header_label.setFont(self.fonts['bold'])
        fio_header_grid.addWidget(fio_header_label, 0, 0)
        # Add the area to the UI:
        self.layout.addWidget(fio_header_frame)

    def add_fio_area(self):
        """
        add_fio_area

        Add FIO area to the UI
        """
        # Create a QFrame for the area:
        self.fio_area['frame'] = QFrame(self)
        fio_frame = self.fio_area['frame']
        fio_frame.setFrameShape(QFrame.StyledPanel)
        fio_frame.setFrameShadow(QFrame.Raised)
        # Create a grid layout for the area:
        self.fio_area['grid'] = QGridLayout(fio_frame)
        fio_grid = self.fio_area['grid']
        # set a column width:
        fio_grid.setSpacing(self.window_properties['grid_spacing'])
        col_width = round(
            (self.window_properties['width'] -
             (4 * self.window_properties['grid_spacing'])) / 3
        )
        fio_grid.setColumnMinimumWidth(0, col_width)
        fio_grid.setColumnMinimumWidth(1, col_width)
        fio_grid.setColumnMinimumWidth(2, col_width)
        # Create a label for FIO4:
        self.fio_area['label_fio4'] = QLabel(self.io_labels['fio4'], self)
        fio_label_fio4 = self.fio_area['label_fio4']
        fio_label_fio4.setTextFormat(Qt.PlainText)
        fio_label_fio4.setAlignment(Qt.AlignLeft)
        fio_label_fio4.setFont(self.fonts['bold'])
        fio_grid.addWidget(fio_label_fio4, 0, 0)
        # Create a value label for FIO4:
        self.fio_area['value_fio4'] = QLabel('--', self)
        self.update_fio_status(4)
        fio_value_fio4 = self.fio_area['value_fio4']
        fio_value_fio4.setTextFormat(Qt.PlainText)
        fio_value_fio4.setAlignment(Qt.AlignLeft)
        fio_grid.addWidget(fio_value_fio4, 0, 1)
        # Create a toggle button for FIO4:
        self.buttons['fio4'] = self.button_fio()
        button_fio4 = self.buttons['fio4']
        button_fio4.clicked.connect(self.toggle_fio4_state)
        fio_grid.addWidget(button_fio4, 0, 2)
        # Create a label for FIO5:
        self.fio_area['label_fio5'] = QLabel(self.io_labels['fio5'], self)
        fio_label_fio5 = self.fio_area['label_fio5']
        fio_label_fio5.setTextFormat(Qt.PlainText)
        fio_label_fio5.setAlignment(Qt.AlignLeft)
        fio_label_fio5.setFont(self.fonts['bold'])
        fio_grid.addWidget(fio_label_fio5, 1, 0)
        # Create a value label for FIO5:
        self.fio_area['value_fio5'] = QLabel('--', self)
        self.update_fio_status(5)
        fio_value_fio5 = self.fio_area['value_fio5']
        fio_value_fio5.setTextFormat(Qt.PlainText)
        fio_value_fio5.setAlignment(Qt.AlignLeft)
        fio_grid.addWidget(fio_value_fio5, 1, 1)
        # Create a toggle button for FIO5:
        self.buttons['fio5'] = self.button_fio()
        button_fio5 = self.buttons['fio5']
        button_fio5.clicked.connect(self.toggle_fio5_state)
        fio_grid.addWidget(button_fio5, 1, 2)
        # Create a label for FIO6:
        self.fio_area['label_fio6'] = QLabel(self.io_labels['fio6'], self)
        fio_label_fio6 = self.fio_area['label_fio6']
        fio_label_fio6.setTextFormat(Qt.PlainText)
        fio_label_fio6.setAlignment(Qt.AlignLeft)
        fio_label_fio6.setFont(self.fonts['bold'])
        fio_grid.addWidget(fio_label_fio6, 2, 0)
        # Create a value label for FIO6:
        self.fio_area['value_fio6'] = QLabel('--', self)
        self.update_fio_status(6)
        fio_value_fio6 = self.fio_area['value_fio6']
        fio_value_fio6.setTextFormat(Qt.PlainText)
        fio_value_fio6.setAlignment(Qt.AlignLeft)
        fio_grid.addWidget(fio_value_fio6, 2, 1)
        # Create a toggle button for FIO6:
        self.buttons['fio6'] = self.button_fio()
        button_fio6 = self.buttons['fio6']
        button_fio6.clicked.connect(self.toggle_fio6_state)
        fio_grid.addWidget(button_fio6, 2, 2)
        # Create a label for FIO7:
        self.fio_area['label_fio7'] = QLabel(self.io_labels['fio7'], self)
        fio_label_fio7 = self.fio_area['label_fio7']
        fio_label_fio7.setTextFormat(Qt.PlainText)
        fio_label_fio7.setAlignment(Qt.AlignLeft)
        fio_label_fio7.setFont(self.fonts['bold'])
        fio_grid.addWidget(fio_label_fio7, 3, 0)
        # Create a value label for FIO7:
        self.fio_area['value_fio7'] = QLabel('--', self)
        self.update_fio_status(7)
        fio_value_fio7 = self.fio_area['value_fio7']
        fio_value_fio7.setTextFormat(Qt.PlainText)
        fio_value_fio7.setAlignment(Qt.AlignLeft)
        fio_grid.addWidget(fio_value_fio7, 3, 1)
        # Create a toggle button for FIO7:
        self.buttons['fio7'] = self.button_fio()
        button_fio7 = self.buttons['fio7']
        button_fio7.clicked.connect(self.toggle_fio7_state)
        fio_grid.addWidget(button_fio7, 3, 2)
        # Add the area to the UI:
        self.layout.addWidget(fio_frame)

    def toggle_run(self):
        """
        toggle_run

        Toggle run status of sequence
        """
        # Get the run button details:
        button_run = self.buttons['run']
        # If the sequence is currently running:
        if self.status['seq_running']:
            # Tell the sequence thread to quit:
            self.status['seq_thread'].quit = True
            # Re-enable FIO toggle buttons:
            self.buttons['fio4'].setEnabled(True)
            self.buttons['fio5'].setEnabled(True)
            self.buttons['fio6'].setEnabled(True)
            self.buttons['fio7'].setEnabled(True)
            # Re-enable run button:
            button_run.setChecked(False)
            button_run.setText('Run')
            button_run.setStyleSheet("background-color: #33ff33")
            # Update status:
            self.status['seq_running'] = False
        else:
            # Update run button to be a stop button:
            button_run.setText('Stop')
            button_run.setStyleSheet("background-color: #ff3333")
            button_run.setChecked(True)
            # Update run status:
            self.status['seq_running'] = True
            # Disable FIO toggle buttons:
            self.buttons['fio4'].setEnabled(False)
            self.buttons['fio5'].setEnabled(False)
            self.buttons['fio6'].setEnabled(False)
            self.buttons['fio7'].setEnabled(False)
            # Start the sequence!:
            self.start_seq()

    def button_run(self):
        """
        button_run

        Create sequence run button.
        """
        # Create the QPushButton:
        button_run = QPushButton('', self)
        # If the sequence is currently running:
        if self.status['seq_running']:
            # The run button is a stop button:
            button_run.setText('Stop')
            button_run.setChecked(True)
            button_run.setStyleSheet("background-color: #33ff33")
        else:
            # Else, the run button is a run button:
            button_run.setText('Run')
            button_run.setChecked(False)
            button_run.setStyleSheet("background-color: #33ff33")
        # If no U3 device is connected, disable the button:
        if not self.u3['dev']:
            button_run.setEnabled(False)
        # When button is clicked, run the toggle_run() function:
        button_run.clicked.connect(self.toggle_run)
        # Return the button:
        return button_run

    def button_clear(self):
        """
        button_clear

        Create a button to clear the message area
        """
        # Create the QPushButton:
        button_clear = QPushButton('Clear', self)
        # Return the button:
        return button_clear

    def add_seq_header_area(self):
        """
        add_seq_header_area

        Add sequence header area to UI
        """
        # Create a QFrame for the area:
        self.seq_header_area['frame'] = QFrame(self)
        seq_header_frame = self.seq_header_area['frame']
        # Create a grid layout:
        self.seq_header_area['grid'] = QGridLayout(seq_header_frame)
        seq_header_grid = self.seq_header_area['grid']
        # Set the column width:
        seq_header_grid.setSpacing(self.window_properties['grid_spacing'])
        col_width = round(
            (self.window_properties['width'] -
             (4 * self.window_properties['grid_spacing'])) / 6
        )
        seq_header_grid.setColumnMinimumWidth(0, col_width * 4)
        seq_header_grid.setColumnMinimumWidth(1, col_width)
        seq_header_grid.setColumnMinimumWidth(2, col_width)
        # Create a label for the area:
        self.seq_header_area['label'] = QLabel('Sequence Status', self)
        seq_header_label = self.seq_header_area['label']
        seq_header_label.setTextFormat(Qt.PlainText)
        seq_header_label.setFont(self.fonts['bold'])
        seq_header_grid.addWidget(seq_header_label, 0, 0)
        # Add the button for clearing log messages:
        self.buttons['clear'] = self.button_clear()
        button_clear = self.buttons['clear']
        seq_header_grid.addWidget(button_clear, 0, 1)
        # Add the run button:
        self.buttons['run'] = self.button_run()
        button_run = self.buttons['run']
        seq_header_grid.addWidget(button_run, 0, 2)
        # Add the area to the UI:
        self.layout.addWidget(seq_header_frame)

    def add_seq_area(self):
        """
        add_seq_area

        Add the sequence status area to the UI
        """
        # Create a QFrame for the area:
        self.seq_area['frame'] = QFrame(self)
        seq_frame = self.seq_area['frame']
        seq_frame.setFrameShape(QFrame.StyledPanel)
        seq_frame.setFrameShadow(QFrame.Raised)
        # Create a grid layout:
        self.seq_area['grid'] = QGridLayout(seq_frame)
        seq_grid = self.seq_area['grid']
        seq_grid.setSpacing(self.window_properties['grid_spacing'])
        # Set a column width:
        col_width = round(
            (self.window_properties['width'] -
             (2 * self.window_properties['grid_spacing'])) / 1
        )
        seq_grid.setColumnMinimumWidth(0, col_width)
        # Add the log message area:
        self.seq_area['text'] = QTextEdit(self)
        seq_text = self.seq_area['text']
        seq_text.setReadOnly(True)
        self.buttons['clear'].clicked.connect(seq_text.clear)
        seq_grid.addWidget(seq_text, 0, 0)
        # Add the area to the UI:
        self.layout.addWidget(seq_frame)

    def set_log_file(self):
        """
        set_log_file

        Use a QFileDialog to set the output log file
        """
        # Get the default QFileDialog options:
        options = QFileDialog.Options()
        # Don't require confirmation for overwrite, as existing files will be
        # appended:
        options |= QFileDialog.DontConfirmOverwrite
        # Get the path to the log file:
        log_file = QFileDialog.getSaveFileName(self, 'Select Output File',
                                               self.working_dir,
                                               'CSV Files (*.csv)',
                                               options=options)[0]
        # Set the working directory to the log file directory:
        self.working_dir = os.path.dirname(log_file)
        # Store log file information:
        self.log_file = log_file
        # Tell the sequence thread about the log file:
        self.status['seq_thread'].log_file = self.log_file

    def set_sample_name(self):
        """
        set_sample_name

        Use a QInputDialog to set the sample name
        """
        # Get the sample name. This returns the text and exit status, e.g.:
        #   ('sample_name', True)
        # or, if the operation is cancelled:
        #   ('', False)
        sample_name, status = QInputDialog.getText(self, APP_NAME, 'Sample name:', 0,
                                                   self.sample_name)
        # If the sample name setting was not successful:
        if not status:
            # Send the sequence thread an empty sample name:
            self.status['seq_thread'].sample_name = ''
        # Otherwise, carry on:
        else:
            # Store sample name information:
            self.sample_name = sample_name
            # Tell the sequence thread about the sample_name:
            self.status['seq_thread'].sample_name = self.sample_name

    def set_seq_int(self):
        """
        set_seq_int

        Use a QInputDialog to set the sequence time step interval
        """
        # Get the sequence time step interval:
        window_msg = 'Sequence time step interval (seconds):'
        seq_int, status = QInputDialog.getInt(self, APP_NAME,
                                              window_msg,
                                              self.seq_int, 1)
        # If the interval getting was not successful:
        if not status:
            # Send the sequence thread the empty interval value:
            self.status['seq_thread'].seq_int = ''
        # Otherwise, carry on:
        else:
            # Store time step interval information:
            self.seq_int = seq_int
            # Tell the sequence thread about the sequence time step interval:
            self.status['seq_thread'].seq_int = self.seq_int

    def set_loop_count(self):
        """
        set_loop_count

        Use a QInputDialog to set the  loop count
        """
        # Get the sequence loop count:
        window_msg = 'Sequence loop count:'
        loop_count, status = QInputDialog.getInt(self, APP_NAME,
                                                 window_msg,
                                                 self.loop_count, 1)
        # If the loop count getting was not successful:
        if not status:
            # Send the sequence thread the empty loop count value:
            self.status['seq_thread'].loop_count = ''
        # Otherwise, carry on:
        else:
            # Store loop count information:
            self.loop_count = loop_count
            # Tell the sequence thread about the loop count:
            self.status['seq_thread'].loop_count = self.loop_count

    def log_state(self, timestamp):
        """
        log_state

        Save the current device status to the log file
        """
        # If the log file does not exist or is empty:
        if (not os.path.exists(self.log_file) or
                os.path.getsize(self.log_file) == 0):
            # Define a header line:
            log_hdr = ''.join(['date,'
                               'sample_name,',
                               'pressure,',
                               'voltage_0,voltage_1,voltage_diff',
                               'valve_state_1,valve_state_2,',
                               'valve_state_3,valve_state_4\n'])
            # Add the header line to the log file:
            with open(self.log_file, 'a') as log_file:
                log_file.write(log_hdr)
        # Open the log file in append mode:
        with open(self.log_file, 'a') as log_file:
            # Define the log message:
            log_msg = '{0},{1},{2},{3},{4},{5},{6},{7},{8},{9}\n'
            log_msg = log_msg.format(timestamp,
                                     self.sample_name,
                                     self.status['pres'],
                                     self.status['ain0'], self.status['ain1'],
                                     self.status['vd'],
                                     self.io_states['fio4'][self.status['fio4']],
                                     self.io_states['fio5'][self.status['fio5']],
                                     self.io_states['fio6'][self.status['fio6']],
                                     self.io_states['fio7'][self.status['fio7']])
            # Add the log message to the log file:
            log_file.write(log_msg)

    def start_seq(self):
        """
        start_seq

        Set the sequence running
        """
        # Create the sequence thread:
        self.status['seq_thread'] = LabJackerSeq(self.io_labels,
                                                 self.io_states, self.status)
        seq_thread = self.status['seq_thread']
        # Link up the signals from the thread to the relevant functions:
        seq_thread.log_msg.connect(self.seq_area['text'].append)
        seq_thread.set_log_file.connect(self.set_log_file)
        seq_thread.set_sample_name.connect(self.set_sample_name)
        seq_thread.set_seq_int.connect(self.set_seq_int)
        seq_thread.set_loop_count.connect(self.set_loop_count)
        seq_thread.log_state.connect(self.log_state)
        seq_thread.toggle_fio.connect(self.toggle_fio_state)
        seq_thread.toggle_run.connect(self.toggle_run)
        seq_thread.display_alert.connect(self.display_alert)
        # Start the thread:
        seq_thread.start()

    def closeEvent(self, event):
        """
        closeEvent

        Close the UI and application
        """
        # If a U3 device is connected:
        if self.u3['dev']:
            # Close the U3 connection:
            self.u3['dev'].close()
        # Quite the application:
        QApplication.instance().quit()

    def update_temp(self):
        """
        update_temp

        Update temperature information in the UI
        """
        # Try to get temperature information from U3 and update status:
        try:
            temp = self.u3['dev'].getTemperature()
            temp_deg_c = temp - 273.15
            self.status['temp'] = temp_deg_c
            temp_txt = '{0:.02f} °C'.format(temp_deg_c)
            self.status_area['value_temp'].setText(temp_txt)
        # Or just set status information to empty:
        except:
            self.status['temp'] = None
            self.status_area['value_temp'].setText('--')

    def update_ain(self, ain_ids=[0, 1]):
        """
        update_ain

        Update AIN information in the UI
        """
        # For each ain id:
        for ain_id in ain_ids:
            # AIN information based on ain_id:
            ain_str = 'ain{0}'.format(ain_id)
            val_str = 'value_ain{0}'.format(ain_id)
            # Try to get AIN information from U3 and update status:
            try:
                ain_value = self.u3['dev'].getAIN(ain_id)
                self.status[ain_str] = ain_value
                self.status_area[val_str].setText('{0:.05f} V'.format(ain_value))
            # Or just set status information to empty:
            except:
                self.status[ain_str] = None
                self.status_area[val_str].setText('--')
        # Voltage diff key values:
        vd_str = 'vd'
        val_vd_str = 'value_vd'
        # Try to get voltage difference, which is ain1 - ain0 (v1 - v0):
        try:
            vd = self.status['ain1'] - self.status['ain0']
            self.status[vd_str] = vd
            vd_txt = '{0:.05f} V'.format(vd)
            self.status_area[val_vd_str].setText(vd_txt)
        except:
            vd = None
            self.status[vd_str] = vd
            self.status_area[val_vd_str].setText('--')
        # Pressure key values:
        pres_str = 'pres'
        val_pres_str = 'value_pres'
        # Pressure comes from voltage diff.
        # Set 'v' to voltage diff for pressure conversion from calibration:
        v = vd
        # If we have a voltage diff value:
        if v:
            # try provided calibration:
            try:
                pres_value = eval(self.calibration['pres'])
            except:
                # If there is an issue with provided value, switch to
                # defaults:
                self.calibration['pres'] = self.calibration_default['pres']
                pres_value = eval(self.calibration_default['pres'])
            self.status[pres_str] = pres_value
            pres_txt = '{0:.05f} psig'.format(pres_value)
            self.status_area[val_pres_str].setText(pres_txt)
        # No voltage value, set status information to empty:
        else:
            self.status[pres_str] = None
            self.status_area[val_pres_str].setText('--')

    def init_ui(self):
        """
        init_ui

        Init the application and UI
        """
        # Try to connect to U3 device:
        self.u3['dev'] = connect_u3()
        if self.u3['dev']:
            self.u3['config'] = self.u3['dev'].configU3()
            self.u3['connected'] = True
        # Set window size:
        self.setFixedSize(self.window_properties['width'],
                          self.window_properties['height'])
        # Set window title:
        self.setWindowTitle('{0} {1}'.format(APP_NAME, APP_VERSION))
        # Add header_area:
        self.add_header_area()
        # Add status area:
        self.add_status_area()
        # Add FIO header area:
        self.add_fio_header_area()
        # Add FIO area:
        self.add_fio_area()
        # Add Sequence header area:
        self.add_seq_header_area()
        # Add Sequence area:
        self.add_seq_area()
        # Temperature monitoring thread:
        self.status['temp_thread'] = LabJackerPoll(poll_type='temp')
        temp_thread = self.status['temp_thread']
        temp_thread.update_temp.connect(self.update_temp)
        temp_thread.start()
        # AIN monitoring thread:
        self.status['ain_thread'] = LabJackerPoll(poll_type='ain')
        ain_thread = self.status['ain_thread']
        ain_thread.update_ain.connect(self.update_ain)
        ain_thread.start()
        # display the application:
        self.show()

def main():
    """
    main

    Create the Qt application and run.
    """
    # Create application:
    LABJACKER_APP = QApplication(sys.argv)
    # Create UI:
    LABJACKER_UI = LabJackerUI()
    # Exec-ing the app this way should make sure the appropriate exit code is
    # returned:
    sys.exit(LABJACKER_APP.exec_())

if __name__ == '__main__':
    main()
