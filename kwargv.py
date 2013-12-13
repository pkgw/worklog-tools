# Copyright 2012 Peter Williams
# Licensed under the GNU General Public License version 3 or higher

""" kwargv - keyword-style command-line arguments

Keywords are defined by declaring a subclass of ParseKeywords. Within
that:

- "foo = 1" defines a keyword with a default value, type inferred as
  int. Likewise for str, bool, float.

- "foo = int" defines an int keyword, default value of None. Likewise
  for str, bool, float.

- "foo = [int]" parses as a list of integers of any length, default []
  (I call these "flexible" lists.)

- "foo = [3.0, int]" parses as a 2-element list, default [3.0, None].
  If 1 value is given, the first array item is parsed, and the second
  is left as its default. (I call these "fixed" lists.)

- "foo = Custom(bar, a=b)" parses like "bar" and then customizes
  keyword properties as defined below.

- "@Custom(bar, a=b) \n def foo (value): ..." defines a keyword "foo"
  that parses like "bar", with custom properties as defined below, and
  has its value fixed up by calling the foo() function after the basic
  parsing.  That is, the final value is "foo (intermediate_value)". A
  common pattern is to use a fixup function for a fixed list where the
  first few values are mandatory (see 'minvals' below) but later
  values can be guessed or defaulted.

Instantiating the subclass fills in all defaults, and calling the
"parse()" method parses a list of strings (defaulting to
sys.argv[1:]). See scibin/omegamap for a somewhat complex example.

Properties for keyword customization:

parser (callable): function to parse basic textual value
default (anything): the default value if keyword is unspecified
required (bool, False): whether to raise an error if keyword is not 
  seen when parsing
sep (str, ','): separator for parsing the keyword as a list
maxvals (int or None, None): maximum number of values **in flexible 
  lists only**
minvals (int, 0): minimum number of values **in fixed lists only**, 
  **if the keyword is specified at all**. If you want minvals=1, use 
  required=True.
scale (numeric or None, None): multiply the value by this after 
  parsing
printexc (bool, False): if there's an exception when parsing the 
  keyword value, whether the exception message should be printed.
  (Otherwise, just prints "cannot parse value <val> for keyword <kw>".)
fixupfunc (callable or None, None): after all other parsing/transform
  steps, the final value is the return value of fixupfunc(intermediateval)
uiname (str or None, None): the name of the keyword as presented in the UI.
  I.e., "foo = Custom (0, uiname='bar')" parses keyword "bar=..." but
  sets attribute "foo" in the Python object.

TODO: --help, etc.

TODO: 'multival' or something; if true, foo=1 foo=2 -> foo=[1,2]
(would be useful for omegamap locator=...)

TODO: +bool, -bool for ParseKeywords parser (but careful about allowing
--help at least)

TODO: remove die() calls, better exception/error framework

TODO: positive, nonzero options for easy bounds-checking of numerics
"""

__all__ = 'basic Custom ParseKeywords'.split ()

## quickutil: holder die
#- snippet: holder.py (2012 Oct 01)
#- SHA1: bc9ad74474ffc74f18a12675f7422f0c5963df59
class Holder (object):
    def __init__ (self, **kwargs):
        self.set (**kwargs)

    def __str__ (self):
        d = self.__dict__
        s = sorted (d.iterkeys ())
        return '{' + ', '.join ('%s=%s' % (k, d[k]) for k in s) + '}'

    def __repr__ (self):
        d = self.__dict__
        s = sorted (d.iterkeys ())
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join ('%s=%r' % (k, d[k]) for k in s))

    def set (self, **kwargs):
        self.__dict__.update (kwargs)
        return self

    def get (self, name, defval=None):
        return self.__dict__.get (name, defval)

    def setone (self, name, value):
        self.__dict__[name] = value
        return self

    def has (self, name):
        return name in self.__dict__

    def copy (self):
        new = self.__class__ ()
        new.__dict__ = dict (self.__dict__)
        return new
#- snippet: die.py (2012 Oct 01)
#- SHA1: 3bdd3282e52403d2dec99d72680cb7bc95c99843
def die (fmt, *args):
    if not len (args):
        raise SystemExit ('error: ' + str (fmt))
    raise SystemExit ('error: ' + (fmt % args))
## end


def basic (args=None):
    if args is None:
        import sys
        args = sys.argv[1:]

    parsed = Holder ()

    for arg in args:
        if arg[0] == '+':
            for kw in arg[1:].split (','):
                parsed.setone (kw, True)
            # avoid analogous -a,b,c syntax because it gets confused with -a --help, etc.
        else:
            t = arg.split ('=', 1)
            if len (t) < 2:
                die ('don\'t know what to do with argument "%s"' % arg)
            if not len (t[1]):
                die ('empty value for keyword argument "%s"' % t[0])
            parsed.setone (t[0], t[1])

    return parsed


# The fancy keyword parsing system.

class ParseError (Exception):
    pass


class KeywordInfo (object):
    parser = None
    default = None
    required = False
    sep = ','
    maxvals = None
    minvals = 0 # note: maxvals and minvals are used in different ways
    scale = None
    printexc = False
    fixupfunc = None
    attrname = None


class KeywordOptions (Holder):
    uiname = None
    subval = None

    def __init__ (self, subval, **kwargs):
        self.set (**kwargs)
        self.subval = subval


    def __call__ (self, fixupfunc):
        # Slightly black magic. Grayish magic. This lets us be used as
        # a decorator on "fixup" functions to modify or range-check
        # the parsed argument value.
        self.fixupfunc = fixupfunc
        return self


Custom = KeywordOptions # sugar for users


def _parse_bool (s):
    s = s.lower ()

    if s in 'y yes t true on 1'.split ():
        return True
    if s in 'n no f false off 0'.split ():
        return False
    raise ParseError ('don\'t know how to interpret "%s" as a boolean' % s)


def _val_to_parser (v):
    if v.__class__ is bool:
        return _parse_bool
    if v.__class__ in (int, float, str):
        return v.__class__
    raise ValueError ('can\'t figure out how to parse %r' % v)


def _val_or_func_to_parser (v):
    if v is bool:
        return _parse_bool
    if callable (v):
        return v
    return _val_to_parser (v)


def _val_or_func_to_default (v):
    if callable (v):
        return None
    if v.__class__ in (int, float, bool, str):
        return v
    raise ValueError ('can\'t figure out a default for %r' % v)


def _handle_flex_list (ki, ks):
    assert len (ks) == 1
    elemparser = ks[0]
    # I don't think 'foo = [0]' will be useful ...
    assert callable (elemparser)

    def flexlistparse (val):
        return [elemparser (i) for i in val.split (ki.sep)]

    return flexlistparse, []


def _handle_fixed_list (ki, ks):
    parsers = [_val_or_func_to_parser (sks) for sks in ks]
    defaults = [_val_or_func_to_default (sks) for sks in ks]
    ntot = len (parsers)

    def fixlistparse (val):
        items = val.split (ki.sep)
        ngot = len (items)

        if ngot < ki.minvals:
            if ki.minvals == ntot:
                raise ParseError ('expected exactly %d values, but only got %d'
                                  % (ntot, ngot))
            raise ParseError ('expected between %d and %d values, but only got %d'
                              % (ki.minvals, ntot, ngot))
        if ngot > ntot:
            raise ParseError ('expected between %d and %d values, but got %d'
                              % (ki.minvals, ntot, ngot))

        result = list (defaults) # make a copy
        for i in xrange (ngot):
            result[i] = parsers[i] (items[i])
        return result

    return fixlistparse, list (defaults) # make a copy


class ParseKeywords (Holder):
    def __init__ (self):
        kwspecs = self.__class__.__dict__
        kwinfos = {}

        # Process our keywords, as specified by the class attributes,
        # into a form more friendly for parsing, and check for things
        # we don't understand. 'kw' is the keyword name exposed to the
        # user; 'attrname' is the name of the attribute to set on the
        # resulting object.

        for kw, ks in kwspecs.iteritems ():
            if kw[0] == '_':
                continue

            ki = KeywordInfo ()
            ko = None
            attrname = kw

            if isinstance (ks, KeywordOptions):
                ko = ks
                ks = ko.subval

                if ko.uiname is not None:
                    kw = ko.uiname

            if callable (ks):
                # expected to be a type (int, float, ...).
                # This branch would get taken for methods, too,
                # which sorta makes sense?
                parser = _val_or_func_to_parser (ks)
                default = _val_or_func_to_default (ks)
            elif isinstance (ks, list) and len (ks) == 1:
                parser, default = _handle_flex_list (ki, ks)
            elif isinstance (ks, list) and len (ks) > 1:
                parser, default = _handle_fixed_list (ki, ks)
            else:
                parser = _val_to_parser (ks)
                default = _val_or_func_to_default (ks)

            ki.attrname = attrname
            ki.parser = parser
            ki.default = default

            if ko is not None: # override with user-specified options
                ki.__dict__.update (ko.__dict__)

            if ki.required:
                # makes sense, and prevents trying to call fixupfunc on
                # weird default values of fixed lists.
                ki.default = None

            if ki.fixupfunc is not None and ki.default is not None:
                # kinda gross structure here, oh well.
                ki.default = ki.fixupfunc (ki.default)

            kwinfos[kw] = ki

        # Apply defaults, save parse info, done

        for kw, ki in kwinfos.iteritems ():
            self.setone (ki.attrname, ki.default)

        self._kwinfos = kwinfos


    def parse (self, args=None):
        if args is None:
            import sys
            args = sys.argv[1:]

        seen = set ()

        for arg in args:
            t = arg.split ('=', 1)
            if len (t) < 2:
                die ('don\'t know what to do with argument "%s"' % arg)

            kw, val = t
            ki = self._kwinfos.get (kw)

            if ki is None:
                die ('unrecognized keyword argument "%s"' % kw)

            if not len (val):
                die ('empty value for keyword argument "%s"' % kw)

            try:
                pval = ki.parser (val)
            except ParseError, e:
                die ('cannot parse value "%s" for keyword argument "%s": %s' %
                     (val, kw, e))
            except Exception, e:
                if ki.printexc:
                    die ('cannot parse value "%s" for keyword argument "%s": %s' %
                         (val, kw, e))
                die ('cannot parse value "%s" for keyword argument "%s"' %
                     (val, kw))

            if ki.maxvals is not None and len (pval) > ki.maxvals:
                die ('keyword argument "%s" may have at most %d values, '
                     'but got %s ("%s")' % (kw, ki.maxvals, len (pval), val))

            if ki.scale is not None:
                pval = pval * ki.scale

            if ki.fixupfunc is not None:
                pval = ki.fixupfunc (pval)

            seen.add (kw)
            self.setone (ki.attrname, pval)

        for kw, ki in self._kwinfos.iteritems ():
            if ki.required and kw not in seen:
                die ('required keyword argument "%s" was not provided' % kw)

        return self # convenience


if __name__ == '__main__':
    print basic ()
