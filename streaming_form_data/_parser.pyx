import cgi

from streaming_form_data.targets import NullTarget


cdef enum Constants:
    Hyphen = 45
    CR = 13
    LF = 10
    MinFileBodyChunkSize = 1024


cdef enum FinderState:
    FS_START, FS_WORKING, FS_END


# Knuth–Morris–Pratt algorithm
cdef class Finder:
    cdef bytes target
    cdef const char* target_ptr
    cdef size_t index, target_len
    cdef FinderState state

    def __init__(self, target):
        if len(target) < 1:
            raise ValueError('Empty values not allowed')

        self.target = target
        self.target_ptr = self.target
        self.target_len = len(target)
        self.index = 0
        self.state = FinderState.FS_START

    cpdef feed(self, char byte):
        if byte != self.target_ptr[self.index]:
            self.state = FinderState.FS_START
            self.index = 0
        else:
            self.state = FinderState.FS_WORKING
            self.index += 1

            if self.index == self.target_len:
                self.state = FinderState.FS_END

    cpdef reset(self):
        self.state = FinderState.FS_START
        self.index = 0

    @property
    def target(self):
        return self.target

    cpdef bint inactive(self):
        return self.state == FinderState.FS_START

    cpdef bint active(self):
        return self.state == FinderState.FS_WORKING

    cpdef bint found(self):
        return self.state == FinderState.FS_END

    cpdef size_t matched_length(self):
        return self.index

class Part:
    """One part of a multipart/form-data request
    """

    def __init__(self, name, target):
        self.name = name
        self.target = target

        self._reading = False

    def headers_parsed(self, content_disposition_dict):
        self.target.headers_parsed(content_disposition_dict)

    def start(self):
        self._reading = True
        self.target.start()

    def data_received(self, chunk):
        self.target.data_received(chunk)

    def finish(self):
        self._reading = False
        self.target.finish()

    @property
    def is_reading(self):
        return self._reading


cdef enum ParserState:
    PS_START,

    PS_STARTING_BOUNDARY, PS_READING_BOUNDARY, PS_ENDING_BOUNDARY,

    PS_READING_HEADER, PS_ENDING_HEADER, PS_ENDED_HEADER, PS_ENDING_ALL_HEADERS,

    PS_READING_BODY,

    PS_END


cdef class _Parser:
    cdef bytes delimiter, ender
    cdef ParserState state
    cdef Finder delimiter_finder, ender_finder
    cdef size_t delimiter_length, ender_length
    cdef object expected_parts
    cdef object active_part, default_part

    cdef bytes _leftover_buffer

    def __init__(self, delimiter, ender):
        self.delimiter = delimiter
        self.ender = ender

        self.delimiter_finder = Finder(delimiter)
        self.ender_finder = Finder(ender)

        self.delimiter_length = len(delimiter)
        self.ender_length = len(ender)

        self.state = ParserState.PS_START

        self.expected_parts = []

        self.active_part = None
        self.default_part = Part('_default', NullTarget())

        self._leftover_buffer = None

    cpdef register(self, str name, object target):
        if not self._part_for(name):
            self.expected_parts.append(Part(name, target))

    cdef set_active_part(self, part):
        self.active_part = part

    cdef unset_active_part(self):
        if self.active_part:
            self.active_part.finish()
        self.set_active_part(None)

    cdef on_body(self, bytes value):
        if self.active_part:
            self.active_part.data_received(value)

    cdef _part_for(self, name):
        for part in self.expected_parts:
            if part.name == name:
                return part

    cpdef int data_received(self, bytes data):
        if not data:
            return 0

        cdef bytes chunk
        cdef size_t buffer_start, buffer_end

        if self._leftover_buffer:
            chunk = self._leftover_buffer + data

            buffer_start = 0
            buffer_end = len(self._leftover_buffer)

            self._leftover_buffer = None
        else:
            chunk = data

            buffer_start = 0
            buffer_end = 0

        return self._parse(chunk, buffer_start, buffer_end)

    cdef int _parse(self, bytes chunk,
                    size_t buffer_start, size_t buffer_end):
        cdef size_t idx, chunk_len, _idx
        cdef char byte
        cdef const char *chunk_ptr, *ptr, *ptr_first, *ptr_last
        chunk_ptr = chunk
        chunk_len = len(chunk)

        idx = buffer_end
        while idx < chunk_len:
            byte = chunk_ptr[idx]

            if self.state == ParserState.PS_START:
                if byte != Constants.Hyphen:
                    return 1

                buffer_end += 1
                self.state = ParserState.PS_STARTING_BOUNDARY
            elif self.state == ParserState.PS_STARTING_BOUNDARY:
                if byte != Constants.Hyphen:
                    return 1

                buffer_end += 1
                self.state = ParserState.PS_READING_BOUNDARY
            elif self.state == ParserState.PS_READING_BOUNDARY:
                buffer_end += 1

                if byte == Constants.CR:
                    self.state = ParserState.PS_ENDING_BOUNDARY
            elif self.state == ParserState.PS_ENDING_BOUNDARY:
                if byte != Constants.LF:
                    return 1

                buffer_end += 1

                if buffer_end - buffer_start < 4:
                    return 1

                if chunk_ptr[buffer_start] == Constants.Hyphen and \
                        chunk_ptr[buffer_start + 1] == Constants.Hyphen and \
                        chunk_ptr[buffer_end - 1] == Constants.Hyphen and \
                        chunk_ptr[buffer_end - 2] == Constants.Hyphen:
                    self.state = ParserState.PS_END

                buffer_start = buffer_end = idx + 1

                self.state = ParserState.PS_READING_HEADER
            elif self.state == ParserState.PS_READING_HEADER:
                buffer_end += 1

                if byte == Constants.CR:
                    self.state = ParserState.PS_ENDING_HEADER
            elif self.state == ParserState.PS_ENDING_HEADER:
                if byte != Constants.LF:
                    return 1

                buffer_end += 1

                value, params = cgi.parse_header(
                    chunk[buffer_start: buffer_end].decode('utf-8'))

                if value.startswith('Content-Disposition') and \
                        value.endswith('form-data'):
                    name = params.get('name')
                    if name:
                        part = self._part_for(name) or self.default_part
                        part.headers_parsed(params)
                        part.start()

                        self.set_active_part(part)

                buffer_start = buffer_end = idx + 1

                self.state = ParserState.PS_ENDED_HEADER
            elif self.state == ParserState.PS_ENDED_HEADER:
                if byte == Constants.CR:
                    self.state = ParserState.PS_ENDING_ALL_HEADERS
                else:
                    self.state = ParserState.PS_READING_HEADER

                buffer_end += 1
            elif self.state == ParserState.PS_ENDING_ALL_HEADERS:
                if byte != Constants.LF:
                    return 1

                buffer_start = buffer_end = idx + 1
                self.state = ParserState.PS_READING_BODY
            elif self.state == ParserState.PS_READING_BODY:
                buffer_end += 1

                self.delimiter_finder.feed(byte)
                self.ender_finder.feed(byte)

                if self.delimiter_finder.found():
                    self.state = ParserState.PS_READING_HEADER

                    if buffer_end - buffer_start > self.delimiter_length:
                        _idx = buffer_end - self.delimiter_length

                        self.on_body(chunk[buffer_start: _idx - 2])

                        buffer_start = buffer_end = idx + 1

                    self.unset_active_part()
                    self.delimiter_finder.reset()
                elif self.ender_finder.found():
                    self.state = ParserState.PS_END

                    if buffer_end - buffer_start > self.ender_length:
                        _idx = buffer_end - self.ender_length

                        if chunk_ptr[_idx - 1] == Constants.LF and \
                                chunk_ptr[_idx - 2] == Constants.CR:
                            self.on_body(chunk[buffer_start: _idx - 2])
                        else:
                            self.on_body(chunk[buffer_start: _idx])

                        buffer_start = buffer_end = idx + 1

                    self.unset_active_part()
                    self.ender_finder.reset()
                else:
                    # The following block is for speedup only
                    # The idea is to skip all data not containing
                    # delimiter starting sequence '--' when
                    # we are not already in the middle of potential delimiter

                    if 1 == 2 and self.ender_finder.inactive() and \
                            self.delimiter_finder.inactive() and \
                            idx + 1 + 10 < chunk_len:

                        # potentially fast forwarded chars:
                        # chunk[idx+1 ..  chunk_len-1] (including borders)
                        # ptr_first = &chunk_ptr[idx + 1]
                        # ptr_last = &chunk_ptr[chunk_len - 1]

                        # for ptr in xrange(ptr_first, ptr_last):
                        for _idx in xrange(idx + 1, chunk_len - 1 - 5):
                            if chunk_ptr[_idx] != '-' or chunk_ptr[_idx + 1] != '-':
                                # buffer_end += 1
                                # idx += 1
                                pass

            elif self.state == ParserState.PS_END:
                return 0
            else:
                return 1

            idx += 1

        if self.state == ParserState.PS_READING_BODY and \
                buffer_end - buffer_start > Constants.MinFileBodyChunkSize:
            _idx = buffer_end - 1 - \
                max(self.delimiter_finder.matched_length(),
                    self.ender_finder.matched_length())
            self.on_body(chunk[buffer_start: _idx])
            buffer_start = idx - 1

        if buffer_end - buffer_start > 0:
            self._leftover_buffer = chunk[buffer_start: buffer_end]

        return 0
