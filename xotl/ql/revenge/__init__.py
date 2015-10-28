# -*- encoding: utf-8 -*-
# ---------------------------------------------------------------------
# xotl.ql.revenge
# ---------------------------------------------------------------------
# Copyright (c) 2014, 2015 Merchise Autrement and Contributors
# All rights reserved.
#

# This is a fork of the uncompyle2 package.  It's been modified to better
# suite our coding standards and aim.
#
# The original copyright notice is kept below.
#
# The name 'revenge' stands for "REVerse ENGineering using an Earley parser"
# ;)
#
# The goal of the uncompyle2 package was to produce source code from byte-code
# of full Python programs.  Our goal is much, much smaller: we need to obtain
# an (pythonic) AST for *expressions* from the byte-code.  This means we don't
# have to keep the entire parser for full-blown programs.
#

#  Copyright (c) 1999 John Aycock
#  Copyright (c) 2000 by hartmut Goebel <h.goebel@crazy-compilers.com>
#
#  Permission is hereby granted, free of charge, to any person obtaining
#  a copy of this software and associated documentation files (the
#  "Software"), to deal in the Software without restriction, including
#  without limitation the rights to use, copy, modify, merge, publish,
#  distribute, sublicense, and/or sell copies of the Software, and to
#  permit persons to whom the Software is furnished to do so, subject to
#  the following conditions:
#
#  The above copyright notice and this permission notice shall be
#  included in all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#  MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
#  CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
#  TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# See the file 'CHANGES' for a list of changes
#
# NB. This is not a masterpiece of software, but became more like a hack.
#     Probably a complete rewrite would be sensefull. hG/2000-12-27
#

from __future__ import (division as _py3_division,
                        print_function as _py3_print,
                        absolute_import as _py3_abs_import)

import types
from xoutil.decorator import memoized_property

from . import scanners, walkers
from .parsers import ParserError


class Uncompyled(object):   # TODO:  Find better name
    def __init__(self, obj, version=None):
        if not version:
            import sys
            version = sys.version.split(' ')[0]
        code = self._extract_code(obj)
        scanner = scanners.getscanner(version)
        self.walker = walker = walkers.Walker(scanner)
        tokens, customizations = scanner.disassemble(code)
        self.tokens = tokens
        self.customizations = customizations
        try:
            ast = walker.build_ast(tokens, customizations)
        except ParserError as error:
            raise error  # make the debugger print the locals

        # Go down in the AST until the root has more than one children.
        while ast and len(ast) == 1:
            ast = ast[0]
        self.ast = ast

    @memoized_property
    def source(self):
        self.walker.gen_source(self.ast, self.customizations)
        return self.walker.f.getvalue()

    @staticmethod
    def _extract_code(obj):
        if isinstance(obj, types.CodeType):
            return obj
        elif isinstance(obj, types.GeneratorType):
            return obj.gi_code
        elif isinstance(obj, types.FunctionType):
            from xoutil.objects import get_first_of
            return get_first_of(obj, 'func_code', '__code__')
        else:
            raise TypeError('Invalid code object')
