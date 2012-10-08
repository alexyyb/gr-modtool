""" Module to add new blocks """

import os
import sys
import re
from optparse import OptionGroup

from util_functions import append_re_line_sequence
from cmakefile_editor import CMakeFileEditor
from modtool_base import ModTool
from templates import Templates
from code_generator import CodeGenerator

### Add new block module #####################################################
class ModToolAdd(ModTool):
    """ Add block to the out-of-tree module. """
    name = 'add'
    aliases = ('insert',)
    _block_types = ('sink', 'source', 'sync', 'decimator', 'interpolator',
                    'general', 'hiercpp', 'hierpython', 'noblock')
    def __init__(self):
        ModTool.__init__(self)
        self._info['inputsig'] = "<+MIN_IN+>, <+MAX_IN+>, sizeof (<+float+>)"
        self._info['outputsig'] = "<+MIN_OUT+>, <+MAX_OUT+>, sizeof (<+float+>)"
        self._add_cc_qa = False
        self._add_py_qa = False
        self.tpl = CodeGenerator()


    def setup_parser(self):
        parser = ModTool.setup_parser(self)
        parser.usage = '%prog add [options]. \n Call %prog without any options to run it interactively.'
        ogroup = OptionGroup(parser, "Add module options")
        ogroup.add_option("-t", "--block-type", type="choice",
                choices=self._block_types, default=None, help="One of %s." % ', '.join(self._block_types))
        ogroup.add_option("--license-file", type="string", default=None,
                help="File containing the license header for every source code file.")
        ogroup.add_option("--argument-list", type="string", default=None,
                help="The argument list for the constructor and make functions.")
        ogroup.add_option("--add-python-qa", action="store_true", default=None,
                help="If given, Python QA code is automatically added if possible.")
        ogroup.add_option("--add-cpp-qa", action="store_true", default=None,
                help="If given, C++ QA code is automatically added if possible.")
        ogroup.add_option("--skip-cmakefiles", action="store_true", default=False,
                help="If given, only source files are written, but CMakeLists.txt files are left unchanged.")
        parser.add_option_group(ogroup)
        return parser


    def setup(self):
        ModTool.setup(self)
        options = self.options
        self._info['blocktype'] = options.block_type
        if self._info['blocktype'] is None:
            while self._info['blocktype'] not in self._block_types:
                self._info['blocktype'] = raw_input("Enter code type: ")
                if self._info['blocktype'] not in self._block_types:
                    print 'Must be one of ' + str(self._block_types)
        print "Code is of type: " + self._info['blocktype']

        if (not self._has_subdirs['lib'] and self._info['blocktype'] != 'hierpython') or \
           (not self._has_subdirs['python'] and self._info['blocktype'] == 'hierpython'):
            print "Can't do anything if the relevant subdir is missing. See ya."
            sys.exit(1)

        if self._info['blockname'] is None:
            if len(self.args) >= 2:
                self._info['blockname'] = self.args[1]
            else:
                self._info['blockname'] = raw_input("Enter name of block/code (without module name prefix): ")
        if not re.match('[a-zA-Z0-9_]+', self._info['blockname']):
            print 'Invalid block name.'
            sys.exit(2)
        print "Block/code identifier: " + self._info['blockname']

        self._info['fullblockname'] = self._info['modname'] + '_' + self._info['blockname']
        self._info['license'] = self.setup_choose_license()

        if options.argument_list is not None:
            self._info['arglist'] = options.argument_list
        else:
            self._info['arglist'] = raw_input('Enter valid argument list, including default arguments: ')

        if not (self._info['blocktype'] in ('noblock') or self._skip_subdirs['python']):
            self._add_py_qa = options.add_python_qa
            if self._add_py_qa is None:
                self._add_py_qa = (raw_input('Add Python QA code? [Y/n] ').lower() != 'n')
        if not (self._info['blocktype'] in ('hierpython') or self._skip_subdirs['lib']):
            self._add_cc_qa = options.add_cpp_qa
            if self._add_cc_qa is None:
                self._add_cc_qa = (raw_input('Add C++ QA code? [Y/n] ').lower() != 'n')

        if self._info['blocktype'] == 'source':
            self._info['inputsig'] = "0, 0, 0"
            self._info['blocktype'] = "sync"
        if self._info['blocktype'] == 'sink':
            self._info['outputsig'] = "0, 0, 0"
            self._info['blocktype'] = "sync"


    def setup_choose_license(self):
        """ Select a license by the following rules, in this order:
        1) The contents of the file given by --license-file
        2) The contents of the file LICENSE or LICENCE in the modules
           top directory
        3) The default license. """
        if self.options.license_file is not None \
            and os.path.isfile(self.options.license_file):
            return open(self.options.license_file).read()
        elif os.path.isfile('LICENSE'):
            return open('LICENSE').read()
        elif os.path.isfile('LICENCE'):
            return open('LICENCE').read()
        else:
            return Templates['defaultlicense']

    def _write_tpl(self, tpl, path, fname):
        """ Shorthand for writing a substituted template to a file"""
        print "Adding file '%s'..." % fname
        open(os.path.join(path, fname), 'w').write(self.tpl.get_template(tpl, **self._info))

    def run(self):
        """ Go, go, go. """
        if self._info['blocktype'] != 'hierpython' and not self._skip_subdirs['lib']:
            self._run_lib()
        has_swig = self._info['blocktype'] in (
                'sink',
                'source',
                'sync',
                'decimator',
                'interpolator',
                'general',
                'hiercpp') and self._has_subdirs['swig'] and not self._skip_subdirs['swig']
        if has_swig:
            self._run_swig()
        if self._add_py_qa:
            self._run_python_qa()
        if self._info['blocktype'] == 'hierpython':
            self._run_python_hierblock()
        if (not self._skip_subdirs['grc'] and self._has_subdirs['grc'] and
            (self._info['blocktype'] == 'hierpython' or has_swig)):
            self._run_grc()


    def _run_lib(self):
        """ Do everything that needs doing in the subdir 'lib' and 'include'.
        - add *_impl.{cc,} files
        - include them into CMakeLists.txt
        - add include/MODNAME/*.h file
        - add that to CMakeLists.txt
        - check if C++ QA code is req'd
        - if yes, create qa_*.{cc,h} and add them to CMakeLists.txt and the test_*.cc file
        """
        print "Traversing lib..."
        if self._info['blocktype'] in ('source', 'sink', 'sync', 'decimator',
                                       'interpolator', 'general', 'hiercpp'):
            fname_impl_h = self._info['blockname'] + '_impl.h'
            fname_cc = self._info['blockname'] + '_impl.cc'
            fname_h = self._info['blockname'] + '.h'
            self._write_tpl('block_impl_h', 'lib', fname_impl_h)
            self._write_tpl('block_impl_cpp', 'lib', fname_cc)
            self._write_tpl('block_def_h', os.path.join('include', self._info['modname']),
                            fname_h)
        elif self._info['blocktype'] == 'noblock':
            fname_h = self._info['blockname'] + '.h'
            fname_cc = self._info['blockname'] + '.cc'
            self._write_tpl('noblock_h', os.path.join('include', self._info['modname']),
                            self._info['blockname'] + '.h')
            self._write_tpl('noblock_cpp', 'lib', self._info['blockname'] + '.cc')
        if not self.options.skip_cmakefiles:
            ed = CMakeFileEditor('lib/CMakeLists.txt')
            ed.append_value('add_library', fname_cc)
            ed.write()
            ed = CMakeFileEditor(os.path.join(self._info['includedir'], 'CMakeLists.txt'), '\n    ')
            ed.append_value('install', fname_h, 'DESTINATION[^()]+')
            ed.write()

        if not self._add_cc_qa:
            return
        fname_qa_cc = 'qa_%s.cc' % self._info['blockname']
        fname_qa_h  = 'qa_%s.h'  % self._info['blockname']
        self._write_tpl('qa_cpp', 'lib', fname_qa_cc)
        self._write_tpl('qa_h', 'lib', fname_qa_h)
        if not self.options.skip_cmakefiles:
            append_re_line_sequence('lib/CMakeLists.txt',
                                    '\$\{CMAKE_CURRENT_SOURCE_DIR\}/qa_%s.cc.*\n' % self._info['modname'],
                                    '  ${CMAKE_CURRENT_SOURCE_DIR}/qa_%s.cc' % self._info['blockname'])
            append_re_line_sequence('lib/qa_%s.cc' % self._info['modname'],
                                    '#include.*\n',
                                    '#include "%s"' % fname_qa_h)
            append_re_line_sequence('lib/qa_%s.cc' % self._info['modname'],
                                    '(addTest.*suite.*\n|new CppUnit.*TestSuite.*\n)',
                                    '\ts->addTest(gr::%s::qa_%s::suite());' % (self._info['modname'],
                                                                               self._info['blockname'])
                                    )


    def _run_swig(self):
        """ Do everything that needs doing in the subdir 'swig'.
        - Edit main *.i file
        """
        print "Traversing swig..."
        if self._get_mainswigfile() is None:
            print 'Warning: No main swig file found.'
            return
        print "Editing %s..." % self._file['swig']
        swig_block_magic_str = '\n%%include "%s/%s.h"\nGR_SWIG_BLOCK_MAGIC2(%s, %s);\n' % (
                                   self._info['modname'],
                                   self._info['blockname'],
                                   self._info['modname'],
                                   self._info['blockname'])
        include_str = '#include "%s/%s.h"' % (self._info['modname'], self._info['blockname'])
        if re.search('#include', open(self._file['swig'], 'r').read()):
            append_re_line_sequence(self._file['swig'], '^#include.*\n', include_str)
        else: # I.e., if the swig file is empty
            oldfile = open(self._file['swig'], 'r').read()
            regexp = re.compile('^%\{\n', re.MULTILINE)
            oldfile = regexp.sub('%%{\n%s\n' % include_str, oldfile, count=1)
            open(self._file['swig'], 'w').write(oldfile)
        open(self._file['swig'], 'a').write(swig_block_magic_str)


    def _run_python_qa(self):
        """ Do everything that needs doing in the subdir 'python' to add
        QA code.
        - add .py files
        - include in CMakeLists.txt
        """
        print "Traversing python..."
        fname_py_qa = 'qa_' + self._info['blockname'] + '.py'
        self._write_tpl('qa_python', 'python', fname_py_qa)
        os.chmod(os.path.join('python', fname_py_qa), 0755)
        print "Editing python/CMakeLists.txt..."
        open('python/CMakeLists.txt', 'a').write(
                'GR_ADD_TEST(qa_%s ${PYTHON_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/%s)\n' % \
                  (self._info['blockname'], fname_py_qa))

    def _run_python_hierblock(self):
        """ Do everything that needs doing in the subdir 'python' to add
        a Python hier_block.
        - add .py file
        - include in CMakeLists.txt
        """
        print "Traversing python..."
        fname_py = self._info['blockname'] + '.py'
        self._write_tpl('hier_python', 'python', fname_py)
        ed = CMakeFileEditor('python/CMakeLists.txt')
        ed.append_value('GR_PYTHON_INSTALL', fname_py, 'DESTINATION[^()]+')
        ed.write()
        append_re_line_sequence('python/__init__.py',
                                '(^from.*import.*\n|# import any pure.*\n)',
                                'from %s import *' % self._info['blockname'])

    def _run_grc(self):
        """ Do everything that needs doing in the subdir 'grc' to add
        a GRC bindings XML file.
        - add .xml file
        - include in CMakeLists.txt
        """
        print "Traversing grc..."
        fname_grc = self._info['fullblockname'] + '.xml'
        self._write_tpl('grc_xml', 'grc', fname_grc)
        print "Editing grc/CMakeLists.txt..."
        ed = CMakeFileEditor('grc/CMakeLists.txt', '\n    ')
        ed.append_value('install', fname_grc, 'DESTINATION[^()]+')
        ed.write()

