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
import Cheetah.Template
import xml.etree.ElementTree as ET

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
    pattern = re.compile(pattern, re.MULTILINE)
    open(filename, 'w').write(pattern.sub('', oldfile))

def strip_default_values(string):
    """ Strip default values from a C++ argument list. """
    return re.sub(' *=[^,)]*', '', string)

def strip_arg_types(string):
    """" Strip the argument types from a list of arguments
    Example: "int arg1, double arg2" -> "arg1, arg2" """
    string = strip_default_values(string)
    return ", ".join([part.strip().split(' ')[-1] for part in string.split(',')])

def get_modname():
    """ Grep the current module's name from gnuradio.project or CMakeLists.txt """
    try:
        prfile = open('gnuradio.project', 'r').read()
        regexp = r'projectname\s*=\s*([a-zA-Z0-9-_]+)$'
        return re.search(regexp, prfile, flags=re.MULTILINE).group(1).strip()
    except IOError:
        pass
    # OK, there's no gnuradio.project. So, we need to guess.
    cmfile = open('CMakeLists.txt', 'r').read()
    regexp = r'(project\s*\(\s*|GR_REGISTER_COMPONENT\(")gr-([a-zA-Z1-9-_]+)(\s*CXX|" ENABLE)'
    return re.search(regexp, cmfile, flags=re.MULTILINE).group(2).strip()

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

def is_number(s):
    " Return True if the string s contains a number. "
    try:
        float(s)
        return True
    except ValueError:
        return False

def xml_indent(elem, level=0):
    """ Adds indents to XML for pretty printing """
    i = "\n" + level*"    "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "    "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            xml_indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
### Templates ################################################################
Templates = {}
# Default licence
Templates['defaultlicense'] = '''
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
''' % datetime.now().year

# Header file of a sync/decimator/interpolator block
Templates['block_impl_h'] = '''/* -*- c++ -*- */
${str_to_fancyc_comment($license)}
\#ifndef INCLUDED_${modname.upper()}_${blockname.upper()}_IMPL_H
\#define INCLUDED_${modname.upper()}_${blockname.upper()}_IMPL_H

\#include <${modname}/${blockname}.h>

namespace gr {
  namespace ${modname} {

    class ${blockname}_impl : public ${blockname}
    {
    private:
      // Nothing to declare in this block.

    public:
      ${blockname}_impl(${strip_default_values($arglist)});
      ~${blockname}_impl();

#if $grblocktype == 'gr_block'
      // Where all the action really happens
      int general_work(int noutput_items,
		       gr_vector_int &ninput_items,
		       gr_vector_const_void_star &input_items,
		       gr_vector_void_star &output_items);
#else if $grblocktype == 'gr_hier_block2'
#silent pass
#else
      // Where all the action really happens
      int work(int noutput_items,
	       gr_vector_const_void_star &input_items,
	       gr_vector_void_star &output_items);
#end if
    };

  } // namespace ${modname}
} // namespace gr

\#endif /* INCLUDED_${modname.upper()}_${blockname.upper()}_IMPL_H */

'''

# C++ file of a GR block
Templates['block_impl_cpp'] = '''/* -*- c++ -*- */
${str_to_fancyc_comment($license)}
\#ifdef HAVE_CONFIG_H
\#include "config.h"
\#endif

\#include <gr_io_signature.h>
\#include "${blockname}_impl.h"

namespace gr {
  namespace ${modname} {

    ${blockname}::sptr
    ${blockname}::make(${strip_default_values($arglist)})
    {
      return gnuradio::get_initial_sptr (new ${blockname}_impl(${strip_arg_types($arglist)}));
    }

#if $grblocktype == 'gr_sync_decimator'
#set $decimation = ', <+decimation+>'
#else if $grblocktype == 'gr_sync_interpolator'
#set $decimation = ', <+interpolation+>'
#else
#set $decimation = ''
#end if
    /*
     * The private constructor
     */
    ${blockname}_impl::${blockname}_impl(${strip_default_values($arglist)})
      : ${grblocktype}("${blockname}",
		      gr_make_io_signature($inputsig),
		      gr_make_io_signature($outputsig)$decimation)
#if $grblocktype == 'gr_hier_block2'
    {
        connect(self(), 0, d_firstblock, 0);
        // connect other blocks
        connect(d_lastblock, 0, self(), 0);
    }
#else
    {}
#end if

    /*
     * Our virtual destructor.
     */
    ${blockname}_impl::~${blockname}_impl()
    {
    }

#if $grblocktype == 'gr_block'
    int
    ${blockname}_impl::general_work (int noutput_items,
                       gr_vector_int &ninput_items,
                       gr_vector_const_void_star &input_items,
                       gr_vector_void_star &output_items)
    {
        const float *in = (const float *) input_items[0];
        float *out = (float *) output_items[0];

        // Do <+signal processing+>
        // Tell runtime system how many input items we consumed on
        // each input stream.
        consume_each (noutput_items);

        // Tell runtime system how many output items we produced.
        return noutput_items;
    }

#else if $grblocktype == 'gr_hier_block2'
#silent pass
#else
    int
    ${blockname}_impl::work(int noutput_items,
			  gr_vector_const_void_star &input_items,
			  gr_vector_void_star &output_items)
    {
        const float *in = (const float *) input_items[0];
        float *out = (float *) output_items[0];

        // Do <+signal processing+>

        // Tell runtime system how many output items we produced.
        return noutput_items;
    }
#end if

  } /* namespace ${modname} */
} /* namespace gr */

'''

# Block definition header file (for include/)
Templates['block_def_h'] = '''/* -*- c++ -*- */
${str_to_fancyc_comment($license)}

\#ifndef INCLUDED_${modname.upper()}_${blockname.upper()}_H
\#define INCLUDED_${modname.upper()}_${blockname.upper()}_H

\#include <${modname}/api.h>
\#include <${grblocktype}.h>

namespace gr {
  namespace ${modname} {

    /*!
     * \\brief <+description of block+>
     * \ingroup block
     *
     */
    class ${modname.upper()}_API ${blockname} : virtual public $grblocktype
    {
    public:
       typedef boost::shared_ptr<${blockname}> sptr;

       /*!
	* \\brief Return a shared_ptr to a new instance of ${modname}::${blockname}.
	*
	* To avoid accidental use of raw pointers, ${modname}::${blockname}'s
	* constructor is in a private implementation
	* class. ${modname}::${blockname}::make is the public interface for
	* creating new instances.
	*/
       static sptr make($arglist);
    };

  } // namespace ${modname}
} // namespace gr

\#endif /* INCLUDED_${modname.upper()}_${blockname.upper()}_H */

'''

# C++ file for QA
Templates['qa_cpp'] = '''/* -*- c++ -*- */
${str_to_fancyc_comment($license)}

\#include "qa_${blockname}.h"
\#include <cppunit/TestAssert.h>

\#include <$modname/${blockname}.h>

namespace gr {
  namespace ${modname} {

    void
    qa_${blockname}::t1()
    {
        // Put test here
    }

  } /* namespace ${modname} */
} /* namespace gr */

'''

# Header file for QA
Templates['qa_h'] = '''/* -*- c++ -*- */
${str_to_fancyc_comment($license)}

\#ifndef _QA_${blockname.upper()}_H_
\#define _QA_${blockname.upper()}_H_

\#include <cppunit/extensions/HelperMacros.h>
\#include <cppunit/TestCase.h>

namespace gr {
  namespace ${modname} {

    class qa_${blockname} : public CppUnit::TestCase
    {
    public:
      CPPUNIT_TEST_SUITE(qa_${blockname});
      CPPUNIT_TEST(t1);
      CPPUNIT_TEST_SUITE_END();

    private:
      void t1();
    };

  } /* namespace ${modname} */
} /* namespace gr */

#endif /* _QA_${blockname.upper()}_H_ */

'''

# Python QA code
Templates['qa_python'] = '''\#!/usr/bin/env python
${str_to_python_comment($license)}
#

from gnuradio import gr, gr_unittest
import ${modname}_swig as ${modname}

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
    gr_unittest.run(qa_${blockname}, "qa_${blockname}.xml")
'''


# Hierarchical block, Python version
Templates['hier_python'] = '''${str_to_python_comment($license)}

from gnuradio import gr

class ${blockname}(gr.hier_block2):
    def __init__(self#if $arglist == '' then '' else ', '#$arglist):
    """
    docstring
	"""
        gr.hier_block2.__init__(self, "$blockname",
				gr.io_signature(${inputsig}),  # Input signature
				gr.io_signature(${outputsig})) # Output signature

        # Define blocks and connect them
        self.connect()

'''

# Non-block file, C++ header
Templates['noblock_h'] = '''/* -*- c++ -*- */
${str_to_fancyc_comment($license)}
\#ifndef INCLUDED_${modname.upper()}_${blockname.upper()}_H
\#define INCLUDED_${modname.upper()}_${blockname.upper()}_H

\#include <${modname}/api.h>

namespace gr {
  namespace ${modname} {
    class ${modname.upper()}_API $blockname
    {
        ${blockname}(${arglist});
        ~${blockname}();
        private:
    };

  }  /* namespace ${modname} */
}  /* namespace gr */


\#endif /* INCLUDED_${modname.upper()}_${blockname.upper()}_H */

'''

# Non-block file, C++ source
Templates['noblock_cpp'] = '''/* -*- c++ -*- */
${str_to_fancyc_comment($license)}

\#ifdef HAVE_CONFIG_H
\#include <config.h>
\#endif

\#include <${modname}/${blockname}.h>

namespace gr {
  namespace ${modname} {

    $blockname::${blockname}(${strip_default_values($arglist)})
    {
    }

    $blockname::~${blockname}()
    {
    }

  }  /* namespace $blockname */
}  /* namespace gr */

'''


Templates['grc_xml'] = '''<?xml version="1.0"?>
<block>
  <name>$blockname</name>
  <key>${modname}_$blockname</key>
  <category>$modname</category>
  <import>import $modname</import>
  <make>${modname}.${blockname}(${strip_arg_types($arglist)})</make>
  <!-- Make one 'param' node for every Parameter you want settable from the GUI.
       Sub-nodes:
       * name
       * key (makes the value accessible as \$keyname, e.g. in the make node)
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
'''

# Usage
Templates['usage'] = '''
gr_modtool.py <command> [options] -- Run <command> with the given options.
gr_modtool.py help -- Show a list of commands.
gr_modtool.py help <command> -- Shows the help for a given command. '''

### Code generator class #####################################################
class GRMTemplate(Cheetah.Template.Template):
    """ An extended template class """
    def __init__(self, src, searchList=[]):
        self.grtypelist = {
                'sync': 'gr_sync_block',
                'decimator': 'gr_sync_decimator',
                'interpolator': 'gr_sync_interpolator',
                'general': 'gr_block',
                'hiercpp': 'gr_hier_block2',
                'noblock': '',
                'hierpython': ''}
        Cheetah.Template.Template.__init__(self, src, searchList=searchList)
        self.grblocktype = self.grtypelist[searchList['blocktype']]
    def strip_default_values(string):
        """ Strip default values from a C++ argument list. """
        return re.compile(" *=[^,)]*").sub("", string)
    def strip_arg_types(string):
        """" Strip the argument types from a list of arguments
        Example: "int arg1, double arg2" -> "arg1, arg2" """
        string = re.compile(" *=[^,)]*").sub("", string) # FIXME this should call strip_arg_types
        return ", ".join([part.strip().split(' ')[-1] for part in string.split(',')])
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
        return re.compile('^', re.MULTILINE).sub('# ', text)

def get_template(tpl_id, **kwargs):
    """ Return the template given by tpl_id, parsed through Cheetah """
    return str(GRMTemplate(Templates[tpl_id], searchList=kwargs))
### CMakeFile.txt editor class ###############################################
class CMakeFileEditor(object):
    """A tool for editing CMakeLists.txt files. """
    def __init__(self, filename, separator=' ', indent='    '):
        self.filename = filename
        self.cfile = open(filename, 'r').read()
        self.separator = separator
        self.indent = indent

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
        regexp = re.compile('(%s\([^()]*?)\s*?(\s?%s)\)' % (entry, to_ignore),
                            re.MULTILINE)
        substi = r'\1' + self.separator + value + r'\2)'
        self.cfile = regexp.sub(substi, self.cfile, count=1)

    def remove_value(self, entry, value, to_ignore=''):
        """Remove a value from an entry."""
        regexp = '^\s*(%s\(\s*%s[^()]*?\s*)%s\s*([^()]*\))' % (entry, to_ignore, value)
        regexp = re.compile(regexp, re.MULTILINE)
        self.cfile = re.sub(regexp, r'\1\2', self.cfile, count=1)

    def delete_entry(self, entry, value_pattern=''):
        """Remove an entry from the current buffer."""
        regexp = '%s\s*\([^()]*%s[^()]*\)[^\n]*\n' % (entry, value_pattern)
        regexp = re.compile(regexp, re.MULTILINE)
        self.cfile = re.sub(regexp, '', self.cfile, count=1)

    def write(self):
        """ Write the changes back to the file. """
        open(self.filename, 'w').write(self.cfile)

    def remove_double_newlines(self):
        """Simply clear double newlines from the file buffer."""
        self.cfile = re.compile('\n\n\n+', re.MULTILINE).sub('\n\n', self.cfile)

    def find_filenames_match(self, regex):
        """ Find the filenames that match a certain regex
        on lines that aren't comments """
        filenames = []
        reg = re.compile(regex)
        fname_re = re.compile('[a-zA-Z]\w+\.\w{1,5}$')
        for line in self.cfile.splitlines():
            if len(line.strip()) == 0 or line.strip()[0] == '#': continue
            for word in re.split('[ /)(\t\n\r\f\v]', line):
                if fname_re.match(word) and reg.search(word):
                    filenames.append(word)
        return filenames

    def disable_file(self, fname):
        """ Comment out a file """
        starts_line = False
        for line in self.cfile.splitlines():
            if len(line.strip()) == 0 or line.strip()[0] == '#': continue
            if re.search(r'\b'+fname+r'\b', line):
                if re.match(fname, line.lstrip()):
                    starts_line = True
                break
        comment_out_re = r'#\1' + '\n' + self.indent
        if not starts_line:
            comment_out_re = r'\n' + self.indent + comment_out_re
        (self.cfile, nsubs) = re.subn(r'(\b'+fname+r'\b)\s*', comment_out_re, self.cfile)
        if nsubs == 0:
            print "Warning: A replacement failed when commenting out %s. Check the CMakeFile.txt manually." % fname
        elif nsubs > 1:
            print "Warning: Replaced %s %d times (instead of once). Check the CMakeFile.txt manually." % (fname, nsubs)


    def comment_out_lines(self, pattern, comment_str='#'):
        """ Comments out all lines that match with pattern """
        for line in self.cfile.splitlines():
            if re.search(pattern, line):
                self.cfile = self.cfile.replace(line, comment_str+line)

### ModTool base class #######################################################
class ModTool(object):
    """ Base class for all modtool command classes. """
    def __init__(self):
        self._subdirs = ['lib', 'include', 'python', 'swig', 'grc'] # List subdirs where stuff happens
        self._has_subdirs = {}
        self._skip_subdirs = {}
        self._info = {}
        self._file = {}
        for subdir in self._subdirs:
            self._has_subdirs[subdir] = False
            self._skip_subdirs[subdir] = False
        self.parser = self.setup_parser()
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

    def _setup_files(self):
        """ Initialise the self._file[] dictionary """
        self._file['swig'] = os.path.join('swig', self._get_mainswigfile())
        self._file['qalib'] = os.path.join('lib', 'qa_%s.cc' % self._info['modname'])
        self._file['pyinit'] = os.path.join('python', '__init__.py')
        self._file['cmlib'] = os.path.join('lib', 'CMakeLists.txt')
        self._file['cmgrc'] = os.path.join('lib', 'CMakeLists.txt')
        self._file['cmpython'] = os.path.join('python', 'CMakeLists.txt')
        self._file['cminclude'] = os.path.join('lib', self._info['modname'], 'CMakeLists.txt')
        self._file['cmswig'] = os.path.join('swig', 'CMakeLists.txt')


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
        self._setup_files()


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
        open(os.path.join(path, fname), 'w').write(get_template(tpl, **self._info))

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
            """ Special function that removes the occurrences of a qa*.{cc,h} file
            from the CMakeLists.txt and the qa_$modname.cc. """
            if filename[:2] != 'qa':
                return
            (base, ext) = os.path.splitext(filename)
            if ext == '.h':
                remove_pattern_from_file(self._file['qalib'],
                                         '^#include "%s"\s*$' % filename)
                remove_pattern_from_file(self._file['qalib'],
                                         '^\s*s->addTest\(gr::%s::%s::suite\(\)\);\s*$' % (self._info['modname'], base))
            elif ext == '.cc':
                ed.remove_value('list',
                                '\$\{CMAKE_CURRENT_SOURCE_DIR\}/%s' % filename,
                                'APPEND test_%s_sources' % self._info['modname'])

        def _remove_py_test_case(filename=None, ed=None):
            """ Special function that removes the occurrences of a qa*.py file
            from the CMakeLists.txt. """
            if filename[:2] != 'qa':
                return
            filebase = os.path.splitext(filename)[0]
            ed.delete_entry('GR_ADD_TEST', filebase)
            ed.remove_double_newlines()

        if not self._skip_subdirs['lib']:
            self._run_subdir('lib', ('*.cc', '*.h'), ('add_library',),
                             cmakeedit_func=_remove_cc_test_case)
        if not self._skip_subdirs['include']:
            incl_files_deleted = self._run_subdir(self._info['includedir'], ('*.h',), ('install',))
        if not self._skip_subdirs['swig']:
            swig_files_deleted = self._run_subdir('swig', ('*.i',), ('install',))
            print "Checking if lines have to be removed from %s..." % self._file['swig']
            for f in incl_files_deleted + swig_files_deleted:
                remove_pattern_from_file(self._file['swig'],
                                         'GR_SWIG_BLOCK_MAGIC2\(%s,\s*%s\);' % (self._info['modname'],
                                                                                os.path.splitext(f)[0]))
                remove_pattern_from_file(self._file['swig'],
                                         '(#|%%)include "(%s/)?%s".*\n' % (self._info['modname'], f))
        if not self._skip_subdirs['python']:
            py_files_deleted = self._run_subdir('python', ('*.py',), ('GR_PYTHON_INSTALL',),
                                                cmakeedit_func=_remove_py_test_case)
            for f in py_files_deleted:
                remove_pattern_from_file(self._file['pyinit'], '.*import\s+%s.*' % f[:-3])
                remove_pattern_from_file(self._file['pyinit'], '.*from\s+%s\s+import.*\n' % f[:-3])
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
        if len(files_filt) == 0:
            print "None found."
            return []
        # 2. Delete files, Makefile entries and other occurences
        files_deleted = []
        ed = CMakeFileEditor(os.path.join(path, 'CMakeLists.txt'))
        yes = self._info['yes']
        for f in files_filt:
            b = os.path.basename(f)
            if not yes:
                ans = raw_input("Really delete %s? [Y/n/a/q]: " % f).lower().strip()
                if ans == 'a':
                    yes = True
                    self._info['yes'] = True
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


### Disable module ###########################################################
class ModToolDisable(ModTool):
    """ Disable block (comments out CMake entries for files) """
    name = 'disable'
    aliases = ('dis',)
    def __init__(self):
        ModTool.__init__(self)

    def setup_parser(self):
        " Initialise the option parser for 'gr_modtool.py rm' "
        parser = ModTool.setup_parser(self)
        parser.usage = '%prog disable [options]. \n Call %prog without any options to run it interactively.'
        ogroup = OptionGroup(parser, "Disable module options")
        ogroup.add_option("-p", "--pattern", type="string", default=None,
                help="Filter possible choices for blocks to be disabled.")
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
            self._info['pattern'] = raw_input('Which blocks do you want to disable? (Regex): ')
        if len(self._info['pattern']) == 0:
            self._info['pattern'] = '.'
        self._info['yes'] = options.yes

    def run(self):
        """ Go, go, go! """
        def _handle_py_qa(cmake, fname):
            """ Do stuff for py qa """
            cmake.comment_out_lines('GR_ADD_TEST.*'+fname)
            return True
        def _handle_py_mod(cmake, fname):
            """ Do stuff for py extra files """
            try:
                initfile = open(self._file['pyinit']).read()
            except IOError:
                print "Could not edit __init__.py, that might be a problem."
                return False
            pymodname = os.path.splitext(fname)[0]
            initfile = re.sub(r'((from|import)\s+\b'+pymodname+r'\b)', r'#\1', initfile)
            open(self._file['pyinit'], 'w').write(initfile)
            return False
        def _handle_cc_qa(cmake, fname):
            """ Comment out the qa*.cc file in CMakeLists.txt, also
            Comment out the qa*.h in qa_$modname.cc (including the addtest line) """
            cmake.comment_out_lines('\$\{CMAKE_CURRENT_SOURCE_DIR\}/'+fname)
            fname_base = os.path.splitext(fname)[0]
            ed = CMakeFileEditor(self._file['qalib']) # Abusing the CMakeFileEditor...
            ed.comment_out_lines('#include\s+"%s.h"' % fname_base, comment_str='//')
            ed.comment_out_lines('%s::suite\(\)' % fname_base, comment_str='//')
            ed.write()
            return True
        def _handle_h_swig(cmake, fname):
            """ Comment out include files from the SWIG file,
            as well as the block magic """
            swigfile = open(self._file['swig']).read()
            (swigfile, nsubs) = re.subn('(.include\s+"%s/%s")' % (self._info['modname'], fname),
                                        r'//\1', swigfile)
            if nsubs > 0:
                print "Changing %s..." % self._file['swig']
            if nsubs > 1: # Need to find a single BLOCK_MAGIC
                blockname = os.path.splitext(fname)[0]
                (swigfile, nsubs) = re.subn('(GR_SWIG_BLOCK_MAGIC2.+'+blockname+'.+;)', r'//\1', swigfile)
                if nsubs > 1:
                    print "Hm, something didn't go right while editing %s." % self._file['swig']
            open(self._file['swig'], 'w').write(swigfile)
            return False
        def _handle_i_swig(cmake, fname):
            """ Comment out include files from the SWIG file,
            as well as the block magic """
            swigfile = open(self._file['swig']).read()
            blockname = os.path.splitext(fname)[0]
            swigfile = re.sub('(%include\s+"'+fname+'")', r'//\1', swigfile)
            print "Changing %s..." % self._file['swig']
            swigfile = re.sub('(GR_SWIG_BLOCK_MAGIC2.+'+blockname+'.+;)', r'//\1', swigfile)
            open(self._file['swig'], 'w').write(swigfile)
            return False
        # List of special rules: 0: subdir, 1: filename re match, 2: function
        special_treatments = (
                ('python', 'qa.+py$', _handle_py_qa),
                ('python', '^(?!qa).+py$', _handle_py_mod),
                ('lib', 'qa.+\.cc$', _handle_cc_qa),
                ('include/%s' % self._info['modname'], '.+\.h$', _handle_h_swig),
                ('swig', '.+\.i$', _handle_i_swig)
        )
        for subdir in self._subdirs:
            if self._skip_subdirs[subdir]: continue
            if subdir == 'include': subdir = 'include/%s' % self._info['modname']
            print "Traversing %s..." % subdir
            cmake = CMakeFileEditor(os.path.join(subdir, 'CMakeLists.txt'))
            filenames = cmake.find_filenames_match(self._info['pattern'])
            yes = self._info['yes']
            for fname in filenames:
                file_disabled = False
                if not yes:
                    ans = raw_input("Really disable %s? [Y/n/a/q]: " % fname).lower().strip()
                    if ans == 'a':
                        yes = True
                    if ans == 'q':
                        sys.exit(0)
                    if ans == 'n':
                        continue
                for special_treatment in special_treatments:
                    if special_treatment[0] == subdir and re.match(special_treatment[1], fname):
                        file_disabled = special_treatment[2](cmake, fname)
                if not file_disabled:
                    cmake.disable_file(fname)
            cmake.write()
        print "Careful: 'gr_modtool disable' does not resolve dependencies."

### The entire new module zipfile as base64 encoded tar.bz2  ###
NEWMOD_TARFILE = """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
hdAYFauYXEznGkRaY02Idh9F+CFguGBgfcpNK8m2N1iDD4+L9Td5ODa1XRAY04KRxIGpKYwxSWZA
fRynMblSkCbSGmxUIOaysH3aZ1B1z59xlG1S7uJMlHyLPzHc14yBuPN13mFCg4qGWcEewpsXRHBx
RIAbaLNIJptNvJln5sj9DmJxsoeoMRB85jLgQSgQqRNbryJgIZlLj01EUWgVoMKVGMOciQHPGSGJ
DCYClDHvqYEI6Gw4qqQGFObiYF0sAzAgQ8kUBQiq8dnRRnASMsQZ+yj/ZW7cxVO9fZ0HsR1Ozmfe
3+pwnVeYTBuzXvLPSzHl7HxQGNJe0tDUy3KUy0NJy0NJy0NJzKcttDSctDSctDSctDSctDUy20NT
LbQ1MttDUy20NSS20NJy0NTLbQ0nLQ0nMpxES20NTLbQ0nLQ1MtynLbQkNTEttDUy20NTEttDUkt
tDUkttDUkttDSctDSctDUgS3KcttDSctDSctDSctDSdmVWZ1d63+U8R4CB7Z3oLvbFxoAw63HnLy
I5ThX3vcyTuw+969t3vVup+FV2YdFbt2PJjGlfc3bOv1Nz3KedMKY3YxZ7WmJVaYbNMdGz0YeDo2
cGNjwcnwVubva97wbTu/by4VsVZ6N2Oqns+WPNpjzVpTh9LZodiuknD0fkdUeDw9rHTZe17HR2Y2
qq4TebK8X1OhjulcGi5LKihGSY94jgRQoiiRGwQzXsu67a7heHTZBhUbq5i8a4u6KjpU5sKC5Ior
l5UYAkIqERzAmQDI4ZDyhCwzsQofnGMBPaAkO652bhfFTep7nns4K4dXJ/wbsNwgqMeUMzHxKapg
cS8wHBHOgUiXFTmJBlvcDe5DEYFNBdq5ptXmLPznkfnFUcR0cT2JO93fGR7Fd3WE8DFVvceNPJwe
jsrk6qTswtYyCRZJZxPOfSgXIhkVJkgVwUwLggSNlMC9IZgiCIlMs2Qqtw3VeBYgRFKlwl4KBDCQ
2gpgX1+tjKGeTIAg9C5/HE0CJodhAcUwO+Lj5TfXlGBBtJMZh1Ezvl0lwMShzjsiQZR6CNcnJ5nN
l2cmiihehmhREDD9Yz1MFAMZo8FGWUI/UihHH4xho7BVknBvArmJ5DEiJUU25FSBMaJuWLG0xiKN
uM4SBiwfYdV5f0acevm68DQcwNgXh0yPLdEgTJD4X0C/los+4ZOwjj3k7KkyySMHmXDKEI4ZIxSI
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
ChIDGz2CwA=="""
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
        """
        * Unpack the tar.bz2 to the new locations
        * Remove the bz2
        * Open all files, rename howto and HOWTO to the module name
        * Rename files and directories that contain the word howto
        """
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
        print "Replacing occurences of 'howto' to '%s'..." % self._info['modname'],
        for root, dirs, files in os.walk('.'):
            for filename in files:
                f = os.path.join(root, filename)
                s = open(f, 'r').read()
                s = s.replace('howto', self._info['modname'])
                s = s.replace('HOWTO', self._info['modname'].upper())
                open(f, 'w').write(s)
                if filename.find('howto') != -1:
                    os.rename(f, os.path.join(root, filename.replace('howto', self._info['modname'])))
            if os.path.basename(root) == 'howto':
                os.rename(root, os.path.join(os.path.dirname(root), self._info['modname']))
        print "Done."
        print "Use 'gr_modtool add' to add a new block to this currently empty module."


### Parser for CC blocks ####################################################
def dummy_translator(the_type, default_v=None):
    """ Doesn't really translate. """
    return the_type

class ParserCCBlock(object):
    """ Class to read blocks written in C++ """
    def __init__(self, filename_cc, filename_h, blockname, type_trans=dummy_translator):
        self.code_cc = open(filename_cc).read()
        self.code_h  = open(filename_h).read()
        self.blockname = blockname
        self.type_trans = type_trans

    def read_io_signature(self):
        """ Scans a .cc file for an IO signature. """
        def _figure_out_iotype_and_vlen(iosigcall, typestr):
            """ From a type identifier, returns the data type.
            E.g., for sizeof(int), it will return 'int'.
            Returns a list! """
            if 'gr_make_iosignaturev' in iosigcall:
                print 'tbi'
                raise ValueError
            return {'type': [_typestr_to_iotype(x) for x in typestr.split(',')],
                    'vlen': [_typestr_to_vlen(x)   for x in typestr.split(',')]
                   }
        def _typestr_to_iotype(typestr):
            """ Convert a type string (e.g. sizeof(int) * vlen) to the type (e.g. 'int'). """
            type_match = re.search('sizeof\s*\(([^)]*)\)', typestr)
            if type_match is None:
                return self.type_trans('char')
            return self.type_trans(type_match.group(1))
        def _typestr_to_vlen(typestr):
            """ From a type identifier, returns the vector length of the block's
            input/out. E.g., for 'sizeof(int) * 10', it returns 10. For
            'sizeof(int)', it returns '1'. For 'sizeof(int) * vlen', it returns
            the string vlen. """
            # Catch fringe case where no sizeof() is given
            if typestr.find('sizeof') == -1:
                return typestr
            if typestr.find('*') == -1:
                return '1'
            vlen_parts = typestr.split('*')
            for fac in vlen_parts:
                if fac.find('sizeof') != -1:
                    vlen_parts.remove(fac)
            if len(vlen_parts) == 1:
                return vlen_parts[0].strip()
            elif len(vlen_parts) > 1:
                return '*'.join(vlen_parts).strip()
        iosig = {}
        iosig_regex = '(?P<incall>gr_make_io_signature[23v]?)\s*\(\s*(?P<inmin>[^,]+),\s*(?P<inmax>[^,]+),' + \
                      '\s*(?P<intype>(\([^\)]*\)|[^)])+)\),\s*' + \
                      '(?P<outcall>gr_make_io_signature[23v]?)\s*\(\s*(?P<outmin>[^,]+),\s*(?P<outmax>[^,]+),' + \
                      '\s*(?P<outtype>(\([^\)]*\)|[^)])+)\)'
        iosig_match = re.compile(iosig_regex, re.MULTILINE).search(self.code_cc)
        try:
            iosig['in'] = _figure_out_iotype_and_vlen(iosig_match.group('incall'),
                                                      iosig_match.group('intype'))
            iosig['in']['min_ports'] = iosig_match.group('inmin')
            iosig['in']['max_ports'] = iosig_match.group('inmax')
        except ValueError, Exception:
            print "Error: Can't parse input signature."
        try:
            iosig['out'] = _figure_out_iotype_and_vlen(iosig_match.group('outcall'),
                                                       iosig_match.group('outtype'))
            iosig['out']['min_ports'] = iosig_match.group('outmin')
            iosig['out']['max_ports'] = iosig_match.group('outmax')
        except ValueError, Exception:
            print "Error: Can't parse output signature."
        return iosig

    def read_params(self):
        """ Read the parameters required to initialize the block """
        make_regex = '(?<=_API)\s+\w+_sptr\s+\w+_make_\w+\s*\(([^)]*)\)'
        make_match = re.compile(make_regex, re.MULTILINE).search(self.code_h)
        # Go through params
        params = []
        try:
            param_str = make_match.group(1).strip()
            if len(param_str) == 0:
                return params
            for param in param_str.split(','):
                p_split = param.strip().split('=')
                if len(p_split) == 2:
                    default_v = p_split[1].strip()
                else:
                    default_v = ''
                (p_type, p_name) = [x for x in p_split[0].strip().split() if x != '']
                params.append({'key': p_name,
                               'type': self.type_trans(p_type, default_v),
                               'default': default_v,
                               'in_constructor': True})
        except ValueError:
            print "Error: Can't parse this: ", make_match.group(0)
            sys.exit(1)
        return params

### GRC XML Generator ########################################################
try:
    import lxml.etree
    LXML_IMPORTED = True
except ImportError:
    LXML_IMPORTED = False

class GRCXMLGenerator(object):
    """ Create and write the XML bindings for a GRC block. """
    def __init__(self, modname=None, blockname=None, doc=None, params=None, iosig=None):
        """docstring for __init__"""
        params_list = ['$'+s['key'] for s in params if s['in_constructor']]
        self._header = {'name': blockname.capitalize(),
                        'key': '%s_%s' % (modname, blockname),
                        'category': modname.upper(),
                        'import': 'import %s' % modname,
                        'make': '%s.%s(%s)' % (modname, blockname, ', '.join(params_list))
                       }
        self.params = params
        self.iosig = iosig
        self.doc = doc
        self.root = None
        if LXML_IMPORTED:
            self._prettyprint = self._lxml_prettyprint
        else:
            self._prettyprint = self._manual_prettyprint

    def _lxml_prettyprint(self):
        """ XML pretty printer using lxml """
        return lxml.etree.tostring(
                   lxml.etree.fromstring(ET.tostring(self.root, encoding="UTF-8")),
                   pretty_print=True
               )

    def _manual_prettyprint(self):
        """ XML pretty printer using xml_indent """
        xml_indent(self.root)
        return ET.tostring(self.root, encoding="UTF-8")

    def make_xml(self):
        """ Create the actual tag tree """
        root = ET.Element("block")
        iosig = self.iosig
        for tag in self._header.keys():
            this_tag = ET.SubElement(root, tag)
            this_tag.text = self._header[tag]
        for param in self.params:
            param_tag = ET.SubElement(root, 'param')
            ET.SubElement(param_tag, 'name').text = param['key'].capitalize()
            ET.SubElement(param_tag, 'key').text = param['key']
            ET.SubElement(param_tag, 'type').text = param['type']
            ET.SubElement(param_tag, 'value').text = param['default']
        for inout in sorted(iosig.keys()):
            if iosig[inout]['max_ports'] == '0':
                continue
            for i in range(len(iosig[inout]['type'])):
                s_tag = ET.SubElement(root, {'in': 'sink', 'out': 'source'}[inout])
                ET.SubElement(s_tag, 'name').text = inout
                ET.SubElement(s_tag, 'type').text = iosig[inout]['type'][i]
                if iosig[inout]['vlen'][i] != '1':
                    vlen = iosig[inout]['vlen'][i]
                    if is_number(vlen):
                        ET.SubElement(s_tag, 'vlen').text = vlen
                    else:
                        ET.SubElement(s_tag, 'vlen').text = '$'+vlen
                if i == len(iosig[inout]['type'])-1:
                    if not is_number(iosig[inout]['max_ports']):
                        ET.SubElement(s_tag, 'nports').text = iosig[inout]['max_ports']
                    elif len(iosig[inout]['type']) < int(iosig[inout]['max_ports']):
                        ET.SubElement(s_tag, 'nports').text = str(int(iosig[inout]['max_ports']) -
                                                                  len(iosig[inout]['type'])+1)
        if self.doc is not None:
            ET.SubElement(root, 'doc').text = self.doc
        self.root = root

    def save(self, filename):
        """ Write the XML file """
        self.make_xml()
        open(filename, 'w').write(self._prettyprint())

### Remove module ###########################################################
class ModToolMakeXML(ModTool):
    """ Make XML file for GRC block bindings """
    name = 'makexml'
    aliases = ('mx',)
    def __init__(self):
        ModTool.__init__(self)

    def setup_parser(self):
        " Initialise the option parser for 'gr_modtool.py makexml' "
        parser = ModTool.setup_parser(self)
        parser.usage = '%prog makexml [options]. \n Call %prog without any options to run it interactively.'
        ogroup = OptionGroup(parser, "Make XML module options")
        ogroup.add_option("-p", "--pattern", type="string", default=None,
                help="Filter possible choices for blocks to be parsed.")
        ogroup.add_option("-y", "--yes", action="store_true", default=False,
                help="Answer all questions with 'yes'. This can overwrite existing files!")
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
            self._info['pattern'] = raw_input('Which blocks do you want to parse? (Regex): ')
        if len(self._info['pattern']) == 0:
            self._info['pattern'] = '.'
        self._info['yes'] = options.yes

    def run(self):
        """ Go, go, go! """
        # 1) Go through lib/
        if not self._skip_subdirs['lib']:
            files = self._search_files('lib', '*.cc')
            for f in files:
                if os.path.basename(f)[0:2] == 'qa':
                    continue
                block_data = self._parse_cc_h(f)
                # Check if overwriting
                # Check if exists in CMakeLists.txt
        # 2) Go through python/


    def _search_files(self, path, path_glob):
        """ Search for files matching pattern in the given path. """
        files = glob.glob("%s/%s"% (path, path_glob))
        files_filt = []
        print "Searching for matching files in %s/:" % path
        for f in files:
            if re.search(self._info['pattern'], os.path.basename(f)) is not None:
                files_filt.append(f)
        if len(files_filt) == 0:
            print "None found."
        return files_filt


    def _parse_cc_h(self, fname_cc):
        """ Go through a .cc and .h-file defining a block and info """
        def _type_translate(p_type, default_v=None):
            """ Translates a type from C++ to GRC """
            translate_dict = {'float': 'real',
                              'double': 'real',
                              'gr_complex': 'complex',
                              'char': 'byte',
                              'unsigned char': 'byte'}
            if default_v is not None and default_v[0:2] == '0x' and p_type == 'int':
                return 'hex'
            if p_type in translate_dict.keys():
                return translate_dict[p_type]
            return p_type
        def _get_blockdata(fname_cc):
            """ Return the block name and the header file name from the .cc file name """
            blockname = os.path.splitext(os.path.basename(fname_cc))[0]
            fname_h = blockname + '.h'
            blockname = blockname.replace(self._info['modname']+'_', '', 1) # Deprecate 3.7
            fname_xml = '%s_%s.xml' % (self._info['modname'], blockname)
            return (blockname, fname_h, fname_xml)
        # Go, go, go
        print "Making GRC bindings for %s..." % fname_cc
        (blockname, fname_h, fname_xml) = _get_blockdata(fname_cc)
        try:
            parser = ParserCCBlock(fname_cc,
                                   os.path.join('include', fname_h),
                                   blockname, _type_translate
                                  )
        except IOError:
            print "Can't open some of the files necessary to parse %s." % fname_cc
            sys.exit(1)
        params = parser.read_params()
        iosig = parser.read_io_signature()
        # Some adaptions for the GRC
        for inout in ('in', 'out'):
            if iosig[inout]['max_ports'] == '-1':
                iosig[inout]['max_ports'] = '$num_%sputs' % inout
                params.append({'key': 'num_%sputs' % inout,
                               'type': 'int',
                               'name': 'Num %sputs' % inout,
                               'default': '2',
                               'in_constructor': False})
        # Make some XML!
        grc_generator = GRCXMLGenerator(
                modname=self._info['modname'],
                blockname=blockname,
                params=params,
                iosig=iosig
        )
        grc_generator.save(os.path.join('grc', fname_xml))
        # Make sure the XML is in the CMakeLists.txt
        if not self._skip_subdirs['grc']:
            ed = CMakeFileEditor(os.path.join('grc', 'CMakeLists.txt'))
            if re.search(fname_xml, ed.cfile) is None:
                ed.append_value('install', fname_xml, 'DESTINATION[^()]+')
                ed.write()

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
        print "Using Python < 2.7 possibly buggy. Ahem. Please send all complaints to /dev/null."
    main()

