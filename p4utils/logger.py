import logging

#custom debug levels
logging.getLogger().setLevel(logging.WARNING)

logging.DEBUG_MEDIUM = 9
logging.DEBUG_HIGH = 8
logging.DEBUG_TEMPORAL = 11

logging.addLevelName(logging.DEBUG_MEDIUM, "DEBUG_MEDIUM")
logging.addLevelName(logging.DEBUG_HIGH, "DEBUG_HIGH")
logging.addLevelName(logging.DEBUG_TEMPORAL, "DEBUG_TEMPORAL")

def debug_medium(self, message, *args, **kws):
    # Yes, logger takes its '*args' as 'args'.
    if self.isEnabledFor(logging.DEBUG_MEDIUM):
         self._log(logging.DEBUG_MEDIUM, message, args, **kws)


def debug_high(self, message, *args, **kws):
    # Yes, logger takes its '*args' as 'args'.
    if self.isEnabledFor(logging.DEBUG_HIGH):
        self._log(logging.DEBUG_HIGH, message, args, **kws)

def debug_temporal(self, message, *args, **kws):
    # Yes, logger takes its '*args' as 'args'.
    if self.isEnabledFor(logging.DEBUG_TEMPORAL):
        self._log(logging.DEBUG_TEMPORAL, message, args, **kws)

logging.Logger.debug_medium = debug_medium
logging.Logger.debug_high = debug_high
logging.Logger.debug_temporal = debug_temporal

logging.addLevelName(logging.WARNING, "\033[1;43m%s\033[1;0m" %
                                      logging.getLevelName(logging.WARNING))
# Errors are red
logging.addLevelName(logging.ERROR, "\033[1;41m%s\033[1;0m" %
                                    logging.getLevelName(logging.ERROR))
# Debug is green
logging.addLevelName(logging.DEBUG, "\033[1;42m%s\033[1;0m" %
                                    logging.getLevelName(logging.DEBUG))
# Debug is green
logging.addLevelName(logging.DEBUG_HIGH, "\033[1;46m%s\033[1;0m" %
                                    logging.getLevelName(logging.DEBUG_HIGH))

# Debug is green
logging.addLevelName(logging.DEBUG_MEDIUM, "\033[1;45m%s\033[1;0m" %
                                    logging.getLevelName(logging.DEBUG_MEDIUM))


# Debug is green
logging.addLevelName(logging.DEBUG_TEMPORAL, "\033[1;41m%s\033[1;0m" %
                                    logging.getLevelName(logging.DEBUG_TEMPORAL))

# Information messages are blue
logging.addLevelName(logging.INFO, "\033[1;44m%s\033[1;0m" %
                                   logging.getLevelName(logging.INFO))
# Critical messages are violet
logging.addLevelName(logging.CRITICAL, "\033[1;45m%s\033[1;0m" %
                                       logging.getLevelName(logging.CRITICAL))



log = logging.getLogger(__name__)
log.setLevel(logging.WARNING)

#fmt = logging.Formatter('[%(levelname)20s] %(asctime)s %(funcName)s: %(message)s ')
fmt = logging.Formatter('[%(levelname)20s] %(funcName)s: %(message)s ')
handler = logging.StreamHandler()
handler.setFormatter(fmt)


#handler.setLevel(logging.WARNING)
log.addHandler(handler)

