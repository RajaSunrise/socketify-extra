from .uws import ffi, lib
from .background import uws_req_for_each_header_handler

from urllib.parse import parse_qs
from http import cookies

import logging
import inspect


class AppRequest:
    def __init__(self, request, app):
        self.req = request
        self.app = app
        self.read_jar = None
        self.jar_parsed = False
        self._for_each_header_handler = None
        self._ptr = ffi.new_handle(self)
        self._headers = None
        self._params = None
        self._query = None
        self._url = None
        self._full_url = None
        self._method = None

    def get_cookie(self, name):
        if self.read_jar is None:
            if self.jar_parsed:
                return None

            if self._headers:
                raw_cookies = self._headers.get("cookie", None)
            else:
                raw_cookies = self.get_header("cookie")

            if raw_cookies:
                self.jar_parsed = True
                self.read_jar = cookies.SimpleCookie(raw_cookies)
            else:
                self.jar_parsed = True
                return None
        try:
            return self.read_jar[name].value
        except Exception:
            return None

    def get_url(self):
        if self._url:
            return self._url
        buffer = ffi.new("char**")
        length = lib.uws_req_get_url(self.req, buffer)
        buffer_address = ffi.addressof(buffer, 0)[0]
        if buffer_address == ffi.NULL:
            return None
        try:
            self._url = ffi.unpack(buffer_address, length).decode("utf-8")
            return self._url
        except Exception:  # invalid utf-8
            return None

    def get_full_url(self):
        if self._full_url:
            return self._full_url
        buffer = ffi.new("char**")
        length = lib.uws_req_get_full_url(self.req, buffer)
        buffer_address = ffi.addressof(buffer, 0)[0]
        if buffer_address == ffi.NULL:
            return None
        try:
            self._full_url = ffi.unpack(buffer_address, length).decode("utf-8")
            return self._full_url
        except Exception:  # invalid utf-8
            return None

    def get_method(self):
        if self._method:
            return self._method
        buffer = ffi.new("char**")
        # will use uws_req_get_case_sensitive_method until version v21 and switch back to uws_req_get_method for 0 impacts on behavior
        length = lib.uws_req_get_case_sensitive_method(self.req, buffer)
        buffer_address = ffi.addressof(buffer, 0)[0]
        if buffer_address == ffi.NULL:
            return None

        try:
            self._method = ffi.unpack(buffer_address, length).decode("utf-8")
            return self._method
        except Exception:  # invalid utf-8
            return None

    def for_each_header(self, handler):
        self._for_each_header_handler = handler
        lib.uws_req_for_each_header(
            self.req, uws_req_for_each_header_handler, self._ptr
        )

    def get_headers(self):
        if self._headers is not None:
            return self._headers

        self._headers = {}

        def copy_headers(key, value):
            self._headers[key] = value

        self.for_each_header(copy_headers)
        return self._headers

    def get_header(self, lower_case_header):
        if self._headers is not None:
            return self._headers.get(lower_case_header, None)

        if isinstance(lower_case_header, str):
            data = lower_case_header.encode("utf-8")
        elif isinstance(lower_case_header, bytes):
            data = lower_case_header
        else:
            data = self.app._json_serializer.dumps(lower_case_header).encode("utf-8")

        buffer = ffi.new("char**")
        length = lib.uws_req_get_header(self.req, data, len(data), buffer)
        buffer_address = ffi.addressof(buffer, 0)[0]
        if buffer_address == ffi.NULL:
            return None
        try:
            return ffi.unpack(buffer_address, length).decode("utf-8")
        except Exception:  # invalid utf-8
            return None

    def get_queries(self):
        try:
            if self._query:
                return self._query

            url = self.get_url()
            query = self.get_full_url()[len(url) :]
            if query.startswith("?"):
                query = query[1:]
            self._query = parse_qs(query, encoding="utf-8")
            return self._query
        except Exception:
            self._query = {}
            return None

    def get_query(self, key):
        if self._query:
            return self._query.get(key, None)
        buffer = ffi.new("char**")

        if isinstance(key, str):
            key_data = key.encode("utf-8")
        elif isinstance(key, bytes):
            key_data = key
        else:
            key_data = self.app._json_serializer.dumps(key).encode("utf-8")

        length = lib.uws_req_get_query(self.req, key_data, len(key_data), buffer)
        buffer_address = ffi.addressof(buffer, 0)[0]
        if buffer_address == ffi.NULL:
            return None
        try:
            return ffi.unpack(buffer_address, length).decode("utf-8")
        except Exception:  # invalid utf-8
            return None

    def get_parameters(self):
        if self._params:
            return self._params
        self._params = []
        i = 0
        while True:
            value = self.get_parameter(i)
            if value:
                self._params.append(value)
            else:
                break
            i = i + 1
        return self._params

    def get_parameter(self, index):
        if self._params:
            try:
                return self._params[index]
            except Exception:
                return None

        buffer = ffi.new("char**")
        length = lib.uws_req_get_parameter(
            self.req, ffi.cast("unsigned short", index), buffer
        )
        buffer_address = ffi.addressof(buffer, 0)[0]
        if buffer_address == ffi.NULL:
            return None
        try:
            return ffi.unpack(buffer_address, length).decode("utf-8")
        except Exception:  # invalid utf-8
            return None

    def preserve(self):
        # preserve queries, headers, parameters, method, url and full url
        self.get_queries()  # queries calls url and full_url so its preserved
        self.get_headers()
        self.get_parameters()
        self.get_method()
        return self

    def set_yield(self, has_yield):
        lib.uws_req_set_yield(self.req, 1 if has_yield else 0)

    def get_yield(self):
        return bool(lib.uws_req_get_yield(self.req))

    def is_ancient(self):
        return bool(lib.uws_req_is_ancient(self.req))

    def trigger_for_each_header_handler(self, key, value):
        if hasattr(self, "_for_each_header_handler") and hasattr(
            self._for_each_header_handler, "__call__"
        ):
            try:
                if inspect.iscoroutinefunction(self._for_each_header_handler):
                    raise RuntimeError(
                        "AppResponse.for_each_header_handler must be synchronous"
                    )
                self._for_each_header_handler(key, value)
            except Exception as err:
                logging.error("Error on data handler %s" % str(err))

        return self

    def __del__(self):
        self.req = ffi.NULL
        self._ptr = ffi.NULL

