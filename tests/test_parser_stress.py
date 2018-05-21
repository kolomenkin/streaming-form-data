from io import BytesIO
import math
from numpy import random
from unittest import TestCase

from requests_toolbelt import MultipartEncoder

from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import ValueTarget


def get_random_bytes(size, seed):
    random.seed(seed)
    return random.bytes(size)

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
        n /= base;
    raise Exception('is_power_of: unexpected result with x = ' +
                    str(x) + ' and base = ' + str(base)) 

def is_square(n):
    sq = int(math.sqrt(n))
    return sq * sq == n

def is_multiple(n, base):
    return n % base == 0

def is_interesting_number(n):
    if is_prime(n):
        return True

    if is_power_of(n, 2) or is_power_of(n-1, 2) or is_power_of(n+1, 2):
        return True

    if is_power_of(n, 10) or is_power_of(n-1, 10) or is_power_of(n+1, 10):
        return True

    if is_multiple(n, 1024) or is_multiple(n-1, 1024) or is_multiple(n+1, 1024):
        return True

    if is_multiple(n, 1000) or is_multiple(n-1, 1000) or is_multiple(n+1, 1000):
        return True

    if is_square(n):
        return True

    return False

class DifferentChunksTestCase(TestCase):

    def test_basic_last_attach(self):
        self.do_test(True)
        pass

    def test_basic_first_attach(self):
        self.do_test(False)
        pass

    def do_test(self, last_attach = True):
        data = get_random_bytes(1024 * 1024, 59)

        with BytesIO(data) as dataset_:
            if last_attach:
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

        interesting_number_count = 0

        for default_chunksize in range(1, 70 * 1000 + 2):
            if not is_interesting_number(default_chunksize):
                continue

            interesting_number_count += 1

            with self.subTest(default_chunksize=default_chunksize) as s:
                print('chunksize: ', default_chunksize)

                parser = StreamingFormDataParser(
                    headers={'Content-Type': content_type})

                target = ValueTarget()
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
                result = target.value
                self.assertEqual(len(result), len(data))
                self.assertEqual(result, data)
                result = None

        self.assertEqual(interesting_number_count, 7559)
