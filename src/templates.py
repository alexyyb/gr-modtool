''' All the templates for skeleton files (needed by ModToolAdd) '''

from datetime import datetime

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

#if $blocktype == 'general'
      // Where all the action really happens
      int general_work(int noutput_items,
		       gr_vector_int &ninput_items,
		       gr_vector_const_void_star &input_items,
		       gr_vector_void_star &output_items);
#else if $blocktype == 'hier'
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

#if $blocktype == 'decimator'
#set $decimation = ', <+decimation+>'
#else if $blocktype == 'interpolator'
#set $decimation = ', <+interpolation+>'
#else
#set $decimation = ''
#end if
#if $blocktype == 'sink'
#set $inputsig = '0, 0, 0'
#else
#set $inputsig = '<+MIN_IN+>, <+MAX_IN+>, sizeof (<+float+>)'
#end if
#if $blocktype == 'source'
#set $outputsig = '0, 0, 0'
#else
#set $outputsig = '<+MIN_IN+>, <+MAX_IN+>, sizeof (<+float+>)'
#end if
    /*
     * The private constructor
     */
    ${blockname}_impl::${blockname}_impl(${strip_default_values($arglist)})
      : ${grblocktype}("${blockname}",
		      gr_make_io_signature($inputsig),
		      gr_make_io_signature($outputsig)$decimation)
#if $blocktype == 'hier'
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

#if $blocktype == 'general'
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

#else if $blocktype == 'hier'
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

# Python block (from grextras!)
Templates['block_python'] = '''\#!/usr/bin/env python
${str_to_python_comment($license)}
#

from gnuradio import gr
import gnuradio.extras

#if $blocktype == 'sink'
#set $inputsig = 'None'
#else
#set $inputsig = '[<+numpy.float+>]'
#end if
#if $blocktype == 'source'
#set $outputsig = 'None'
#else
#set $outputsig = '[<+numpy.float+>]'
#end if

class ${blockname}(gr.block):
    def __init__(self, args):
        gr.block.__init__(self, name="${blockname}", in_sig=${inputsig}, out_sig=${outputsig})
#if $blocktype == 'decimator'
        self.set_relative_rate(1.0/<+decimation+>)
#else if $blocktype == 'interpolator'
        self.set_relative_rate(<+interpolation+>)
#else if $blocktype == 'general'
        self.set_auto_consume(False)

    def forecast(self, noutput_items, ninput_items_required):
        #setup size of input_items[i] for work call
        for i in range(len(ninput_items_required)):
            ninput_items_required[i] = noutput_items
#end if

    def work(self, input_items, output_items):
#if $blocktype != 'source'
        in = input_items[0]
#end if
#if $blocktype != 'sink'
        out = output_items[0]
#end if
#if $blocktype in ('sync', 'decimator', 'interpolator')
        # <+signal processing here+>
        out[:] = in
        return len(output_items[0])
#else if $blocktype == 'sink'
        return len(input_items[0])
#else if $blocktype == 'source'
        out[:] = whatever
        return len(output_items[0])
#else if $blocktype == 'general'
        # <+signal processing here+>
        out[:] = in

        self.consume(0, len(in0)) //consume port 0 input
        \#self.consume_each(len(out)) //or shortcut to consume on all inputs

        # return produced
        return len(out)
#end if

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

#if $blocktype == 'sink'
#set $inputsig = '0, 0, 0'
#else
#set $inputsig = '<+MIN_IN+>, <+MAX_IN+>, gr.sizeof_<+float+>'
#end if
#if $blocktype == 'source'
#set $outputsig = '0, 0, 0'
#else
#set $outputsig = '<+MIN_OUT+>, <+MAX_OUT+>, gr.sizeof_<+float+>'
#end if
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

