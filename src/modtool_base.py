""" Base class for the modules """

import os
import re
import sys
from optparse import OptionParser, OptionGroup

from util_functions import get_modname
from templates import Templates
from code_generator import CodeGenerator

### ModTool base class #######################################################
class ModTool(object):
    """ Base class for all modtool command classes. """
    def __init__(self):
        self._subdirs = ['lib', 'include', 'python', 'swig', 'grc'] # List subdirs where stuff happens
        self._has_subdirs = {}
        self._skip_subdirs = {}
        self._info = {}
        for subdir in self._subdirs:
            self._has_subdirs[subdir] = False
            self._skip_subdirs[subdir] = False
        self.parser = self.setup_parser()
        self.tpl = CodeGenerator()
        self.args = None
        self.options = None
        self._dir = None

    def setup_parser(self):
        """ Init the option parser. If derived classes need to add options,
        override this and call the parent function. """
        parser = OptionParser(usage=Templates['usage'], add_help_option=False)
        ogroup = OptionGroup(parser, "General options")
        ogroup.add_option("-h", "--help", action="help", help="Displays this help message.")
        ogroup.add_option("-d", "--directory", type="string", default=".",
                help="Base directory of the module.")
        ogroup.add_option("-n", "--module-name", type="string", default=None,
                help="Name of the GNU Radio module. If possible, this gets detected from CMakeLists.txt.")
        ogroup.add_option("-N", "--block-name", type="string", default=None,
                help="Name of the block, minus the module name prefix.")
        ogroup.add_option("--skip-lib", action="store_true", default=False,
                help="Don't do anything in the lib/ subdirectory.")
        ogroup.add_option("--skip-swig", action="store_true", default=False,
                help="Don't do anything in the swig/ subdirectory.")
        ogroup.add_option("--skip-python", action="store_true", default=False,
                help="Don't do anything in the python/ subdirectory.")
        ogroup.add_option("--skip-grc", action="store_true", default=False,
                help="Don't do anything in the grc/ subdirectory.")
        parser.add_option_group(ogroup)
        return parser


    def setup(self):
        """ Initialise all internal variables, such as the module name etc. """
        (options, self.args) = self.parser.parse_args()
        self._dir = options.directory
        if not self._check_directory(self._dir):
            print "No GNU Radio module found in the given directory. Quitting."
            sys.exit(1)
        print "Operating in directory " + self._dir

        if options.skip_lib:
            print "Force-skipping 'lib'."
            self._skip_subdirs['lib'] = True
        if options.skip_python:
            print "Force-skipping 'python'."
            self._skip_subdirs['python'] = True
        if options.skip_swig:
            print "Force-skipping 'swig'."
            self._skip_subdirs['swig'] = True
        if options.skip_grc:
            print "Force-skipping 'grc'."
            self._skip_subdirs['grc'] = True

        if options.module_name is not None:
            self._info['modname'] = options.module_name
        else:
            self._info['modname'] = get_modname()
        print "GNU Radio module name identified: " + self._info['modname']
        self._info['blockname'] = options.block_name
        self._info['includedir'] = os.path.join('include', self._info['modname'])
        self.options = options


    def run(self):
        """ Override this. """
        pass


    def _check_directory(self, directory):
        """ Guesses if dir is a valid GNU Radio module directory by looking for
        CMakeLists.txt and at least one of the subdirs lib/, python/ and swig/.
        Changes the directory, if valid. """
        has_makefile = False
        try:
            files = os.listdir(directory)
            os.chdir(directory)
        except OSError:
            print "Can't read or chdir to directory %s." % directory
            return False
        for f in files:
            if (os.path.isfile(f) and
                    f == 'CMakeLists.txt' and
                    re.search('(find_package\(GnuradioCore\)|GR_REGISTER_COMPONENT)', open(f).read()) is not None):
                has_makefile = True
            elif os.path.isdir(f):
                if (f in self._has_subdirs.keys()):
                    self._has_subdirs[f] = True
                else:
                    self._skip_subdirs[f] = True
        return bool(has_makefile and (self._has_subdirs.values()))


    def _get_mainswigfile(self):
        """ Find out which name the main SWIG file has. In particular, is it
            a MODNAME.i or a MODNAME_swig.i? Returns None if none is found. """
        modname = self._info['modname']
        swig_files = (modname + '.i',
                      modname + '_swig.i')
        for fname in swig_files:
            if os.path.isfile(os.path.join(self._dir, 'swig', fname)):
                return fname
        return None


