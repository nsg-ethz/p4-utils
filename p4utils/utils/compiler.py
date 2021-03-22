import os
import tempfile
import hashlib
from mininet.log import debug, info, warning
from p4utils.utils.helper import *


class CompilationError(Exception):
    pass


class NotCompiledError(Exception):
    pass


class P4InfoDisabled(Exception):
    pass


class P4C:
    """
    This compiler reads the .p4 program and outputs
    the configuration files used by switches.

    Attributes:
        p4_filepath (string): path of the source P4 file to compile.
        p4c_bin (string)    : path to the compiler binary
        outdir (string)     : directory containing all the output files. If set to
                              None, then a every output is stored in temporary files.
        options (string)    : p4c compilation options
        p4runtime (bool)    : whether to output the p4info file used to
                              establish p4runtime connection to simple_switch_grpc.
    """
    compiled = False
    p4c_bin = 'p4c'

    @classmethod
    def set_binary(self, p4c_bin):
        """Set class default binary"""
        P4C.p4c_bin = p4c_bin

    def __init__(self, p4_filepath,
                 p4c_bin=None,
                 outdir='.',
                 options='--target bmv2 --arch v1model --std p4-16',
                 p4runtime=True,
                 **kwargs):

        if p4c_bin is not None:
            self.set_binary(p4c_bin)

        self.p4_filepath = None
        self.set_source(p4_filepath)        
        self.outdir = outdir
        self.options = options
        self.p4runtime = p4runtime
        
        p4_basename = os.path.basename(self.p4_filepath)
        p4rt_out_basename = p4_basename.replace('.p4', '') + '_p4rt.txt'
        json_out_basename = p4_basename.replace('.p4', '') + '.json'

        self.p4rt_out = self.outdir + '/' + p4rt_out_basename
        self.json_out = self.outdir + '/' + json_out_basename

    def compile(self):
        """
        This method compiles the .p4 file and generates the
        configuration files
        """
        # Compute checksum of P4 file. This allows to recognize modified files.
        self.cksum = cksum(self.p4_filepath)
        debug('source: {}\tcksum: {}\n'.format(self.p4_filepath, self.cksum))

        compiler_args = []
        compiler_args.append(self.options)
        compiler_args.append('-o "{}"'.format(self.outdir))

        if self.p4runtime:
            compiler_args.append('--p4runtime-files "{}"'.format(self.p4rt_out))
        
        compiler_args.append('"{}"'.format(self.p4_filepath))
        info(self.p4c_bin + ' {}'.format(' '.join(compiler_args)) + '\n')
        return_value = run_command(self.p4c_bin + ' {}'.format(' '.join(compiler_args)))
        if return_value != 0:
            raise CompilationError
        else:
            info('{} compiled successfully.\n'.format(self.p4_filepath))
            self.compiled = True
    
    def get_json_out(self):
        """Returns the json configuration filepath"""
        if self.compiled:
            return self.json_out
        else:
            raise NotCompiledError

    def get_p4rt_out(self):
        """Returns the p4info filepath"""
        if self.compiled:
            if self.p4runtime:
                return self.p4rt_out
            else:
                raise P4InfoDisabled
        else:
            raise NotCompiledError

    def clean(self):
        """Remove output files and set compiler as uncompiled."""
        os.remove(self.p4rt_out)
        os.remove(self.json_out)
        self.compiled = False

    def new_source(self):
        """
        Returns True if the source P4 file has changed since
        the last time it was compiled.
        """
        return cksum(self.p4_filepath) != self.cksum

    def set_source(self, p4_filepath):
        """Set the P4 source file path."""
        # Check whether the p4file is valid
        if os.path.isfile(p4_filepath):
            if self.p4_filepath != os.path.realpath(p4_filepath):
                self.compiled = False
                self.p4_filepath = os.path.realpath(p4_filepath)
        else:
            raise FileNotFoundError('FileMissing: could not find file {}'.format(p4_filepath))
    