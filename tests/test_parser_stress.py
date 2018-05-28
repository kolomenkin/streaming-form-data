from io import BytesIO
from itertools import chain
import math
from numpy import random
from unittest import TestCase

from requests_toolbelt import MultipartEncoder

from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import ValueTarget


def get_random_bytes(size, seed):
    random.seed(seed)
    return random.bytes(size)


def get_hyphens_crlfs(size, seed):
    random.seed(seed)
    return random.choice([b'\r', b'\n', b'-'], size,
                         p=[0.25, 0.25, 0.5]).tobytes()


def is_prime(n):
    if n % 2 == 0 and n > 2:
        return False
    return all(n % i for i in range(3, int(math.sqrt(n)) + 1, 2))


def is_power_of(x, base):
    n = x
    while(n > 0):
        if n == 1:
            return True
        if n % base:
            return False
        n /= base
    raise Exception('is_power_of: unexpected result with x = ' +
                    str(x) + ' and base = ' + str(base))


def is_square(n):
    sq = int(math.sqrt(n))
    return sq * sq == n


def is_multiple(n, base):
    return n % base == 0


def is_interesting_number(n):
    if n < 1:
        return False

    if n <= 1000 and is_prime(n):
        return True

    if is_power_of(n, 2) \
            or is_power_of(n-1, 2) \
            or is_power_of(n+1, 2):
        return True

    if is_power_of(n, 10) \
            or is_power_of(n-1, 10) \
            or is_power_of(n+1, 10):
        return True

    if is_multiple(n, 1024) \
            or is_multiple(n-1, 1024) \
            or is_multiple(n+1, 1024):
        return True

    if is_multiple(n, 1000) \
            or is_multiple(n-1, 1000) \
            or is_multiple(n+1, 1000):
        return True

    if is_square(n):
        return True

    if n <= 64:
        return True

    return False


def is_interesting_number_short(n):
    if n < 1:
        return False

    if n <= 100 and is_prime(n):
        return True

    if is_power_of(n, 2) \
            or is_power_of(n-1, 2) \
            or is_power_of(n+1, 2):
        return True

    if is_power_of(n, 10) \
            or is_power_of(n-1, 10) \
            or is_power_of(n+1, 10):
        return True

    if is_multiple(n, 4 * 1024) \
            or is_multiple(n-1, 1024) \
            or is_multiple(n+1, 1024):
        return True

    if is_multiple(n, 5 * 1000) \
            or is_multiple(n-1, 1000) \
            or is_multiple(n+1, 1000):
        return True

    if is_square(n) and n <= 100:
        return True

    if n <= 32:
        return True

    return False


def get_max_number():
    return 70 * 1000 + 1


def get_interesting_numbers(short=False):
    if short:
        interesting_numbers = (x for x in range(1, 17000)
                               if is_interesting_number_short(x))
    else:
        interesting_numbers = (x for x in range(1, get_max_number() + 1)
                               if is_interesting_number(x))
    return list(interesting_numbers)


class TestingValueTarget(ValueTarget):
    def __init__(self):
        super().__init__()
        self.started = False
        self.finished = False

    def start(self):
        self.started = True
        super().start()

    def finish(self):
        self.finished = True
        super().finish()


class DifferentChunksTestCase(TestCase):

    def test_basic_last_attach(self):
        data = get_random_bytes(1024 * 1024, 159)
        self.do_test(data, 'random_bytes', True)
        pass

    def test_basic_first_attach(self):
        data = get_random_bytes(1024 * 1024, 259)
        self.do_test(data, 'random_bytes', False)
        pass

    def test_special_chars_last_attach(self):
        data = get_hyphens_crlfs(1024 * 1024, 359)
        self.do_test(data, 'hyphens_crlfs', True)
        pass

    def test_special_chars_first_attach(self):
        data = get_hyphens_crlfs(1024 * 1024, 459)
        self.do_test(data, 'hyphens_crlfs', False)
        pass

    def do_test(self, data, data_name, last_part):

        with BytesIO(data) as dataset_:
            if last_part:
                fields = {
                    'name': 'hello world',
                    'file': ('file.dat', dataset_, 'binary/octet-stream')
                }
            else:
                fields = {
                    'file': ('file.dat', dataset_, 'binary/octet-stream'),
                    'name': 'hello world'
                }

            encoder = MultipartEncoder(fields=fields)
            content_type = encoder.content_type
            body = encoder.to_string()
            encoder = None

        interesting_numbers = get_interesting_numbers()
        self.assertEqual(len(interesting_numbers), 880)

        idx = 0
        for default_chunksize in interesting_numbers:
            idx += 1

            with self.subTest(data_name=data_name,
                              default_chunksize=default_chunksize):
                # print(idx, '; name: ', data_name, '; last_part: ',
                #       last_part, '; chunksize: ', default_chunksize)

                parser = StreamingFormDataParser(
                    headers={'Content-Type': content_type})

                target = TestingValueTarget()
                parser.register('file', target)

                remaining = len(body)
                offset = 0

                while(remaining > 0):
                    chunksize = min(remaining, default_chunksize)
                    parser.data_received(body[offset:offset + chunksize])
                    offset += chunksize
                    remaining -= chunksize

                self.assertEqual(offset, len(body))
                self.assertEqual(target.multipart_filename, 'file.dat')
                self.assertEqual(target.started, True)
                self.assertEqual(target.finished, True)
                result = target.value
                self.assertEqual(len(result), len(data))
                self.assertEqual(result, data)
                result = None
        self.assertEqual(idx, len(interesting_numbers))


class DifferentFileSizeTestCase(TestCase):

    def test_basic(self):
        data = get_random_bytes(get_max_number(), 137)
        self.do_test(data, 'random_bytes')
        pass

    def test_special_chars(self):
        data = get_hyphens_crlfs(get_max_number(), 237)
        self.do_test(data, 'hyphens_crlfs')
        pass

    def do_test(self, data, data_name):

        interesting_numbers = get_interesting_numbers()

        idx = 0
        for file_size in chain([0, ], interesting_numbers):
            idx += 1

            with self.subTest(data_name=data_name, file_size=file_size):
                # print(idx, '; name: ', data_name, '; file_size: ', file_size)

                data_view = data[0:file_size]
                with BytesIO(data[0:file_size]) as dataset_:
                    fields = {
                        'file': ('file.dat', dataset_, 'binary/octet-stream')
                    }
                    encoder = MultipartEncoder(fields=fields)
                    content_type = encoder.content_type
                    body = encoder.to_string()
                    encoder = None

                parser = StreamingFormDataParser(
                    headers={'Content-Type': content_type})

                target = TestingValueTarget()
                parser.register('file', target)

                remaining = len(body)
                offset = 0

                while(remaining > 0):
                    chunksize = min(remaining, 1024)
                    parser.data_received(body[offset:offset + chunksize])
                    offset += chunksize
                    remaining -= chunksize

                self.assertEqual(offset, len(body))
                self.assertEqual(target.multipart_filename, 'file.dat')
                self.assertEqual(target.started, True)
                self.assertEqual(target.finished, True)
                result = target.value
                self.assertEqual(len(result), len(data_view))
                self.assertEqual(result, data_view)
                result = None
        self.assertEqual(idx, len(interesting_numbers) + 1)


class StressMatrixTestCase(TestCase):

    def test_basic(self):
        data = get_random_bytes(get_max_number(), 171)
        self.do_test(data, 'random_bytes')
        pass

    def do_test(self, data, data_name):

        interesting_numbers = get_interesting_numbers(short=True)
        self.assertEqual(len(interesting_numbers), 140)

        idx = 0
        for file_size in chain([0, ], interesting_numbers):

            data_view = data[0:file_size]
            with BytesIO(data[0:file_size]) as dataset_:
                fields = {
                    'file': ('file.dat', dataset_, 'binary/octet-stream')
                }
                encoder = MultipartEncoder(fields=fields)
                content_type = encoder.content_type
                body = encoder.to_string()
                encoder = None

            for default_chunksize in interesting_numbers:
                if default_chunksize > file_size:
                    continue
                idx += 1

                with self.subTest(data_name=data_name,
                                  file_size=file_size,
                                  default_chunksize=default_chunksize):
                    # print(idx, '; name: ', data_name, '; file_size: ',
                    #       file_size, '; chunksize: ', default_chunksize)

                    parser = StreamingFormDataParser(
                        headers={'Content-Type': content_type})

                    target = TestingValueTarget()
                    parser.register('file', target)

                    remaining = len(body)
                    offset = 0

                    while(remaining > 0):
                        chunksize = min(remaining, default_chunksize)
                        parser.data_received(body[offset:offset + chunksize])
                        offset += chunksize
                        remaining -= chunksize

                    self.assertEqual(offset, len(body))
                    self.assertEqual(target.multipart_filename, 'file.dat')
                    self.assertEqual(target.started, True)
                    self.assertEqual(target.finished, True)
                    result = target.value
                    self.assertEqual(len(result), len(data_view))
                    self.assertEqual(result, data_view)
                    result = None
        self.assertEqual(idx, len(interesting_numbers) *
                         (len(interesting_numbers) + 1) / 2)
