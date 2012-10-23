""" Automatically create XML bindings for GRC from block code """

import sys
import os
import re
import glob
from optparse import OptionGroup

from modtool_base import ModTool
from parser_cc_block import ParserCCBlock
from grc_xml_generator import GRCXMLGenerator
from cmakefile_editor import CMakeFileEditor

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
            files = self._search_files('lib', '*_impl.cc')
            for f in files:
                if os.path.basename(f)[0:2] == 'qa':
                    continue
                (params, iosig, blockname) = self._parse_cc_h(f)
                self._make_grc_xml_from_block_data(params, iosig, blockname)
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

    def _make_grc_xml_from_block_data(self, params, iosig, blockname):
        """ Take the return values from the parser and call the XML
        generator. Also, check the makefile if the .xml file is in there.
        If necessary, add. """
        fname_xml = '%s_%s.xml' % (self._info['modname'], blockname)
        # Some adaptions for the GRC
        for inout in ('in', 'out'):
            if iosig[inout]['max_ports'] == '-1':
                iosig[inout]['max_ports'] = '$num_%sputs' % inout
                params.append({'key': 'num_%sputs' % inout,
                               'type': 'int',
                               'name': 'Num %sputs' % inout,
                               'default': '2',
                               'in_constructor': False})
        if os.path.isfile(os.path.join('grc', fname_xml)):
            # TODO add an option to keep
            print "Overwriting existing GRC file."
        grc_generator = GRCXMLGenerator(
                modname=self._info['modname'],
                blockname=blockname,
                params=params,
                iosig=iosig
        )
        grc_generator.save(os.path.join('grc', fname_xml))
        if not self._skip_subdirs['grc']:
            ed = CMakeFileEditor(self._file['cmgrc'])
            if re.search(fname_xml, ed.cfile) is None:
                print "Adding GRC bindings to grc/CMakeLists.txt..."
                ed.append_value('install', fname_xml, 'DESTINATION[^()]+')
                ed.write()


    def _parse_cc_h(self, fname_cc):
        """ Go through a .cc and .h-file defining a block and return info """
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
            blockname = os.path.splitext(os.path.basename(fname_cc))[0].replace('_impl', '')
            fname_h = blockname + '.h'
            blockname = blockname.replace(self._info['modname']+'_', '', 1) # Deprecate 3.7
            return (blockname, fname_h)
        # Go, go, go
        print "Making GRC bindings for %s..." % fname_cc
        (blockname, fname_h) = _get_blockdata(fname_cc)
        try:
            parser = ParserCCBlock(fname_cc,
                                   os.path.join('include', self._info['modname'], fname_h),
                                   blockname, _type_translate
                                  )
        except IOError:
            print "Can't open some of the files necessary to parse %s." % fname_cc
            sys.exit(1)
        return (parser.read_params(), parser.read_io_signature(), blockname)

