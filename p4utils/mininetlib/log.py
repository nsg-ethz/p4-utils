"""__ https://github.com/mininet/mininet/blob/master/mininet/log.py

This module is an extension of `mininet.log`__ that implements colored logs.
"""

import sys
import logging
from mininet.log import *


class ShellStyles:
    """Shell styles."""
    reset='\033[0m'
    bold='\033[01m'
    disable='\033[02m'
    underline='\033[04m'
    reverse='\033[07m'
    strikethrough='\033[09m'
    invisible='\033[08m'


class ShellFGColors:
    """Shell foreground colors."""
    black='\033[30m'
    red='\033[31m'
    green='\033[32m'
    orange='\033[33m'
    blue='\033[34m'
    purple='\033[35m'
    cyan='\033[36m'
    lightgrey='\033[37m'
    darkgrey='\033[90m'
    lightred='\033[91m'
    lightgreen='\033[92m'
    yellow='\033[93m'
    lightblue='\033[94m'
    pink='\033[95m'
    lightcyan='\033[96m'


class ShellBGColors:
    """Shell background colors."""
    black='\033[40m'
    red='\033[41m'
    green='\033[42m'
    orange='\033[43m'
    blue='\033[44m'
    purple='\033[45m'
    cyan='\033[46m'
    lightgrey='\033[47m'
    darkgrey='\033[100m'
    lightred='\033[101m'
    lightgreen='\033[102m'
    yellow='\033[103m'
    lightblue='\033[104m'
    pink='\033[105m'
    lightcyan='\033[106m'


LOG_FORMAT = {
    LEVELS['debug']: ShellStyles.disable,
    LEVELS['info']: ShellStyles.reset,
    LEVELS['output']: ShellStyles.bold,
    LEVELS['warning']: ShellStyles.bold + ShellFGColors.yellow,
    LEVELS['warn']: ShellStyles.bold + ShellFGColors.yellow,
    LEVELS['error']: ShellStyles.bold + ShellFGColors.red,
    LEVELS['critical']: ShellStyles.bold + ShellBGColors.red
}


class ColoredFormatter(logging.Formatter):
    """Get colored logs."""
    def format(self, record):
        s = super().format(record)
        if record.levelno in LOG_FORMAT:
            s = LOG_FORMAT[record.levelno] + s
            if record.levelno == LEVELS['critical']:
                s += '\n'
        if s[-1] == '\n':
            s = s[:-1] + ShellStyles.reset + '\n'
        else:
            s += ShellStyles.reset
        return s


# Add critical level
critical = lg.critical

# Set formatter
formatter = ColoredFormatter( LOGMSGFORMAT )
lg.ch.setFormatter( formatter )

# Handle exceptions as critical
def excepthook(type, value, traceback):
    critical('', exc_info=(type, value, traceback))

sys.excepthook = excepthook