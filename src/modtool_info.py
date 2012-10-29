""" Returns information about a module """

import os
import sys
from optparse import OptionGroup

from modtool_base import ModTool
from util_functions import get_modname

### Info  module #############################################################
class ModToolInfo(ModTool):
    """ Create a new out-of-tree module """
    name = 'info'
    aliases = ('getinfo', 'inf')
    def __init__(self):
        ModTool.__init__(self)

    def setup_parser(self):
        " Initialise the option parser for 'gr_modtool.py info' "
        parser = ModTool.setup_parser(self)
        parser.usage = '%prog info [options]. \n Call %prog without any options to run it interactively.'
        ogroup = OptionGroup(parser, "Info options")
        ogroup.add_option("--python-readable", action="store_true", default=None,
                help="Return the output in a format that's easier to read for Python scripts.")
        parser.add_option_group(ogroup)
        return parser

    def setup(self):
        # Won't call parent's setup(), because that's too chatty
        (self.options, self.args) = self.parser.parse_args()

    def run(self):
        """ Go, go, go! """
        mod_info = {}
        base_dir = self._get_base_dir(self.options.directory)
        if base_dir is None:
            if self.options.python_readable:
                print '{}'
            else:
                print "No module found."
            sys.exit(0)
        mod_info['base_dir'] = base_dir
        os.chdir(mod_info['base_dir'])
        mod_info['modname'] = get_modname()
        mod_info['incdirs'] = []
        mod_incl_dir = os.path.join(mod_info['base_dir'], 'include')
        if os.path.isdir(os.path.join(mod_incl_dir, mod_info['modname'])):
            mod_info['incdirs'].append(os.path.join(mod_incl_dir, mod_info['modname']))
        else:
            mod_info['incdirs'].append(mod_incl_dir)
        build_dir = self._get_build_dir(mod_info)
        if build_dir is not None:
            mod_info['build_dir'] = build_dir
            mod_info['incdirs'] += self._get_include_dirs(mod_info)
        if self.options.python_readable:
            print str(mod_info)
        else:
            self._pretty_print(mod_info)

    def _get_base_dir(self, start_dir):
        """ Figure out the base dir (where the top-level cmake file is) """
        base_dir = os.path.abspath(start_dir)
        if self._check_directory(base_dir):
            return base_dir
        else:
            (up_dir, this_dir) = os.path.split(base_dir)
            if os.path.split(up_dir)[1] == 'include':
                up_dir = os.path.split(up_dir)[0]
            if self._check_directory(up_dir):
                return up_dir
        return None

    def _get_build_dir(self, mod_info):
        """ Figure out the build dir (i.e. where you run 'cmake'). This checks
        for a file called CMakeCache.txt, which is created when running cmake.
        If that hasn't happened, the build dir cannot be detected, unless it's
        called 'build', which is then assumed to be the build dir. """
        has_build_dir = os.path.isdir(os.path.join(mod_info['base_dir'], 'build'))
        if (has_build_dir and os.path.isfile(os.path.join(mod_info['base_dir'], 'CMakeCache.txt'))):
            return os.path.join(mod_info['base_dir'], 'build')
        else:
            for (dirpath, dirnames, filenames) in os.walk(mod_info['base_dir']):
                if 'CMakeCache.txt' in filenames:
                    return dirpath
        if has_build_dir:
            return os.path.join(mod_info['base_dir'], 'build')
        return None

    def _get_include_dirs(self, mod_info):
        """ Figure out include dirs for the make process. """
        inc_dirs = []
        try:
            cmakecache_fid = open(os.path.join(mod_info['build_dir'], 'CMakeCache.txt'))
            for line in cmakecache_fid:
                if line.find('GNURADIO_CORE_INCLUDE_DIRS:PATH') != -1:
                    inc_dirs += line.replace('GNURADIO_CORE_INCLUDE_DIRS:PATH=', '').strip().split(';')
                if line.find('GRUEL_INCLUDE_DIRS:PATH') != -1:
                    inc_dirs += line.replace('GRUEL_INCLUDE_DIRS:PATH=', '').strip().split(';')
        except IOError:
            pass
        return inc_dirs

    def _pretty_print(self, mod_info):
        """ Output the module info in human-readable format """
        index_names = {'base_dir': 'Base directory',
                       'modname':  'Module name',
                       'build_dir': 'Build directory',
                       'incdirs': 'Include directories'}
        for key in mod_info.keys():
            print '%19s: %s' % (index_names[key], mod_info[key])

