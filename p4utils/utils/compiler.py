import os
import shlex 
import hashlib
import subprocess

from p4utils.utils.helper import *
from p4utils.mininetlib.log import debug, info, output, warning, error, critical


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
                    raise NotADirectoryError("'{}' exists and is not a directory.".format(self.outdir))
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

        # Compiler command to execute
        cmd = self.p4c_bin + ' '
        cmd += '"{}" '.format(self.p4_src)
        cmd += self.opts + ' '
        cmd += '-o "{}" '.format(self.outdir)

        if self.p4rt:
            cmd += '--p4runtime-files "{}" '.format(self.p4rt_out)

        debug(cmd + '\n')

        # Execute command
        p = subprocess.Popen(shlex.split(cmd),
                             stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()

        if p.returncode != 0:
            info(stdout.decode(errors='backslashreplace'))
            error(stderr.decode(errors='backslashreplace'))
            raise CompilationError
        else:
            if len(stderr) == 0:
                info('{} compiled successfully.\n'.format(self.p4_src))
                info(stdout.decode(errors='backslashreplace'))
            else:
                info('{} compiled with warnings.\n'.format(self.p4_src))
                info(stdout.decode(errors='backslashreplace'))
                warning(stderr.decode(errors='backslashreplace'))
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


class BF_P4C:
    """This compiler reads the P4 program and generates
    the configuration files used by Tofinos.

    Args:
        p4_src (str)     : path of the source P4 file to compile
        build_dir (str)  : directory where the Tofino's configuration is built
        sde (str)        : Tofino SDE path ($SDE)
        sde_install (str): Tofino SDE install path ($SDE_INSTALL)
    """

    def __init__(self, p4_src,
                 sde,
                 sde_install,
                 build_dir=None,
                 **kwargs):

        self.sde = os.path.realpath(sde)
        self.sde_install = os.path.realpath(sde_install)

        # Check whether the p4file is valid
        if p4_src is not None:
            if os.path.isfile(p4_src):
                self.p4_src = os.path.realpath(p4_src)
            else:
                 raise FileNotFoundError('could not find file {}.'.format(p4_src))
        else:
            raise FileNotFoundError('no source file provided.'.format(p4_src))

        if build_dir is None:  
                self.build_dir = os.path.join(os.path.dirname(self.p4_src), 'build')
        else:
            # Make sure that the provided outdir path is not pointing to a file
            # and, if necessary, create an empty build_dir
            if not os.path.isdir(build_dir):
                if os.path.exists(build_dir):
                    raise NotADirectoryError("'{}' exists and is not a directory.".format(self.build_dir))
                else:
                    os.mkdir(build_dir)
            else:
                # Remove existent files and subdirectories
                os.system('rm -rf {}'.format(os.path.join(build_dir, '*')))
            self.build_dir = build_dir

        self.p4_name, _ = os.path.splitext(os.path.basename(self.p4_src))
        self.compiled = False

    def compile(self):
        """Compiles the P4 file and generates the configuration files."""
        # Compute checksum of P4 file. This allows to recognize modified files.
        self.cksum = cksum(self.p4_src)
        debug('source: {}\tcksum: {}\n'.format(self.p4_src, self.cksum))

        # Set environmental variables
        cmd = 'export SDE={} && '.format(self.sde)
        cmd += 'export SDE_INSTALL={} && '.format(self.sde_install)
        cmd += 'cd {}; '.format(self.build_dir)
        cmd += 'cmake $SDE/p4studio/ -DCMAKE_INSTALL_PREFIX=$SDE/install ' + \
               '-DCMAKE_MODULE_PATH=$SDE/cmake  -DP4_NAME={} '.format(self.p4_name) + \
               '-DP4_PATH={} && '.format(self.p4_src)
        cmd += 'make {} && make install'.format(self.p4_name)

        debug(cmd + '\n')

        # Execute command
        p = subprocess.Popen(cmd,
                             shell=True,
                             stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)

        stdout, stderr = p.communicate()

        if p.returncode != 0:
            info(stdout.decode(errors='backslashreplace'))
            error(stderr.decode(errors='backslashreplace'))
            raise CompilationError
        else:
            if len(stderr) == 0:
                info('{} compiled successfully.\n'.format(self.p4_src))
                info(stdout.decode(errors='backslashreplace'))
            else:
                info('{} compiled with warnings.\n'.format(self.p4_src))
                info(stdout.decode(errors='backslashreplace'))
                warning(stderr.decode(errors='backslashreplace'))
            self.compiled = True

    def get_p4name(self):
        """Returns the JSON configuration filepath."""
        if self.compiled:
            return self.p4_name
        else:
            raise NotCompiledError

    def clean(self):
        """Removes output files and set compiler as uncompiled."""
        os.remove(self.build_dir)
        self.compiled = False

    def new_source(self):
        """Checks whether a new source was provided to the
        compiler.
        
        Returns:
            bool: **True** if the source P4 file has changed since
            the last time it was compiled, **False** otherwise.
        """
        return cksum(self.p4_src) != self.cksum