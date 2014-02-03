# Copyright 2012-2014 Peter Williams
# Licensed under the GNU General Public License version 3 or higher

"""A simple parser for ini-style files that's better than Python's
ConfigParser/configparser."""

__all__ = ('Holder readStream read FileChunk '
           'mutateStream mutate mutateInPlace').split ()

## quickutil: holder
#- snippet: holder.py (2012 Mar 29)
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

    def iteritems (self):
        for k, v in self.__dict__.iteritems ():
            if k[0] == '_':
                continue
            if v is None:
                continue
            yield k, v
## end

import re, os

sectionre = re.compile (r'^\[(.*)]\s*$')
keyre = re.compile (r'^(\S+)\s*=(.*)$') # leading space chomped later
escre = re.compile (r'^(\S+)\s*=\s*"(.*)"\s*$')

def readStream (stream):
    section = None
    key = None
    data = None

    for fullline in stream:
        line = fullline.split ('#', 1)[0]

        m = sectionre.match (line)
        if m is not None:
            # New section
            if section is not None:
                if key is not None:
                    section.setone (key, data.strip ().decode ('utf8'))
                    key = data = None
                yield section

            section = Holder ()
            section.section = m.group (1)
            continue

        if len (line.strip ()) == 0:
            if key is not None:
                section.setone (key, data.strip ().decode ('utf8'))
                key = data = None
            continue

        m = escre.match (fullline)
        if m is not None:
            if section is None:
                raise Exception ('key seen without section!')
            if key is not None:
                section.setone (key, data.strip ().decode ('utf8'))
            key = m.group (1)
            data = m.group (2).replace (r'\"', '"').replace (r'\n', '\n').replace (r'\\', '\\')
            section.setone (key, data.decode ('utf8'))
            key = data = None
            continue

        m = keyre.match (line)
        if m is not None:
            if section is None:
                raise Exception ('key seen without section!')
            if key is not None:
                section.setone (key, data.strip ().decode ('utf8'))
            key = m.group (1)
            data = m.group (2)
            if not len (data):
                data = ' '
            elif not data[-1].isspace ():
                data += ' '
            continue

        if line[0].isspace () and key is not None:
            data += line.strip () + ' '
            continue

        raise Exception ('unparsable line: ' + line[:-1])

    if section is not None:
        if key is not None:
            section.setone (key, data.strip ().decode ('utf8'))
        yield section


def read (stream_or_path):
    if isinstance (stream_or_path, basestring):
        return readStream (open (stream_or_path))
    return readStream (stream_or_path)


def writeStream (stream, items):
    """Note that we just dumbly stringify the item values. That's sufficient
    for our limited purposes but not good in generality."""

    first = True

    for i in items:
        if first:
            first = False
        else:
            print >>stream

        print >>stream, '[%s]' % i.section

        for k, v in sorted (i.iteritems ()):
            if k == 'section':
                continue
            print >>stream, k, '=', unicode (v).encode ('utf-8')


def write (stream_or_path, items):
    if isinstance (stream_or_path, basestring):
        return writeStream (open (stream_or_path, 'w'), items)
    return writeStream (stream_or_path, items)


# Parsing plus inline modification, preserving the file
# as much as possible.
#
# I'm pretty sure that this code gets the corner cases right, but it
# hasn't been thoroughly tested, and it's a little hairy ...

class FileChunk (object):
    def __init__ (self):
        self.data = Holder ()
        self._lines = []


    def _addLine (self, line, assoc):
        self._lines.append ((assoc, line))


    def set (self, name, value):
        newline = ((u'%s = %s' % (name, value)) + os.linesep).encode ('utf8')
        first = True

        for i in xrange (len (self._lines)):
            assoc, line = self._lines[i]

            if assoc != name:
                continue

            if first:
                self._lines[i] = (assoc, newline)
                first = False
            else:
                # delete the line
                self._lines[i] = (None, None)

        if first:
            # Need to append the line to the last block
            for i in xrange (len (self._lines) - 1, -1, -1):
                if self._lines[i][0] is not None:
                    break

            self._lines.insert (i + 1, (name, newline))


    def emit (self, stream):
        for assoc, line in self._lines:
            if line is None:
                continue

            stream.write (line)


def mutateStream (instream, outstream):
    chunk = None
    key = None
    data = None
    misclines = []

    for fullline in instream:
        line = fullline.split ('#', 1)[0]

        m = sectionre.match (line)
        if m is not None:
            # New chunk
            if chunk is not None:
                if key is not None:
                    chunk.data.setone (key, data.strip ().decode ('utf8'))
                    key = data = None
                yield chunk
                chunk.emit (outstream)

            chunk = FileChunk ()
            for miscline in misclines:
                chunk._addLine (miscline, None)
            misclines = []
            chunk.data.section = m.group (1)
            chunk._addLine (fullline, None)
            continue

        if len (line.strip ()) == 0:
            if key is not None:
                chunk.data.setone (key, data.strip ().decode ('utf8'))
                key = data = None
            if chunk is not None:
                chunk._addLine (fullline, None)
            else:
                misclines.append (fullline)
            continue

        m = escre.match (fullline)
        if m is not None:
            if chunk is None:
                raise Exception ('key seen without section!')
            if key is not None:
                chunk.data.setone (key, data.strip ().decode ('utf8'))
            key = m.group (1)
            data = m.group (2).replace (r'\"', '"').replace (r'\n', '\n').replace (r'\\', '\\')
            chunk.data.setone (key, data.decode ('utf8'))
            chunk._addLine (fullline, key)
            key = data = None
            continue

        m = keyre.match (line)
        if m is not None:
            if chunk is None:
                raise Exception ('key seen without section!')
            if key is not None:
                chunk.data.setone (key, data.strip ().decode ('utf8'))
            key = m.group (1)
            data = m.group (2)
            if not data[-1].isspace ():
                data += ' '
            chunk._addLine (fullline, key)
            continue

        if line[0].isspace () and key is not None:
            data += line.strip () + ' '
            chunk._addLine (fullline, key)
            continue

        raise Exception ('unparsable line: ' + line[:-1])

    if chunk is not None:
        if key is not None:
            chunk.data.setone (key, data.strip ().decode ('utf8'))
        yield chunk
        chunk.emit (outstream)

    if len (misclines):
        for miscline in misclines:
            outstream.write (miscline)


def mutate (instream_or_path, outstream_or_path, outmode='w'):
    if isinstance (instream_or_path, basestring):
        instream_or_path = open (instream_or_path)

    if isinstance (outstream_or_path, basestring):
        outstream_or_path = open (outstream_or_path, outmode)

    return mutateStream (instream_or_path, outstream_or_path)


def mutateInPlace (inpath):
    from sys import exc_info
    from os import rename, unlink

    tmppath = inpath + '.new'

    with open (inpath) as instream:
        try:
            with open (tmppath, 'w') as outstream:
                for item in mutateStream (instream, outstream):
                    yield item
                rename (tmppath, inpath)
        except:
            et, ev, etb = exc_info ()
            try:
                os.unlink (tmppath)
            except Exception:
                pass
            raise et, ev, etb
