""" All the templates for skeleton files (needed by ModToolAdd) """

from datetime import datetime
from string import Template

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
Templates['block_impl_h'] = Template("""/* -*- c++ -*- */
$license
#ifndef INCLUDED_${modnameupper}_${blocknameupper}_IMPL_H
#define INCLUDED_${modnameupper}_${blocknameupper}_IMPL_H

#include <${modname}/${blockname}.h>

namespace gr {
  namespace $modname {

    class ${blockname}_impl : public ${blockname}
    {
    private:
      // Nothing to declare in this block.

    public:
      ${blockname}_impl($argliststripped);
      ~${blockname}_impl();

      // Where all the action really happens

$workfunc
    };

  } // namespace $modname
} // namespace gr

#endif /* INCLUDED_${modnameupper}_${blocknameupper}_IMPL_H */

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
Templates['block_impl_cpp'] = Template("""/* -*- c++ -*- */
$license
#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <gr_io_signature.h>
#include "${blockname}_impl.h"

namespace gr {
  namespace $modname {

    ${blockname}::sptr
    ${blockname}::make($argliststripped)
    {
      return gnuradio::get_initial_sptr (new ${blockname}_impl($arglistnotypes));
    }

    /*
     * The private constructor
     */
    ${blockname}_impl::${blockname}_impl($argliststripped)
      : $grblocktype("${blockname}",
		      gr_make_io_signature($inputsig),
		      gr_make_io_signature($outputsig)$decimation)
    {
$constructorcontent}

    /*
     * Our virtual destructor.
     */
    ${blockname}_impl::~${blockname}_impl()
    {
    }

    $workcall
  } /* namespace $modname */
} /* namespace gr */

""")

Templates['block_cpp_workcall'] = Template("""

    int
    ${blockname}_impl::$workfunc
""")

Templates['block_cpp_hierconstructor'] = """
	connect(self(), 0, d_firstblock, 0);
	// connect other blocks
	connect(d_lastblock, 0, self(), 0);
"""

# Block definition header file (for include/)
Templates['block_def_h'] = Template("""/* -*- c++ -*- */
$license

#ifndef INCLUDED_${modnameupper}_${blocknameupper}_H
#define INCLUDED_${modnameupper}_${blocknameupper}_H

#include <${modname}/api.h>
#include <$grblocktype.h>

namespace gr {
  namespace $modname {

    /*!
     * \\brief <+description of block+>
     * \ingroup block
     *
     */
    class ${modnameupper}_API ${blockname} : virtual public $grblocktype
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

  } // namespace $modname
} // namespace gr

#endif /* INCLUDED_${modnameupper}_${blocknameupper}_H */

""")

# Header file for QA
Templates['qa_cmakeentry'] = Template("""
add_executable($basename $filename)
target_link_libraries($basename gnuradio-$modname $${Boost_LIBRARIES})
GR_ADD_TEST($basename $basename)
""")

# C++ file for QA
Templates['qa_cpp'] = Template("""/* -*- c++ -*- */
$license

#include "qa_square2_ff.h"
#include <cppunit/TestAssert.h>

#include <$modname/$blockname.h>

namespace gr {
  namespace $modname {

    void
    qa_${blockname}::t1()
    {
        // Put test here
    }

  } /* namespace $modname */
} /* namespace gr */

""")

# Header file for QA
Templates['qa_h'] = Template("""/* -*- c++ -*- */
$license

#ifndef _QA_${blocknameupper}_H_
#define _QA_${blocknameupper}_H_

#include <cppunit/extensions/HelperMacros.h>
#include <cppunit/TestCase.h>

namespace gr {
  namespace $modname {

    class qa_${blockname} : public CppUnit::TestCase
    {
    public:
      CPPUNIT_TEST_SUITE(qa_${blockname});
      CPPUNIT_TEST(t1);
      CPPUNIT_TEST_SUITE_END();

    private:
      void t1();
    };

  } /* namespace $modname */
} /* namespace gr */

#endif /* _QA_${blocknameupper}_H_ */

""")

# Python QA code
Templates['qa_python'] = Template("""#!/usr/bin/env python
$license
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
""")


# Hierarchical block, Python version
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

        # Define blocks and connect them
        self.connect()

''')

# Non-block file, C++ header
Templates['noblock_h'] = Template('''/* -*- c++ -*- */
$license
#ifndef INCLUDED_${modnameupper}_${blocknameupper}_H
#define INCLUDED_${modnameupper}_${blocknameupper}_H

#include <$modname/api.h>

namespace gr {
  namespace $modname {
    class ${modnameupper}_API $blockname
    {
        $blockname({$arglist});
        ~$blockname();
        private:
    };



  }  /* namespace $modname */
}  /* namespace gr */


#endif /* INCLUDED_${modnameupper}_${blocknameupper}_H */

''')

# Non-block file, C++ source
Templates['noblock_cpp'] = Template('''/* -*- c++ -*- */
$license

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <$modname/$blockname.h>

namespace gr {
  namespace ${modname} {

    $blockname::$blockname($argliststripped)
    {
    }

    $blockname::~$blockname()
    {
    }

  }  /* namespace $blockname */
}  /* namespace gr */

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

