import hashlib
from os import path


class BaseTarget:
    """Targets determine what to do with some input once the parser is done with
    it. Any new Target should inherit from this class and override
    data_received.
    """

    def headers_parsed(self, content_disposition_dict):
        pass

    def start(self):
        pass

    def data_received(self, chunk):
        raise NotImplementedError()

    def finish(self):
        pass


class NullTarget(BaseTarget):
    def data_received(self, chunk):
        pass


class ValueTarget(BaseTarget):
    def __init__(self):
        self._values = []

    def data_received(self, chunk):
        self._values.append(chunk)

    @property
    def value(self):
        return b''.join(self._values)


class FileTarget(BaseTarget):
    def __init__(self, filename, openmode='wb'):
        self.filename = filename
        assert 'b' in openmode, \
            'openmode should be binary. ' + \
            'I.e. it should contain \'b\' character.' + \
            'Current openmode: %s' % openmode
        self.openmode = openmode
        self._fd = None

    def start(self):
        self._fd = open(self.filename, self.openmode)

    def data_received(self, chunk):
        self._fd.write(chunk)

    def finish(self):
        self._fd.close()


class FileTargetUsingRemoteName(BaseTarget):
    def __init__(self, directory, openmode='wb'):
        self.directory = directory
        assert 'b' in openmode, \
            'openmode should be binary. ' + \
            'I.e. it should contain \'b\' character.' + \
            'Current openmode: %s' % openmode
        self.openmode = openmode
        self.filename = None
        self._fd = None

    def headers_parsed(self, content_disposition_dict):
        remote_name = content_disposition_dict['filename']
        self.filename = path.join(self.directory, remote_name)

    def start(self):
        self._fd = open(self.filename, self.openmode)

    def data_received(self, chunk):
        self._fd.write(chunk)

    def finish(self):
        self._fd.close()


class SHA256Target(BaseTarget):
    def __init__(self):
        self._hash = hashlib.sha256()

    def data_received(self, chunk):
        self._hash.update(chunk)

    @property
    def value(self):
        return self._hash.hexdigest()
