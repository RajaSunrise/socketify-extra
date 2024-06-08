from enum import IntEnum
from .uws import ffi, lib

import inspect
import logging


class CompressOptions(IntEnum):
    # Disabled, shared, shared are "special" values
    DISABLED = lib.DISABLED
    SHARED_COMPRESSOR = lib.SHARED_COMPRESSOR
    SHARED_DECOMPRESSOR = lib.SHARED_DECOMPRESSOR
    # Highest 4 bits describe decompressor
    DEDICATED_DECOMPRESSOR_32KB = lib.DEDICATED_DECOMPRESSOR_32KB
    DEDICATED_DECOMPRESSOR_16KB = lib.DEDICATED_DECOMPRESSOR_16KB
    DEDICATED_DECOMPRESSOR_8KB = lib.DEDICATED_DECOMPRESSOR_8KB
    DEDICATED_DECOMPRESSOR_4KB = lib.DEDICATED_DECOMPRESSOR_4KB
    DEDICATED_DECOMPRESSOR_2KB = lib.DEDICATED_DECOMPRESSOR_2KB
    DEDICATED_DECOMPRESSOR_1KB = lib.DEDICATED_DECOMPRESSOR_1KB
    DEDICATED_DECOMPRESSOR_512B = lib.DEDICATED_DECOMPRESSOR_512B
    # Same as 32kb
    DEDICATED_DECOMPRESSOR = (lib.DEDICATED_DECOMPRESSOR,)

    # Lowest 8 bit describe compressor
    DEDICATED_COMPRESSOR_3KB = lib.DEDICATED_COMPRESSOR_3KB
    DEDICATED_COMPRESSOR_4KB = lib.DEDICATED_COMPRESSOR_4KB
    DEDICATED_COMPRESSOR_8KB = lib.DEDICATED_COMPRESSOR_8KB
    DEDICATED_COMPRESSOR_16KB = lib.DEDICATED_COMPRESSOR_16KB
    DEDICATED_COMPRESSOR_32KB = lib.DEDICATED_COMPRESSOR_32KB
    DEDICATED_COMPRESSOR_64KB = lib.DEDICATED_COMPRESSOR_64KB
    DEDICATED_COMPRESSOR_128KB = lib.DEDICATED_COMPRESSOR_128KB
    DEDICATED_COMPRESSOR_256KB = lib.DEDICATED_COMPRESSOR_256KB
    # Same as 256kb
    DEDICATED_COMPRESSOR = lib.DEDICATED_COMPRESSOR


class OpCode(IntEnum):
    CONTINUATION = 0
    TEXT = 1
    BINARY = 2
    CLOSE = 8
    PING = 9
    PONG = 10


class SendStatus(IntEnum):
    BACKPRESSURE = 0
    SUCCESS = 1
    DROPPED = 2


# block import cirular
#for response.py
@ffi.callback("void(uws_res_t*, void*)")
def uws_generic_aborted_handler(response, user_data):
    if user_data != ffi.NULL:
        try:
            res = ffi.from_handle(user_data)
            res.trigger_aborted()
        except Exception:
            pass

@ffi.callback("bool(uws_res_t*, uintmax_t, void*)")
def uws_generic_on_writable_handler(res, offset, user_data):
    if user_data != ffi.NULL:
        res = ffi.from_handle(user_data)
        res.app.loop.is_idle = False
        result = res.trigger_writable_handler(offset)
        return result
    return False


@ffi.callback("void(uws_res_t*, const char*, size_t, bool, void*)")
def uws_generic_on_data_handler(res, chunk, chunk_length, is_end, user_data):
    if user_data != ffi.NULL:
        res = ffi.from_handle(user_data)
        res.app.loop.is_idle = False
        if chunk == ffi.NULL:
            data = None
        else:
            data = ffi.unpack(chunk, chunk_length)

        res.trigger_data_handler(data, bool(is_end))

@ffi.callback("void(uws_res_t*, void*)")
def uws_generic_cork_handler(res, user_data):
    if user_data != ffi.NULL:
        response = ffi.from_handle(user_data)
        try:
            if inspect.iscoroutinefunction(response._cork_handler):
                raise RuntimeError("Calls inside cork must be sync")
            response._cork_handler(response)
        except Exception as err:
            logging.error("Error on cork handler %s" % str(err))


# for request.py
@ffi.callback("void(const char*, size_t, const char*, size_t, void*)")
def uws_req_for_each_header_handler(
    header_name, header_name_size, header_value, header_value_size, user_data
):
    if user_data != ffi.NULL:
        try:
            req = ffi.from_handle(user_data)
            header_name = ffi.unpack(header_name, header_name_size).decode("utf-8")
            header_value = ffi.unpack(header_value, header_value_size).decode("utf-8")

            req.trigger_for_each_header_handler(header_name, header_value)
        except Exception:  # invalid utf-8
            return


# for websocket.py
@ffi.callback("void(const char*, size_t, void*)")
def uws_req_for_each_topic_handler(topic, topic_size, user_data):
    if user_data != ffi.NULL:
        try:
            ws = ffi.from_handle(user_data)
            topic = ffi.unpack(topic, topic_size).decode("utf-8")
            ws.trigger_for_each_topic_handler(topic)
        except Exception:  # invalid utf-8
            return


@ffi.callback("void(void*)")
def uws_ws_cork_handler(user_data):
    if user_data != ffi.NULL:
        ws = ffi.from_handle(user_data)
        try:
            if inspect.iscoroutinefunction(ws._cork_handler):
                raise RuntimeError("Calls inside cork must be sync")
            ws._cork_handler(ws)
        except Exception as err:
            logging.error("Error on cork handler %s" % str(err))