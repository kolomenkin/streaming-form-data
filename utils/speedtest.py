from io import BytesIO
from requests_toolbelt import MultipartEncoder
from streaming_form_data.parser import StreamingFormDataParser
from streaming_form_data.targets import NullTarget, BaseTarget
from time import time


class DummyTarget(BaseTarget):
    def __init__(self, print_report):
        self.report = print_report

    def start(self):
        if self.report:
            print('DummyTarget: start')

    def data_received(self, chunk):
        if self.report:
            print('DummyTarget: data_received:', len(chunk), 'bytes')

    def finish(self):
        if self.report:
            print('DummyTarget: finish')


def main():
    print('Prepare data...')
    begin_time = time()

    kibibyte = 1024
    mebibyte = kibibyte * kibibyte
    filedata_size = 40 * mebibyte
    filedata = bytearray(filedata_size)

    value = 42
    for i in range(0, filedata_size):
        filedata[i] = value % 256
        # value = value + 1 if value != 255 else 0
        value = (value * 48271) % 2147483647  # std::minstd_rand

    with BytesIO(filedata) as fd:
        content_type = 'binary/octet-stream'

        encoder = MultipartEncoder(fields={
            'file': ('file', fd, content_type)
        })
        headers = {'Content-Type': encoder.content_type}
        body = encoder.to_string()

    filedata = None  # free memory
    parser = StreamingFormDataParser(headers)
    parser.register('name', NullTarget())
    parser.register('lines', NullTarget())
    parser.register('file', DummyTarget(print_report=False))

    defaultChunksize = 32 * kibibyte
    position = 0
    body_length = len(body)
    remaining = body_length

    end_time = time()
    print('Data prepared')
    time_diff = end_time - begin_time
    print('Preparation took: %.3f sec; speed: %.3f MB/s; body size: %.3f MB' %
          (time_diff,
           (body_length / time_diff / mebibyte if time_diff > 0 else 0),
           body_length / mebibyte))
    print('Begin test...')

    begin_time = time()
    while remaining > 0:
        chunksize = min(defaultChunksize, remaining)
        parser.data_received(body[position: position + chunksize])
        remaining -= chunksize
        position += chunksize
    end_time = time()

    print('End test')
    time_diff = end_time - begin_time
    print('Test took: %.3f sec; speed: %.3f MB/s; body size: %.3f MB' %
          (time_diff,
           (body_length / time_diff / mebibyte if time_diff > 0 else 0),
           body_length / mebibyte))


if __name__ == '__main__':
    main()
