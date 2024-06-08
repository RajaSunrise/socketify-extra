from typing import Union
from http import cookies
from datetime import datetime
from io import BytesIO
from urllib.parse import quote_plus, parse_qs, unquote_plus

import uuid
import inspect
import logging

from .background import (
    uws_generic_cork_handler, uws_generic_aborted_handler,
    uws_generic_on_data_handler, uws_generic_on_writable_handler
)
from .uws import lib, ffi
from .request import AppRequest

class AppResponse:
    def __init__(self, response, app):
        self.res = response
        self.app = app
        self.aborted = False
        self._aborted_handler = None
        self._writable_handler = None
        self._data_handler = None
        self._ptr = ffi.new_handle(self)
        self._grabbed_abort_handler_once = False
        self._write_jar = None
        self._cork_handler = None
        self._lastChunkOffset = 0
        self._chunkFuture = None
        self._dataFuture = None
        self._data = None

    def cork(self, callback):
        self.app.loop.is_idle = False
        
        if not self.aborted:
            self.grab_aborted_handler()
            self._cork_handler = callback
            lib.uws_res_cork(
                self.app.SSL, self.res, uws_generic_cork_handler, self._ptr
            )

    def set_cookie(self, name, value, options):
        if options is None:
            options = {}
        if self._write_jar is None:
            self._write_jar = cookies.SimpleCookie()
        self._write_jar[name] = quote_plus(value)
        if isinstance(options, dict):
            for key in options:
                if key == "expires" and isinstance(options[key], datetime):
                    self._write_jar[name][key] = options[key].strftime(
                        "%a, %d %b %Y %H:%M:%S GMT"
                    )
                else:
                    self._write_jar[name][key] = options[key]

    def trigger_aborted(self):
        self.aborted = True
        self._ptr = ffi.NULL
        self.res = ffi.NULL
        if hasattr(self, "_aborted_handler") and hasattr(
            self._aborted_handler, "__call__"
        ):
            try:
                if inspect.iscoroutinefunction(self._aborted_handler):
                    self.run_async(self._aborted_handler(self))
                else:
                    self._aborted_handler(self)
            except Exception as err:
                logging.error("Error on abort handler %s" % str(err))
        return self

    def trigger_data_handler(self, data, is_end):
        if self.aborted:
            return self
        if hasattr(self, "_data_handler") and hasattr(self._data_handler, "__call__"):
            try:
                if inspect.iscoroutinefunction(self._data_handler):
                    self.run_async(self._data_handler(self, data, is_end))
                else:
                    self._data_handler(self, data, is_end)
            except Exception as err:
                logging.error("Error on data handler %s" % str(err))

        return self

    def trigger_writable_handler(self, offset):
        if self.aborted:
            return False
        if hasattr(self, "_writable_handler") and hasattr(
            self._writable_handler, "__call__"
        ):
            try:
                if inspect.iscoroutinefunction(self._writable_handler):
                    raise RuntimeError("AppResponse.on_writable must be synchronous")
                return self._writable_handler(self, offset)
            except Exception as err:
                logging.error("Error on writable handler %s" % str(err))
            return False
        return False

    def run_async(self, task):
        self.grab_aborted_handler()
        return self.app.loop.run_async(task, self)

    async def get_form_urlencoded(self, encoding="utf-8"):
        data = await self.get_data()
        try:
            # decode and unquote all
            result = {}
            parsed = parse_qs(data.getvalue(), encoding=encoding)
            has_value = False
            for key in parsed:
                has_value = True
                try:
                    value = parsed[key]
                    new_key = key.decode(encoding)
                    last_value = value[len(value) - 1]

                    result[new_key] = unquote_plus(last_value.decode(encoding))
                except Exception:
                    pass
            return result if has_value else None
        except Exception:
            return None  # invalid encoding

    async def get_text(self, encoding="utf-8"):
        data = await self.get_data()
        try:
            return data.getvalue().decode(encoding)
        except Exception:
            return None  # invalid encoding

    def get_json(self):
        data = self.get_data()
        try:
            return self.app._json_serializer.loads(data.getvalue().decode("utf-8"))
        except Exception:
            return None

    def send_chunk(self, buffer, total_size):
        self._chunkFuture = self.app.loop.create_future()
        self._lastChunkOffset = 0

        def is_aborted(self):
            self.aborted = True
            try:
                if not self._chunkFuture.done():
                    self._chunkFuture.set_result(
                        (False, True)
                    )  # if aborted set to done True and ok False
            except Exception:
                pass

        def on_writeble(self, offset):
            # Here the timeout is off, we can spend as much time before calling try_end we want to
            (ok, done) = self.try_end(
                buffer[offset - self._lastChunkOffset : :], total_size
            )
            if ok:
                self._chunkFuture.set_result((ok, done))
            return ok

        self.on_writable(on_writeble)
        self.on_aborted(is_aborted)

        if self.aborted:
            self._chunkFuture.set_result(
                (False, True)
            )  # if aborted set to done True and ok False
            return self._chunkFuture

        self._lastChunkOffset = self.get_write_offset()

        (ok, done) = self.try_end(buffer, total_size)
        if ok:
            self._chunkFuture.set_result((ok, done))
            return self._chunkFuture

        # failed to send chunk
        return self._chunkFuture

    def get_data(self):
        self._dataFuture = self.app.loop.create_future()
        self._data = BytesIO()

        def is_aborted(self):
            self.aborted = True
            try:
                if not self._dataFuture.done():
                    self._dataFuture.set_result(self._data)
            except Exception:
                pass

        def get_chunks(self, chunk, is_end):
            if chunk is not None:
                self._data.write(chunk)
            if is_end:
                self._dataFuture.set_result(self._data)
                self._data = None

        self.on_aborted(is_aborted)
        self.on_data(get_chunks)
        return self._dataFuture

    def grab_aborted_handler(self):
        # only needed if is async
        if not self.aborted and not self._grabbed_abort_handler_once:
            self._grabbed_abort_handler_once = True
            lib.uws_res_on_aborted(
                self.app.SSL, self.res, uws_generic_aborted_handler, self._ptr
            )
        return self

    def redirect(self, location, status_code=302):
        self.write_status(status_code)
        self.write_header("Location", location)
        self.end_without_body(False)
        return self

    def write_offset(self, offset):
        lib.uws_res_override_write_offset(
            self.app.SSL, self.res, ffi.cast("uintmax_t", offset)
        )
        return self

    def close(self):
        lib.uws_res_close(
            self.app.SSL, self.res
        )
        return self

    def try_end(self, message, total_size, end_connection=False):
        self.app.loop.is_idle = False
        try:
            if self.aborted:
                return False, True
            if self._write_jar is not None:
                self.write_header("Set-Cookie", self._write_jar.output(header=""))
                self._write_jar = None
            if isinstance(message, str):
                data = message.encode("utf-8")
            elif isinstance(message, bytes):
                data = message
            else:
                return False, True
            result = lib.uws_res_try_end(
                self.app.SSL,
                self.res,
                data,
                len(data),
                ffi.cast("uintmax_t", total_size),
                1 if end_connection else 0,
            )
            return bool(result.ok), bool(result.has_responded)
        except Exception:
            return False, True

    def cork_end(self, message, end_connection=False):
        self.cork(lambda res: res.end(message, end_connection))
        return self

    def render(self, *args, **kwargs):
        if self.app._template:

            def render(res):
                res.write_header(b"Content-Type", b"text/html")
                res.end(self.app._template.render(*args, **kwargs))

            self.cork(render)
            return self
        raise RuntimeError("No registered templated engine")

    def get_remote_address_bytes(self):
        buffer = ffi.new("char**")
        length = lib.uws_res_get_remote_address(self.app.SSL, self.res, buffer)
        buffer_address = ffi.addressof(buffer, 0)[0]
        if buffer_address == ffi.NULL:
            return None
        try:
            return ffi.unpack(buffer_address, length)
        except Exception:  # invalid
            return None

    def get_remote_address(self):
        buffer = ffi.new("char**")
        length = lib.uws_res_get_remote_address_as_text(self.app.SSL, self.res, buffer)
        buffer_address = ffi.addressof(buffer, 0)[0]
        if buffer_address == ffi.NULL:
            return None
        try:
            return ffi.unpack(buffer_address, length).decode("utf-8")
        except Exception:  # invalid utf-8
            return None

    def get_proxied_remote_address_bytes(self):
        buffer = ffi.new("char**")
        length = lib.uws_res_get_proxied_remote_address(self.app.SSL, self.res, buffer)
        buffer_address = ffi.addressof(buffer, 0)[0]
        if buffer_address == ffi.NULL:
            return None
        try:
            return ffi.unpack(buffer_address, length)
        except Exception:  # invalid
            return None

    def get_proxied_remote_address(self):
        buffer = ffi.new("char**")
        length = lib.uws_res_get_proxied_remote_address_as_text(
            self.app.SSL, self.res, buffer
        )
        buffer_address = ffi.addressof(buffer, 0)[0]
        if buffer_address == ffi.NULL:
            return None
        try:
            return ffi.unpack(buffer_address, length).decode("utf-8")
        except Exception:  # invalid utf-8
            return None

    def cork_send(
        self,
        message: any,
        content_type: Union[str, bytes] = b"text/plain",
        status: Union[str, bytes, int] = b"200 OK",
        headers=None,
        end_connection: bool = False,
    ):
        # TODO: use socketify_res_cork_send_int_code and socketify_res_cork_send after optimize headers
        self.cork(
            lambda res: res.send(message, content_type, status, headers, end_connection)
        )
        return self

    def send(
        self,
        message: any = b"",
        content_type: Union[str, bytes] = b"text/plain",
        status: Union[str, bytes, int] = b"200 OK",
        headers = None,
        end_connection: bool = False,
    ):
        self.app.loop.is_idle = False
        
        # TODO: optimize headers
        if headers is not None:
            for name, value in headers:
                self.write_header(name, value)
        try:

            # TODO: optimize Set-Cookie
            if self._write_jar is not None:
                self.write_header("Set-Cookie", self._write_jar.output(header=""))
                self._write_jar = None

            if isinstance(message, str):
                data = message.encode("utf-8")
            elif isinstance(message, bytes):
                data = message
            elif message is None:
                if isinstance(status, int):
                    lib.socketify_res_send_int_code(
                        self.app.SSL,
                        self.res,
                        ffi.NULL,
                        0,
                        status,
                        content_type,
                        len(content_type),
                        1 if end_connection else 0,
                    )
                elif isinstance(status, str):
                    status = status.encode("utf-8")
                    lib.socketify_res_send(
                        self.app.SSL,
                        self.res,
                        ffi.NULL,
                        0,
                        status,
                        len(status),
                        content_type,
                        len(content_type),
                        1 if end_connection else 0,
                    )
                else:
                    lib.socketify_res_send(
                        self.app.SSL,
                        self.res,
                        ffi.NULL,
                        0,
                        status,
                        len(status),
                        content_type,
                        len(content_type),
                        1 if end_connection else 0,
                    )
                return self
            else:
                data = self.app._json_serializer.dumps(message).encode("utf-8")
                content_type = b"application/json"

            if isinstance(status, int):
                lib.socketify_res_send_int_code(
                    self.app.SSL,
                    self.res,
                    data,
                    len(data),
                    status,
                    content_type,
                    len(content_type),
                    1 if end_connection else 0,
                )
            elif isinstance(status, str):
                status = status.encode("utf-8")
                lib.socketify_res_send(
                    self.app.SSL,
                    self.res,
                    ffi.NULL,
                    0,
                    status,
                    len(status),
                    content_type,
                    len(content_type),
                    1 if end_connection else 0,
                )
            else:
                lib.socketify_res_send(
                    self.app.SSL,
                    self.res,
                    data,
                    len(data),
                    status,
                    len(status),
                    content_type,
                    len(content_type),
                    1 if end_connection else 0,
                )

        finally:
            return self

    def end(self, message, end_connection=False):
        self.app.loop.is_idle = False
        
        try:
            if self.aborted:
                return self
            if self._write_jar is not None:
                self.write_header("Set-Cookie", self._write_jar.output(header=""))
                self._write_jar = None
            if isinstance(message, str):
                data = message.encode("utf-8")
            elif isinstance(message, bytes):
                data = message
            elif message is None:
                self.end_without_body(end_connection)
                return self
            else:
                self.write_header(b"Content-Type", b"application/json")
                data = self.app._json_serializer.dumps(message).encode("utf-8")
            lib.uws_res_end(
                self.app.SSL, self.res, data, len(data), 1 if end_connection else 0
            )
        finally:
            return self

    def pause(self):
        if not self.aborted:
            lib.uws_res_pause(self.app.SSL, self.res)
        return self

    def resume(self):
        self.app.loop.is_idle = False
        if not self.aborted:
            lib.uws_res_resume(self.app.SSL, self.res)
        return self

    def write_continue(self):
        self.app.loop.is_idle = False
        if not self.aborted:
            lib.uws_res_write_continue(self.app.SSL, self.res)
        return self

    def write_status(self, status_or_status_text):
        self.app.loop.is_idle = False
        if not self.aborted:
            if isinstance(status_or_status_text, int):
                if bool(
                    lib.socketify_res_write_int_status(
                        self.app.SSL, self.res, status_or_status_text
                    )
                ):
                    return self
                raise RuntimeError(
                    '"%d" Is not an valid Status Code' % status_or_status_text
                )

            elif isinstance(status_or_status_text, str):
                data = status_or_status_text.encode("utf-8")
            elif isinstance(status_or_status_text, bytes):
                data = status_or_status_text
            else:
                data = self.app._json_serializer.dumps(status_or_status_text).encode(
                    "utf-8"
                )

            lib.uws_res_write_status(self.app.SSL, self.res, data, len(data))
        return self

    def write_header(self, key, value):
        self.app.loop.is_idle = False
        if not self.aborted:
            if isinstance(key, str):
                key_data = key.encode("utf-8")
            elif isinstance(key, bytes):
                key_data = key
            else:
                key_data = self.app._json_serializer.dumps(key).encode("utf-8")

            if isinstance(value, int):
                lib.uws_res_write_header_int(
                    self.app.SSL,
                    self.res,
                    key_data,
                    len(key_data),
                    ffi.cast("uint64_t", value),
                )
            elif isinstance(value, str):
                value_data = value.encode("utf-8")
            elif isinstance(value, bytes):
                value_data = value
            else:
                value_data = self.app._json_serializer.dumps(value).encode("utf-8")
            lib.uws_res_write_header(
                self.app.SSL,
                self.res,
                key_data,
                len(key_data),
                value_data,
                len(value_data),
            )
        return self

    def end_without_body(self, end_connection=False):
        self.app.loop.is_idle = False
        if not self.aborted:
            if self._write_jar is not None:
                self.write_header("Set-Cookie", self._write_jar.output(header=""))
            lib.uws_res_end_without_body(
                self.app.SSL, self.res, 1 if end_connection else 0
            )
        return self

    def write(self, message):
        self.app.loop.is_idle = False
        if not self.aborted:
            if isinstance(message, str):
                data = message.encode("utf-8")
            elif isinstance(message, bytes):
                data = message
            else:
                data = self.app._json_serializer.dumps(message).encode("utf-8")
            lib.uws_res_write(self.app.SSL, self.res, data, len(data))
        return self

    def get_write_offset(self):
        if not self.aborted:
            return int(lib.uws_res_get_write_offset(self.app.SSL, self.res))
        return 0

    def has_responded(self):
        if self.aborted:
            return False
        return bool(lib.uws_res_has_responded(self.app.SSL, self.res))

    def on_aborted(self, handler):
        if hasattr(handler, "__call__"):
            self._aborted_handler = handler
            self.grab_aborted_handler()
        return self

    def on_data(self, handler):
        if not self.aborted:
            if hasattr(handler, "__call__"):
                self._data_handler = handler
                self.grab_aborted_handler()
                lib.uws_res_on_data(
                    self.app.SSL, self.res, uws_generic_on_data_handler, self._ptr
                )
        return self

    def upgrade(
        self,
        sec_web_socket_key,
        sec_web_socket_protocol,
        sec_web_socket_extensions,
        socket_context,
        user_data=None,
    ):
        if self.aborted:
            return False

        if isinstance(sec_web_socket_key, str):
            sec_web_socket_key_data = sec_web_socket_key.encode("utf-8")
        elif isinstance(sec_web_socket_key, bytes):
            sec_web_socket_key_data = sec_web_socket_key
        else:
            sec_web_socket_key_data = b""

        if isinstance(sec_web_socket_protocol, str):
            sec_web_socket_protocol_data = sec_web_socket_protocol.encode("utf-8")
        elif isinstance(sec_web_socket_protocol, bytes):
            sec_web_socket_protocol_data = sec_web_socket_protocol
        else:
            sec_web_socket_protocol_data = b""

        if isinstance(sec_web_socket_extensions, str):
            sec_web_socket_extensions_data = sec_web_socket_extensions.encode("utf-8")
        elif isinstance(sec_web_socket_extensions, bytes):
            sec_web_socket_extensions_data = sec_web_socket_extensions
        else:
            sec_web_socket_extensions_data = b""

        user_data_ptr = ffi.NULL
        if user_data is not None:
            _id = uuid.uuid4()
            user_data_ptr = ffi.new_handle((user_data, _id))
            # keep alive data
            self.app._socket_refs[_id] = user_data_ptr

        lib.uws_res_upgrade(
            self.app.SSL,
            self.res,
            user_data_ptr,
            sec_web_socket_key_data,
            len(sec_web_socket_key_data),
            sec_web_socket_protocol_data,
            len(sec_web_socket_protocol_data),
            sec_web_socket_extensions_data,
            len(sec_web_socket_extensions_data),
            socket_context,
        )
        return True

    def on_writable(self, handler):
        if not self.aborted:
            if hasattr(handler, "__call__"):
                self._writable_handler = handler
                self.grab_aborted_handler()
                lib.uws_res_on_writable(
                    self.app.SSL, self.res, uws_generic_on_writable_handler, self._ptr
                )
        return self

    def get_native_handle(self):
        return lib.uws_res_get_native_handle(self.app.SSL, self.res)

    def __del__(self):
        self.res = ffi.NULL
        self._ptr = ffi.NULL


class RequestResponseFactory:
    def __init__(self, app, max_size):
        self.factory_queue = []
        self.app = app
        self.max_size = max_size
        self.dispose = self._dispose
        self.populate = self._populate
        self.get = self._get

    def update_extensions(self):
        self.dispose = self._dispose_with_extension
        self.populate = self._populate_with_extension
        self.get = self._get_with_extension

    def _populate_with_extension(self):
        self.factory_queue = []
        for _ in range(0, self.max_size):
            response = AppResponse(None, self.app)
            # set default value in properties
            self.app._response_extension.set_properties(response)
            # bind methods to response
            self.app._response_extension.bind_methods(response)
            request = AppRequest(None, self.app)
            # set default value in properties
            self.app._request_extension.set_properties(request)
            # bind methods to request
            self.app._request_extension.bind_methods(request)
            self.factory_queue.append((response, request, True))

    def _populate(self):
        self.factory_queue = []
        for _ in range(0, self.max_size):
            response = AppResponse(None, self.app)
            request = AppRequest(None, self.app)
            self.factory_queue.append((response, request, True))

    def _get_with_extension(self, app, res, req):
        if len(self.factory_queue) == 0:
            response = AppResponse(res, app)
            # set default value in properties
            self.app._response_extension.set_properties(response)
            # bind methods to response
            self.app._response_extension.bind_methods(response)
            request = AppRequest(req, app)
            # set default value in properties
            self.app._request_extension.set_properties(request)
            # bind methods to request
            self.app._request_extension.bind_methods(request)
            return response, request, False

        instances = self.factory_queue.pop()
        (response, request, _) = instances
        response.res = res
        request.req = req
        return instances

    def _get(self, app, res, req):
        if len(self.factory_queue) == 0:
            response = AppResponse(res, app)
            request = AppRequest(req, app)
            return response, request, False

        instances = self.factory_queue.pop()
        (response, request, _) = instances
        response.res = res
        request.req = req
        return instances

    def _dispose_with_extension(self, instances):
        (res, req, _) = instances
        # dispose res
        res.res = None
        res.aborted = False
        res._aborted_handler = None
        res._writable_handler = None
        res._data_handler = None
        res._grabbed_abort_handler_once = False
        res._write_jar = None
        res._cork_handler = None
        res._lastChunkOffset = 0
        res._chunkFuture = None
        res._dataFuture = None
        res._data = None
        # set default value in properties
        self.app._response_extension.set_properties(res)
        # dispose req
        req.req = None
        req.read_jar = None
        req.jar_parsed = False
        req._for_each_header_handler = None
        req._headers = None
        req._params = None
        req._query = None
        req._url = None
        req._full_url = None
        req._method = None
        
        self.app._request_extension.set_properties(req)

        if res._ptr != ffi.NULL:
            ffi.release(res._ptr)
            res._ptr = ffi.NULL
        if req._ptr != ffi.NULL:
            ffi.release(req._ptr)
            req._ptr = ffi.NULL

        self.factory_queue.append(instances)

    def _dispose(self, instances):
        (res, req, _) = instances
        # dispose res
        res.res = None
        res.aborted = False
        res._aborted_handler = None
        res._writable_handler = None
        res._data_handler = None
        res._grabbed_abort_handler_once = False
        res._write_jar = None
        res._cork_handler = None
        res._lastChunkOffset = 0
        res._chunkFuture = None
        res._dataFuture = None
        res._data = None
        # dispose req
        req.req = None
        req.read_jar = None
        req.jar_parsed = False
        req._for_each_header_handler = None
        req._headers = None
        req._params = None
        req._query = None
        req._url = None
        req._full_url = None
        req._method = None

        if res._ptr != ffi.NULL:
            ffi.release(res._ptr)
            res._ptr = ffi.NULL
        if req._ptr != ffi.NULL:
            ffi.release(req._ptr)
            req._ptr = ffi.NULL

        self.factory_queue.append(instances)

        
