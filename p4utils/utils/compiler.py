import os
import tempfile
import hashlib

from p4utils.utils.helper import *
from p4utils.mininetlib.log import debug, info, warning


class CompilationError(Exception):
    pass


class NotCompiledError(Exception):
    pass


class P4InfoDisabled(Exception):
    pass


class P4C:
    """This compiler reads the P4 program and generates
    the configuration files used by switches.

    Args:
        p4_src (str) : path of the source P4 file to compile
        p4c_bin (str): path to the compiler binary
        outdir (str) : directory containing all the output files. If set to **None**,
                       then every output is stored in the directory of ``p4_src``
        opts (str)   : ``p4c`` compilation options
        p4rt (bool)  : generate the P4Info file used to establish P4Runtime connection
                       to ``simple_switch_grpc``
    """
    p4c_bin = 'p4c'

    @classmethod
    def set_binary(self, p4c_bin):
        """Sets class default binary."""
        P4C.p4c_bin = p4c_bin

    def __init__(self, p4_src,
                 p4c_bin=None,
                 outdir=None,
                 opts='--target bmv2 --arch v1model --std p4-16',
                 p4rt=False,
                 **kwargs):

        if p4c_bin is not None:
            self.set_binary(p4c_bin)

        # Check whether the p4file is valid
        if p4_src is not None:
            if os.path.isfile(p4_src):
                self.p4_src = os.path.realpath(p4_src)
            else:
                 raise FileNotFoundError('could not find file {}.'.format(p4_src))
        else:
            raise FileNotFoundError('no source file provided.'.format(p4_src))

        if outdir is None:  
                self.outdir = os.path.dirname(self.p4_src)
        else:
            # Make sure that the provided outdir path is not pointing to a file
            # and, if necessary, create an empty outdir
            if not os.path.isdir(outdir):
                if os.path.exists(outdir):
                    raise NotADirectoryError("'{}' exists and is not a directory.".format(self.pcap_dir))
                else:
                    os.mkdir(outdir)
            self.outdir = outdir

        self.opts = opts
        self.p4rt = p4rt
        self.compiled = False
        
        p4_basename = os.path.basename(self.p4_src)
        p4rt_out_basename = p4_basename.replace('.p4', '') + '_p4rt.txt'
        json_out_basename = p4_basename.replace('.p4', '') + '.json'

        self.p4rt_out = self.outdir + '/' + p4rt_out_basename
        self.json_out = self.outdir + '/' + json_out_basename

    def compile(self):
        """Compiles the P4 file and generates the configuration files."""
        # Compute checksum of P4 file. This allows to recognize modified files.
        self.cksum = cksum(self.p4_src)
        debug('source: {}\tcksum: {}\n'.format(self.p4_src, self.cksum))

        compiler_args = []
        compiler_args.append(self.opts)
        compiler_args.append('-o "{}"'.format(self.outdir))

        if self.p4rt:
            compiler_args.append('--p4runtime-files "{}"'.format(self.p4rt_out))
        
        compiler_args.append('"{}"'.format(self.p4_src))
        info(self.p4c_bin + ' {}'.format(' '.join(compiler_args)) + '\n')
        return_value = run_command(self.p4c_bin + ' {}'.format(' '.join(compiler_args)))
        if return_value != 0:
            raise CompilationError
        else:
            info('{} compiled successfully.\n'.format(self.p4_src))
            self.compiled = True
    
    def get_json_out(self):
        """Returns the JSON configuration filepath."""
        if self.compiled:
            return self.json_out
        else:
            raise NotCompiledError

    def get_p4rt_out(self):
        """Returns the P4Info configuration filepath."""
        if self.compiled:
            if self.p4rt:
                return self.p4rt_out
            else:
                raise P4InfoDisabled
        else:
            raise NotCompiledError

    def clean(self):
        """Removes output files and set compiler as uncompiled."""
        os.remove(self.p4rt_out)
        os.remove(self.json_out)
        self.compiled = False

    def new_source(self):
        """Checks whether a new source was provided to the
        compiler.
        
        Returns:
            bool: **True** if the source P4 file has changed since
            the last time it was compiled, **False** otherwise.
        """
        return cksum(self.p4_src) != self.cksum