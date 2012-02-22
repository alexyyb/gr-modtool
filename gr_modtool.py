#!/usr/bin/env python
""" A tool for editing GNU Radio modules. """
# Copyright 2010 Communications Engineering Lab, KIT, Germany
#
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#

import sys
import os
import re
import glob
import base64
import tarfile
from datetime import datetime
from optparse import OptionParser, OptionGroup
from string import Template

### Utility functions ########################################################
def get_command_from_argv(possible_cmds):
    """ Read the requested command from argv. This can't be done with optparse,
    since the option parser isn't defined before the command is known, and
    optparse throws an error."""
    command = None
    for arg in sys.argv:
        if arg[0] == "-":
            continue
        else:
            command = arg
        if command in possible_cmds:
            return arg
    return None

def append_re_line_sequence(filename, linepattern, newline):
    """Detects the re 'linepattern' in the file. After its last occurrence,
    paste 'newline'. If the pattern does not exist, append the new line
    to the file. Then, write. """
    oldfile = open(filename, 'r').read()
    lines = re.findall(linepattern, oldfile, flags=re.MULTILINE)
    if len(lines) == 0:
        open(filename, 'a').write(newline)
        return
    last_line = lines[-1]
    newfile = oldfile.replace(last_line, last_line + newline + '\n')
    open(filename, 'w').write(newfile)

def remove_pattern_from_file(filename, pattern):
    """ Remove all occurrences of a given pattern from a file. """
    oldfile = open(filename, 'r').read()
    open(filename, 'w').write(re.sub(pattern, '', oldfile, flags=re.MULTILINE))

def str_to_fancyc_comment(text):
    """ Return a string as a C formatted comment. """
    l_lines = text.splitlines()
    outstr = "/* " + l_lines[0] + "\n"
    for line in l_lines[1:]:
        outstr += " * " + line + "\n"
    outstr += " */\n"
    return outstr

def str_to_python_comment(text):
    """ Return a string as a Python formatted comment. """
    return re.sub('^', '# ', text, flags=re.MULTILINE)

def get_modname():
    """ Grep the current module's name from gnuradio.project """
    try:
        prfile = open('gnuradio.project', 'r').read()
        regexp = r'projectname\s*=\s*([a-zA-Z0-9-_]+)$'
        return re.search(regexp, prfile, flags=re.MULTILINE).group(1).strip()
    except IOError:
        pass
    # OK, there's no gnuradio.project. So, we need to guess.
    cmfile = open('CMakeLists.txt', 'r').read()
    regexp = r'project\s*\(\s*gr-([a-zA-Z0-9-_]+)\s*CXX'
    return re.search(regexp, cmfile, flags=re.MULTILINE).group(1).strip()

def get_class_dict():
    " Return a dictionary of the available commands in the form command->class "
    classdict = {}
    for g in globals().values():
        try:
            if issubclass(g, ModTool):
                classdict[g.name] = g
                for a in g.aliases:
                    classdict[a] = g
        except (TypeError, AttributeError):
            pass
    return classdict

### Templates ################################################################
Templates = {}
# Default licence
Templates['defaultlicense'] = """
Copyright %d <+YOU OR YOUR COMPANY+>.

This is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 3, or (at your option)
any later version.

This software is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this software; see the file COPYING.  If not, write to
the Free Software Foundation, Inc., 51 Franklin Street,
Boston, MA 02110-1301, USA.
""" % datetime.now().year

Templates['work_h'] = """
	int work (int noutput_items,
		gr_vector_const_void_star &input_items,
		gr_vector_void_star &output_items);"""

Templates['generalwork_h'] = """
  int general_work (int noutput_items,
		    gr_vector_int &ninput_items,
		    gr_vector_const_void_star &input_items,
		    gr_vector_void_star &output_items);"""

# Header file of a sync/decimator/interpolator block
Templates['block_h'] = Template("""/* -*- c++ -*- */
$license
#ifndef INCLUDED_${fullblocknameupper}_H
#define INCLUDED_${fullblocknameupper}_H

#include <${modname}_api.h>
#include <$grblocktype.h>

class $fullblockname;
typedef boost::shared_ptr<$fullblockname> ${fullblockname}_sptr;

${modnameupper}_API ${fullblockname}_sptr ${modname}_make_$blockname ($arglist);

/*!
 * \\brief <+description+>
 *
 */
class ${modnameupper}_API $fullblockname : public $grblocktype
{
	friend ${modnameupper}_API ${fullblockname}_sptr ${modname}_make_$blockname ($argliststripped);

	$fullblockname ($argliststripped);

 public:
	~$fullblockname ();

$workfunc
};

#endif /* INCLUDED_${fullblocknameupper}_H */

""")


# Work functions for C++ GR blocks
Templates['work_cpp'] = """work (int noutput_items,
			gr_vector_const_void_star &input_items,
			gr_vector_void_star &output_items)
{
	const float *in = (const float *) input_items[0];
	float *out = (float *) output_items[0];

	// Do <+signal processing+>

	// Tell runtime system how many output items we produced.
	return noutput_items;
}
"""

Templates['generalwork_cpp'] = """general_work (int noutput_items,
			       gr_vector_int &ninput_items,
			       gr_vector_const_void_star &input_items,
			       gr_vector_void_star &output_items)
{
  const float *in = (const float *) input_items[0];
  float *out = (float *) output_items[0];

  // Tell runtime system how many input items we consumed on
  // each input stream.
  consume_each (noutput_items);

  // Tell runtime system how many output items we produced.
  return noutput_items;
}
"""

# C++ file of a GR block
Templates['block_cpp'] = Template("""/* -*- c++ -*- */
$license
#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <gr_io_signature.h>
#include <$fullblockname.h>


${fullblockname}_sptr
${modname}_make_$blockname ($argliststripped)
{
	return $sptr (new $fullblockname ($arglistnotypes));
}


$fullblockname::$fullblockname ($argliststripped)
	: $grblocktype ("$blockname",
		gr_make_io_signature ($inputsig),
		gr_make_io_signature ($outputsig)$decimation)
{
$constructorcontent}


$fullblockname::~$fullblockname ()
{
}
""")

Templates['block_cpp_workcall'] = Template("""

int
$fullblockname::$workfunc
""")

Templates['block_cpp_hierconstructor'] = """
	connect(self(), 0, d_firstblock, 0);
	// connect other blocks
	connect(d_lastblock, 0, self(), 0);
"""

# Header file for QA
Templates['qa_cmakeentry'] = Template("""
add_executable($basename $filename)
target_link_libraries($basename gnuradio-$modname $${Boost_LIBRARIES})
GR_ADD_TEST($basename $basename)
""")

# C++ file for QA
Templates['qa_cpp'] = Template("""/* -*- c++ -*- */
$license

#include <boost/test/unit_test.hpp>

BOOST_AUTO_TEST_CASE(qa_${fullblockname}_t1){
    BOOST_CHECK_EQUAL(2 + 2, 4);
    // BOOST_* test macros <+here+>
}

BOOST_AUTO_TEST_CASE(qa_${fullblockname}_t2){
    BOOST_CHECK_EQUAL(2 + 2, 4);
    // BOOST_* test macros <+here+>
}

""")

# Python QA code
Templates['qa_python'] = Template("""#!/usr/bin/env python
$license
#

from gnuradio import gr, gr_unittest
import ${modname}$swig

class qa_$blockname (gr_unittest.TestCase):

    def setUp (self):
        self.tb = gr.top_block ()

    def tearDown (self):
        self.tb = None

    def test_001_t (self):
        # set up fg
        self.tb.run ()
        # check data


if __name__ == '__main__':
    gr_unittest.main ()
""")


Templates['hier_python'] = Template('''$license

from gnuradio import gr

class $blockname(gr.hier_block2):
    def __init__(self, $arglist):
    """
    docstring
	"""
        gr.hier_block2.__init__(self, "$blockname",
				gr.io_signature($inputsig),  # Input signature
				gr.io_signature($outputsig)) # Output signature

        # Define blocks
        self.connect()

''')

# Implementation file, C++ header
Templates['impl_h'] = Template('''/* -*- c++ -*- */
$license
#ifndef INCLUDED_QA_${fullblocknameupper}_H
#define INCLUDED_QA_${fullblocknameupper}_H

class $fullblockname
{
 public:
	$fullblockname($arglist);
	~$fullblockname();


 private:

};

#endif /* INCLUDED_${fullblocknameupper}_H */

''')

# Implementation file, C++ source
Templates['impl_cpp'] = Template('''/* -*- c++ -*- */
$license

#include <$fullblockname.h>


$fullblockname::$fullblockname($argliststripped)
{
}


$fullblockname::~$fullblockname()
{
}
''')


Templates['grc_xml'] = Template('''<?xml version="1.0"?>
<block>
  <name>$blockname</name>
  <key>$fullblockname</key>
  <category>$modname</category>
  <import>import $modname</import>
  <make>$modname.$blockname($arglistnotypes)</make>
  <!-- Make one 'param' node for every Parameter you want settable from the GUI.
       Sub-nodes:
       * name
       * key (makes the value accessible as $$keyname, e.g. in the make node)
       * type -->
  <param>
    <name>...</name>
    <key>...</key>
    <type>...</type>
  </param>

  <!-- Make one 'sink' node per input. Sub-nodes:
       * name (an identifier for the GUI)
       * type
       * vlen
       * optional (set to 1 for optional inputs) -->
  <sink>
    <name>in</name>
    <type><!-- e.g. int, real, complex, byte, short, xxx_vector, ...--></type>
  </sink>

  <!-- Make one 'source' node per output. Sub-nodes:
       * name (an identifier for the GUI)
       * type
       * vlen
       * optional (set to 1 for optional inputs) -->
  <source>
    <name>out</name>
    <type><!-- e.g. int, real, complex, byte, short, xxx_vector, ...--></type>
  </source>
</block>
''')

# Usage
Templates['usage'] = """
gr_modtool.py <command> [options] -- Run <command> with the given options.
gr_modtool.py help -- Show a list of commands.
gr_modtool.py help <command> -- Shows the help for a given command. """

### Code generator class #####################################################
class CodeGenerator(object):
    """ Creates the skeleton files. """
    def __init__(self):
        self.defvalpatt = re.compile(" *=[^,)]*")
        self.grtypelist = {
                'sync': 'gr_sync_block',
                'decimator': 'gr_sync_decimator',
                'interpolator': 'gr_sync_interpolator',
                'general': 'gr_block',
                'hiercpp': 'gr_hier_block2',
                'impl': ''}

    def strip_default_values(self, string):
        """ Strip default values from a C++ argument list. """
        return self.defvalpatt.sub("", string)

    def strip_arg_types(self, string):
        """" Strip the argument types from a list of arguments
        Example: "int arg1, double arg2" -> "arg1, arg2" """
        string = self.strip_default_values(string)
        return ", ".join([part.strip().split(' ')[-1] for part in string.split(',')])

    def get_template(self, tpl_id, **kwargs):
        ''' Request a skeleton file from a template.
        First, it prepares a dictionary which the template generator
        can use to fill in the blanks, then it uses Python's
        Template() function to create the file contents. '''
        # Licence
        if tpl_id in ('block_h', 'block_cpp', 'qa_h', 'qa_cpp', 'impl_h', 'impl_cpp'):
            kwargs['license'] = str_to_fancyc_comment(kwargs['license'])
        elif tpl_id in ('qa_python', 'hier_python'):
            kwargs['license'] = str_to_python_comment(kwargs['license'])
        # Standard values for templates
        kwargs['argliststripped'] = self.strip_default_values(kwargs['arglist'])
        kwargs['arglistnotypes'] = self.strip_arg_types(kwargs['arglist'])
        kwargs['fullblocknameupper'] = kwargs['fullblockname'].upper()
        kwargs['modnameupper'] = kwargs['modname'].upper()
        kwargs['grblocktype'] = self.grtypelist[kwargs['blocktype']]
        # Specials for qa_python
        kwargs['swig'] = ''
        if kwargs['blocktype'] != 'hierpython':
            kwargs['swig'] = '_swig'
        # Specials for block_h
        if tpl_id == 'block_h':
            if kwargs['blocktype'] == 'general':
                kwargs['workfunc'] = Templates['generalwork_h']
            elif kwargs['blocktype'] == 'hiercpp':
                kwargs['workfunc'] = ''
            else:
                kwargs['workfunc'] = Templates['work_h']
        # Specials for block_cpp
        if tpl_id == 'block_cpp':
            return self._get_block_cpp(kwargs)
        # All other ones
        return Templates[tpl_id].substitute(kwargs)

    def _get_block_cpp(self, kwargs):
        '''This template is a bit fussy, so it needs some extra attention.'''
        kwargs['decimation'] = ''
        kwargs['constructorcontent'] = ''
        kwargs['sptr'] = kwargs['fullblockname'] + '_sptr'
        if kwargs['blocktype'] == 'decimator':
            kwargs['decimation'] = ", <+decimation+>"
        elif kwargs['blocktype'] == 'interpolator':
            kwargs['decimation'] = ", <+interpolation+>"
        if kwargs['blocktype'] == 'general':
            kwargs['workfunc'] = Templates['generalwork_cpp']
        elif kwargs['blocktype'] == 'hiercpp':
            kwargs['workfunc'] = ''
            kwargs['constructorcontent'] = Templates['block_cpp_hierconstructor']
            kwargs['sptr'] = 'gnuradio::get_initial_sptr'
            return Templates['block_cpp'].substitute(kwargs)
        else:
            kwargs['workfunc'] = Templates['work_cpp']
        return Templates['block_cpp'].substitute(kwargs) + \
               Templates['block_cpp_workcall'].substitute(kwargs)

### CMakeFile.txt editor class ###############################################
class CMakeFileEditor(object):
    """A tool for editing CMakeLists.txt files. """
    def __init__(self, filename, separator=' '):
        self.filename = filename
        fid = open(filename, 'r')
        self.cfile = fid.read()
        self.separator = separator

    def get_entry_value(self, entry, to_ignore=''):
        """ Get the value of an entry.
        to_ignore is the part of the entry you don't care about. """
        regexp = '%s\(%s([^()]+)\)' % (entry, to_ignore)
        mobj = re.search(regexp, self.cfile, flags=re.MULTILINE)
        if mobj is None:
            return None
        value = mobj.groups()[0].strip()
        return value

    def append_value(self, entry, value, to_ignore=''):
        """ Add a value to an entry. """
        regexp = '(%s\([^()]*?)\s*?(\s?%s)\)' % (entry, to_ignore)
        substi = r'\1' + self.separator + value + r'\2)'
        self.cfile = re.sub(regexp, substi, self.cfile,
                            count=1, flags=re.MULTILINE)

    def remove_value(self, entry, value, to_ignore=''):
        """Remove a value from an entry."""
        regexp = '^\s*(%s\(\s*%s[^()]*?\s*)%s\s*([^()]*\))' % (entry, to_ignore, value)
        self.cfile = re.sub(regexp, r'\1\2', self.cfile, count=1, flags=re.MULTILINE)

    def delete_entry(self, entry, value_pattern=''):
        """Remove an entry from the current buffer."""
        regexp = '%s\s*\([^()]*%s[^()]*\)[^\n]*\n' % (entry, value_pattern)
        self.cfile = re.sub(regexp, '', self.cfile, count=1, flags=re.MULTILINE)

    def write(self):
        """ Write the changes back to the file. """
        open(self.filename, 'w').write(self.cfile)

    def remove_double_newlines(self):
        """Simply clear double newlines from the file buffer."""
        self.cfile = re.sub('\n\n\n+', '\n\n', self.cfile, flags=re.MULTILINE)

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
        ogroup.add_option("--skip-grc", action="store_true", default=True,
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

        if options.module_name is not None:
            self._info['modname'] = options.module_name
        else:
            self._info['modname'] = get_modname()
        print "GNU Radio module name identified: " + self._info['modname']
        self._info['blockname'] = options.block_name
        self.options = options


    def run(self):
        """ Override this. """
        pass


    def _check_directory(self, directory):
        """ Guesses if dir is a valid GNU Radio module directory by looking for
        gnuradio.project and at least one of the subdirs lib/, python/ and swig/.
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
                    re.search('find_package\(GnuradioCore\)', open(f).read()) is not None):
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


### Add new block module #####################################################
class ModToolAdd(ModTool):
    """ Add block to the out-of-tree module. """
    name = 'add'
    aliases = ('insert',)
    _block_types = ('sink', 'source', 'sync', 'decimator', 'interpolator',
                    'general', 'hiercpp', 'hierpython', 'impl')
    def __init__(self):
        ModTool.__init__(self)
        self._info['inputsig'] = "<+MIN_IN+>, <+MAX_IN+>, sizeof (<+float+>)"
        self._info['outputsig'] = "<+MIN_IN+>, <+MAX_IN+>, sizeof (<+float+>)"
        self._add_cc_qa = False
        self._add_py_qa = False


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

        self._info['prefix'] = self._info['modname']
        if self._info['blocktype'] == 'impl':
            self._info['prefix'] += 'i'
        self._info['fullblockname'] = self._info['prefix'] + '_' + self._info['blockname']
        print "Full block/code identifier is: " + self._info['fullblockname']

        self._info['license'] = self.setup_choose_license()

        if options.argument_list is not None:
            self._info['arglist'] = options.argument_list
        else:
            self._info['arglist'] = raw_input('Enter valid argument list, including default arguments: ')

        if not (self._info['blocktype'] in ('impl') or self._skip_subdirs['python']):
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
        - add .cc and .h files
        - include them into CMakeLists.txt
        - check if C++ QA code is req'd
        - if yes, create qa_*.{cc,h} and add them to CMakeLists.txt
        """
        print "Traversing lib..."
        fname_h = self._info['fullblockname'] + '.h'
        fname_cc = self._info['fullblockname'] + '.cc'
        if self._info['blocktype'] in ('source', 'sink', 'sync', 'decimator',
                                       'interpolator', 'general', 'hiercpp'):
            self._write_tpl('block_h', 'include', fname_h)
            self._write_tpl('block_cpp', 'lib', fname_cc)
        elif self._info['blocktype'] == 'impl':
            self._write_tpl('impl_h', 'include', fname_h)
            self._write_tpl('impl_cpp', 'lib', fname_cc)
        if not self.options.skip_cmakefiles:
            ed = CMakeFileEditor('lib/CMakeLists.txt')
            ed.append_value('add_library', fname_cc)
            ed.write()
            ed = CMakeFileEditor('include/CMakeLists.txt', '\n    ')
            ed.append_value('install', fname_h, 'DESTINATION[^()]+')
            ed.write()

        if not self._add_cc_qa:
            return
        fname_qa_cc = 'qa_%s' % fname_cc
        self._write_tpl('qa_cpp', 'lib', fname_qa_cc)
        if not self.options.skip_cmakefiles:
            open('lib/CMakeLists.txt', 'a').write(Template.substitute(Templates['qa_cmakeentry'],
                                          {'basename': os.path.splitext(fname_qa_cc)[0],
                                           'filename': fname_qa_cc,
                                           'modname': self._info['modname']}))
            ed = CMakeFileEditor('lib/CMakeLists.txt')
            ed.remove_double_newlines()
            ed.write()

    def _run_swig(self):
        """ Do everything that needs doing in the subdir 'swig'.
        - Edit main *.i file
        """
        print "Traversing swig..."
        fname_mainswig = self._get_mainswigfile()
        if fname_mainswig is None:
            print 'Warning: No main swig file found.'
            return
        fname_mainswig = os.path.join('swig', fname_mainswig)
        print "Editing %s..." % fname_mainswig
        swig_block_magic_str = 'GR_SWIG_BLOCK_MAGIC(%s,%s);\n%%include "%s"\n' % (
                                   self._info['modname'],
                                   self._info['blockname'],
                                   self._info['fullblockname'] + '.h')
        if re.search('#include', open(fname_mainswig, 'r').read()):
            append_re_line_sequence(fname_mainswig, '^#include.*\n',
                    '#include "%s.h"' % self._info['fullblockname'])
            append_re_line_sequence(fname_mainswig,
                                    '^GR_SWIG_BLOCK_MAGIC\(.*?\);\s*?\%include.*\s*',
                                    swig_block_magic_str)
        else: # I.e., if the swig file is empty
            oldfile = open(fname_mainswig, 'r').read()
            oldfile = re.sub('^%\{\n', '%%{\n#include "%s.h"\n' % self._info['fullblockname'],
                           oldfile, count=1, flags=re.MULTILINE)
            oldfile = re.sub('^%\}\n', '%}\n\n' + swig_block_magic_str,
                           oldfile, count=1, flags=re.MULTILINE)
            open(fname_mainswig, 'w').write(oldfile)


    def _run_python_qa(self):
        """ Do everything that needs doing in the subdir 'python' to add
        QA code.
        - add .py files
        - include in CMakeLists.txt
        """
        print "Traversing python..."
        fname_py_qa = 'qa_' + self._info['fullblockname'] + '.py'
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

### Remove module ###########################################################
class ModToolRemove(ModTool):
    """ Remove block (delete files and remove Makefile entries) """
    name = 'remove'
    aliases = ('rm', 'del')
    def __init__(self):
        ModTool.__init__(self)

    def setup_parser(self):
        " Initialise the option parser for 'gr_modtool.py rm' "
        parser = ModTool.setup_parser(self)
        parser.usage = '%prog rm [options]. \n Call %prog without any options to run it interactively.'
        ogroup = OptionGroup(parser, "Remove module options")
        ogroup.add_option("-p", "--pattern", type="string", default=None,
                help="Filter possible choices for blocks to be deleted.")
        ogroup.add_option("-y", "--yes", action="store_true", default=False,
                help="Answer all questions with 'yes'.")
        parser.add_option_group(ogroup)
        return parser

    def setup(self):
        ModTool.setup(self)
        options = self.options
        if options.pattern is not None:
            self._info['pattern'] = options.pattern
        elif options.block_name is not None:
            self._info['pattern'] = options.block_name
        elif len(self.args) >= 2:
            self._info['pattern'] = self.args[1]
        else:
            self._info['pattern'] = raw_input('Which blocks do you want to delete? (Regex): ')
        if len(self._info['pattern']) == 0:
            self._info['pattern'] = '.'
        self._info['yes'] = options.yes

    def run(self):
        """ Go, go, go! """
        def _remove_cc_test_case(filename=None, ed=None):
            """ Special function that removes the occurrences of a qa*.cc file
            from the CMakeLists.txt. """
            if filename[:2] != 'qa':
                return
            filebase = os.path.splitext(filename)[0]
            ed.delete_entry('add_executable', filebase)
            ed.delete_entry('target_link_libraries', filebase)
            ed.delete_entry('GR_ADD_TEST', filebase)
            ed.remove_double_newlines()

        def _make_swig_regex(filename):
            filebase = os.path.splitext(filename)[0]
            pyblockname = filebase.replace(self._info['modname'] + '_', '')
            regexp = r'^\s*GR_SWIG_BLOCK_MAGIC\(%s,\s*%s\);\s*%%include\s*"%s"\s*' % \
                    (self._info['modname'], pyblockname, filename)
            return regexp

        if not self._skip_subdirs['lib']:
            self._run_subdir('lib', ('*.cc', '*.h'), ('add_library',),
                             cmakeedit_func=_remove_cc_test_case)
        if not self._skip_subdirs['include']:
            incl_files_deleted = self._run_subdir('include', ('*.cc', '*.h'), ('install',),
                             cmakeedit_func=_remove_cc_test_case)
        if not self._skip_subdirs['swig']:
            for f in incl_files_deleted:
                remove_pattern_from_file('swig/'+self._get_mainswigfile(), _make_swig_regex(f))
                remove_pattern_from_file('swig/'+self._get_mainswigfile(), '#include "%s"' % f)
        if not self._skip_subdirs['python']:
            py_files_deleted = self._run_subdir('python', ('*.py',), ('GR_PYTHON_INSTALL',))
            for f in py_files_deleted:
                remove_pattern_from_file('python/__init__.py', '.*import.*%s.*' % f[:-3])
        if not self._skip_subdirs['grc']:
            self._run_subdir('grc', ('*.xml',), ('install',))


    def _run_subdir(self, path, globs, makefile_vars, cmakeedit_func=None):
        """ Delete all files that match a certain pattern in path.
        path - The directory in which this will take place
        globs - A tuple of standard UNIX globs of files to delete (e.g. *.xml)
        makefile_vars - A tuple with a list of CMakeLists.txt-variables which
                        may contain references to the globbed files
        cmakeedit_func - If the CMakeLists.txt needs special editing, use this
        """
        # 1. Create a filtered list
        files = []
        for g in globs:
            files = files + glob.glob("%s/%s"% (path, g))
        files_filt = []
        print "Searching for matching files in %s/:" % path
        for f in files:
            if re.search(self._info['pattern'], os.path.basename(f)) is not None:
                files_filt.append(f)
            if path is "swig":
                files_filt.append(f)
        if len(files_filt) == 0:
            print "None found."
            return []
        # 2. Delete files, Makefile entries and other occurences
        files_deleted = []
        ed = CMakeFileEditor('%s/CMakeLists.txt' % path)
        yes = self._info['yes']
        for f in files_filt:
            b = os.path.basename(f)
            if not yes:
                ans = raw_input("Really delete %s? [Y/n/a/q]: " % f).lower().strip()
                if ans == 'a':
                    yes = True
                if ans == 'q':
                    sys.exit(0)
                if ans == 'n':
                    continue
            files_deleted.append(b)
            print "Deleting %s." % f
            os.unlink(f)
            print "Deleting occurrences of %s from %s/CMakeLists.txt..." % (b, path)
            for var in makefile_vars:
                ed.remove_value(var, b)
            if cmakeedit_func is not None:
                cmakeedit_func(b, ed)
        ed.write()
        return files_deleted


### The entire new module zipfile as base64 encoded tar.bz2  ###
NEWMOD_TARFILE = """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
OH+7p43oQuECAd76AFf/+LuSKcKEhWmtpeA="""
### New out-of-tree-mod module ###############################################
class ModToolNewModule(ModTool):
    """ Create a new out-of-tree module """
    name = 'newmod'
    aliases = ('nm', 'create')
    def __init__(self):
        ModTool.__init__(self)

    def setup_parser(self):
        " Initialise the option parser for 'gr_modtool.py newmod' "
        parser = ModTool.setup_parser(self)
        #parser.usage = '%prog rm [options]. \n Call %prog without any options to run it interactively.'
        #ogroup = OptionGroup(parser, "New out-of-tree module options")
        #parser.add_option_group(ogroup)
        return parser

    def setup(self):
        (options, self.args) = self.parser.parse_args()
        self._info['modname'] = options.module_name
        if self._info['modname'] is None:
            if len(self.args) >= 2:
                self._info['modname'] = self.args[1]
            else:
                self._info['modname'] = raw_input('Name of the new module: ')
        if not re.match('[a-zA-Z0-9_]+', self._info['modname']):
            print 'Invalid module name.'
            sys.exit(2)
        self._dir = options.directory
        if self._dir == '.':
            self._dir = './gr-%s' % self._info['modname']
        print 'Module directory is "%s".' % self._dir
        try:
            os.stat(self._dir)
        except OSError:
            pass # This is what should happen
        else:
            print 'The given directory exists.'
            sys.exit(2)

    def run(self):
        """ Go, go, go! """
        print "Creating directory..."
        try:
            os.mkdir(self._dir)
            os.chdir(self._dir)
        except OSError:
            print 'Could not create directory %s. Quitting.' % self._dir
            sys.exit(2)
        print "Copying howto example..."
        open('tmp.tar.bz2', 'wb').write(base64.b64decode(NEWMOD_TARFILE))
        print "Unpacking..."
        tar = tarfile.open('tmp.tar.bz2', mode='r:bz2')
        tar.extractall()
        tar.close()
        os.unlink('tmp.tar.bz2')
        print "Replacing occurences of 'howto' to '%s'..." % self._info['modname']
        skip_dir_re = re.compile('^..cmake|^..apps|^..grc|doxyxml')
        for root, dirs, files in os.walk('.'):
            if skip_dir_re.search(root):
                continue
            for filename in files:
                f = os.path.join(root, filename)
                s = open(f, 'r').read()
                s = s.replace('howto', self._info['modname'])
                s = s.replace('HOWTO', self._info['modname'].upper())
                open(f, 'w').write(s)
                if filename[0:5] == 'howto':
                    newfilename = filename.replace('howto', self._info['modname'])
                    os.rename(f, os.path.join(root, newfilename))
        print "Done."
        print "Use 'gr_modtool add' to add a new block to this currently empty module."


### Help module ##############################################################
def print_class_descriptions():
    ''' Go through all ModTool* classes and print their name,
        alias and description. '''
    desclist = []
    for gvar in globals().values():
        try:
            if issubclass(gvar, ModTool) and not issubclass(gvar, ModToolHelp):
                desclist.append((gvar.name, ','.join(gvar.aliases), gvar.__doc__))
        except (TypeError, AttributeError):
            pass
    print 'Name      Aliases          Description'
    print '====================================================================='
    for description in desclist:
        print '%-8s  %-12s    %s' % description

class ModToolHelp(ModTool):
    ''' Show some help. '''
    name = 'help'
    aliases = ('h', '?')
    def __init__(self):
        ModTool.__init__(self)

    def setup(self):
        pass

    def run(self):
        cmd_dict = get_class_dict()
        cmds = cmd_dict.keys()
        cmds.remove(self.name)
        for a in self.aliases:
            cmds.remove(a)
        help_requested_for = get_command_from_argv(cmds)
        if help_requested_for is None:
            print 'Usage:' + Templates['usage']
            print '\nList of possible commands:\n'
            print_class_descriptions()
            return
        cmd_dict[help_requested_for]().setup_parser().print_help()

### Main code ################################################################
def main():
    """ Here we go. Parse command, choose class and run. """
    cmd_dict = get_class_dict()
    command = get_command_from_argv(cmd_dict.keys())
    if command is None:
        print 'Usage:' + Templates['usage']
        sys.exit(2)
    modtool = cmd_dict[command]()
    modtool.setup()
    modtool.run()

if __name__ == '__main__':
    if not ((sys.version_info[0] > 2) or
            (sys.version_info[0] == 2 and sys.version_info[1] >= 7)):
        print "Python 2.7 required."
        sys.exit(1)
    main()

