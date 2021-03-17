import os
import tempfile
from mininet.log import debug, info, warning
from p4.v1 import p4runtime_pb2
from p4.v1 import p4runtime_pb2_grpc
from p4.config.v1 import p4info_pb2
from p4.tmp import p4config_pb2

class P4C:
    """
    This compiler reads the .p4 program and outputs
    the configuration files used by switches.

    Attributes:
        p4_filepath (string): path of the p4 file to compile.
        outdir (string) : directory containing all the output files. If set to
                          None, then a every output is stored in temporary files.
        options (string): p4c compilation options
        p4runtime (bool): whether to output the p4info file used to
                          establish p4runtime connection to simple_switch_grpc.
    """
    compiled = False

    def __init__(self, p4_filepath,
                 outdir=None,
                 options='--target bmv2 --arch v1model --std p4-16',
                 p4runtime=False):

        # Check whether the p4file is valid
        if os.path.isfile(p4_filepath):
            self.p4_filepath = p4_filepath
        else:
            raise FileNotFoundError('FileMissing: could not find file {}'.format(p4_filepath))
        
        self.outdir = outdir
        self.options = options
        self.p4runtime = p4runtime
        
        p4_basename = os.path.basename(self.p4_filepath)
        p4rt_out_basename = p4_basename.replace('.p4', '') + '.p4rt'
        json_out_basename = p4_basename.replace('.p4', '') + '.json'

        # If outdir is not set, create a temporary directory
        if self.outdir is None:
            self.outdir = tempfile.TemporaryDirectory()

        self.p4rt_out = self.outdir + '/' + p4rt_out_basename
        self.json_out = self.outdir + '/' + json_out_basename

    def compile(self):
        """
        This method compiles the .p4 file and generates the
        configuration files
        """
        compiler = 'p4c'
        compiler_args = []
        compiler_args.append(self.options)
        compiler_args.append('-o "{}"'.format(self.outdir))

        if p4runtime:
            compiler_args.append('--p4runtime-files "{}"'.format(self.p4rt_out))
        
        compiler_args.append('"{}"'.format(self.p4_filepath))
        debug(compiler + ' {}'.format(' '.join(compiler_args))))
        return_value = run_command(compiler + ' {}'.format(' '.join(compiler_args)))
        if return_value != 0:
            raise Exception('CompilationError')
        else:
            info("{} compiled successfully.".format(self.p4_filepath))
            self.compiled = True

    def clean(self):
        """Unset temporary files if present"""
        if isinstance(self.outdir, tempfile.TemporaryDirectory):
            self.outdir.cleanup()
        else:
            os.remove(self.p4rt_out)
            os.remove(self.json_out)
        self.compiled = False


    