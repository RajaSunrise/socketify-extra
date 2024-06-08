from .uws import ffi, lib
from .background import (
    OpCode, SendStatus, 
    uws_req_for_each_topic_handler,
    uws_ws_cork_handler,
)

import inspect
import logging

class WebSocket:
    def __init__(self, websocket, app):
        self.ws = websocket
        self._ptr = ffi.new_handle(self)
        self.app = app
        self._cork_handler = None
        self._for_each_topic_handler = None
        self.socket_data_id = None
        self.socket_data = None
        self.got_socket_data = False

    def clone(self):
        # clone and preserve this websocket in another instance
        return WebSocket(self.ws, self.app)

    def trigger_for_each_topic_handler(self, topic):
        if hasattr(self, "_for_each_topic_handler") and hasattr(
            self._for_each_topic_handler, "__call__"
        ):
            try:
                if inspect.iscoroutinefunction(self._for_each_topic_handler):
                    raise RuntimeError(
                        "WebSocket.for_each_topic_handler must be synchronous"
                    )
                self._for_each_topic_handler(topic)
            except Exception as err:
                logging.error("Error on for each topic handler %s" % str(err))

    # uuid for socket data, used to free data after socket closes
    def get_user_data_uuid(self):
        try:
            if self.got_socket_data:
                return self.socket_data_id
            user_data = lib.uws_ws_get_user_data(self.app.SSL, self.ws)
            if user_data == ffi.NULL:
                return None
            (data, socket_data_id) = ffi.from_handle(user_data)
            self.socket_data_id = socket_data_id
            self.socket_data = data
            self.got_socket_data = True
            return socket_data_id
        except Exception:
            return None

    def get_user_data(self):
        try:
            if self.got_socket_data:
                return self.socket_data
            user_data = lib.uws_ws_get_user_data(self.app.SSL, self.ws)
            if user_data == ffi.NULL:
                return None
            (data, socket_data_id) = ffi.from_handle(user_data)
            self.socket_data_id = socket_data_id
            self.socket_data = data
            self.got_socket_data = True
            return data
        except Exception:
            return None

    def get_buffered_amount(self):
        return int(lib.uws_ws_get_buffered_amount(self.app.SSL, self.ws))

    def subscribe(self, topic):
        try:
            if isinstance(topic, str):
                data = topic.encode("utf-8")
            elif isinstance(topic, bytes):
                data = topic
            else:
                return False

            return bool(lib.uws_ws_subscribe(self.app.SSL, self.ws, data, len(data)))
        except Exception:
            return False

    def unsubscribe(self, topic):
        try:
            if isinstance(topic, str):
                data = topic.encode("utf-8")
            elif isinstance(topic, bytes):
                data = topic
            else:
                return False

            return bool(lib.uws_ws_unsubscribe(self.app.SSL, self.ws, data, len(data)))
        except Exception:
            return False

    def is_subscribed(self, topic):
        try:
            if isinstance(topic, str):
                data = topic.encode("utf-8")
            elif isinstance(topic, bytes):
                data = topic
            else:
                return False

            return bool(
                lib.uws_ws_is_subscribed(self.app.SSL, self.ws, data, len(data))
            )
        except Exception:
            return False

    def publish(self, topic, message, opcode=OpCode.BINARY, compress=False):
        # publish in app just send to everyone and default uws_ws_publish ignores the current connection
        # so we use the same publish in app to keep the same behavior
        return self.app.publish(topic, message, opcode, compress)
        

    def get_topics(self):
        topics = []

        def copy_topics(topic):
            topics.append(topic)

        self.for_each_topic(copy_topics)
        return topics

    def for_each_topic(self, handler):
        self._for_each_topic_handler = handler
        lib.uws_ws_iterate_topics(
            self.app.SSL, self.ws, uws_req_for_each_topic_handler, self._ptr
        )

    def get_remote_address_bytes(self):
        buffer = ffi.new("char**")
        length = lib.uws_ws_get_remote_address(self.app.SSL, self.ws, buffer)
        buffer_address = ffi.addressof(buffer, 0)[0]
        if buffer_address == ffi.NULL:
            return None
        try:
            return ffi.unpack(buffer_address, length)
        except Exception:  # invalid
            return None

    def get_remote_address(self):
        buffer = ffi.new("char**")
        length = lib.uws_ws_get_remote_address_as_text(self.app.SSL, self.ws, buffer)
        buffer_address = ffi.addressof(buffer, 0)[0]
        if buffer_address == ffi.NULL:
            return None
        try:
            return ffi.unpack(buffer_address, length).decode("utf-8")
        except Exception:  # invalid utf-8
            return None

    def send_fragment(self, message, compress=False):
        self.app.loop.is_idle = False
        try:
            if isinstance(message, str):
                data = message.encode("utf-8")
            elif isinstance(message, bytes):
                data = message
            elif message is None:
                lib.uws_ws_send_fragment(self.app.SSL, self.ws, b"", 0, compress)
                return self
            else:
                data = self.app._json_serializer.dumps(message).encode("utf-8")

            return SendStatus(
                lib.uws_ws_send_fragment(
                    self.app.SSL, self.ws, data, len(data), compress
                )
            )
        except Exception:
            return None

    def send_last_fragment(self, message, compress=False):
        self.app.loop.is_idle = False
        try:
            if isinstance(message, str):
                data = message.encode("utf-8")
            elif isinstance(message, bytes):
                data = message
            elif message is None:
                lib.uws_ws_send_last_fragment(self.app.SSL, self.ws, b"", 0, compress)
                return self
            else:
                data = self.app._json_serializer.dumps(message).encode("utf-8")

            return SendStatus(
                lib.uws_ws_send_last_fragment(
                    self.app.SSL, self.ws, data, len(data), compress
                )
            )
        except Exception:
            return None

    def send_first_fragment(self, message, opcode=OpCode.BINARY, compress=False):
        self.app.loop.is_idle = False
        try:
            if isinstance(message, str):
                data = message.encode("utf-8")
            elif isinstance(message, bytes):
                data = message
            elif message is None:
                lib.uws_ws_send_first_fragment_with_opcode(
                    self.app.SSL, self.ws, b"", 0, int(opcode), compress
                )
                return self
            else:
                data = self.app._json_serializer.dumps(message).encode("utf-8")

            return SendStatus(
                lib.uws_ws_send_first_fragment_with_opcode(
                    self.app.SSL, self.ws, data, len(data), int(opcode), compress
                )
            )
        except Exception:
            return None

    def cork_send(self, message, opcode=OpCode.BINARY, compress=False, fin=True):
        self.cork(lambda ws: ws.send(message, opcode, compress, fin))
        return self

    def send(self, message, opcode=OpCode.BINARY, compress=False, fin=True):
        self.app.loop.is_idle = False
        try:
            if isinstance(message, str):
                data = message.encode("utf-8")
            elif isinstance(message, bytes):
                data = message
            elif message is None:
                lib.uws_ws_send_with_options(
                    self.app.SSL, self.ws, b"", 0, int(opcode), compress, fin
                )
                return self
            else:
                data = self.app._json_serializer.dumps(message).encode("utf-8")

            return SendStatus(
                lib.uws_ws_send_with_options(
                    self.app.SSL, self.ws, data, len(data), int(opcode), compress, fin
                )
            )
        except Exception:
            return None

    def cork_end(self, code=0, message=None):
        self.cork(lambda ws: ws.end(message, code, message))
        return self

    def end(self, code=0, message=None):
        self.app.loop.is_idle = False
        try:
            if not isinstance(code, int):
                raise RuntimeError("code must be an int")
            if isinstance(message, str):
                data = message.encode("utf-8")
            elif isinstance(message, bytes):
                data = message
            elif message is None:
                lib.uws_ws_end(self.app.SSL, self.ws, b"", 0)
                return self
            else:
                data = self.app._json_serializer.dumps(message).encode("utf-8")

            lib.uws_ws_end(self.app.SSL, self.ws, code, data, len(data))
        finally:
            return self

    def close(self):
        lib.uws_ws_close(self.app.SSL, self.ws)
        return self

    def cork(self, callback):
        self._cork_handler = callback
        lib.uws_ws_cork(self.app.SSL, self.ws, uws_ws_cork_handler, self._ptr)

    def __del__(self):
        self.ws = ffi.NULL
        self._ptr = ffi.NULL



class WebSocketFactory:
    def __init__(self, app, max_size):
        self.factory_queue = []
        self.app = app
        self.max_size = max_size
        self.dispose = self._dispose
        self.populate = self._populate
        self.get = self._get

    def update_extensions(self):
        self.populate = self._populate_with_extension
        self.get = self._get_with_extension
        if len(self.app._ws_extension.properties) > 0:
            self.dispose = self._dispose_with_extension

    def _populate_with_extension(self):
        self.factory_queue = []
        for _ in range(0, self.max_size):
            websocket = WebSocket(None, self.app)
            # bind methods to websocket
            self.app._ws_extension.set_properties(websocket)
            # set default value in properties
            self.app._ws_extension.bind_methods(websocket)
            self.factory_queue.append((websocket, True))

    def _populate(self):
        self.factory_queue = []
        for _ in range(0, self.max_size):
            websocket = WebSocket(None, self.app)
            self.factory_queue.append((websocket, True))

    def _get_with_extension(self, app, ws):
        if len(self.factory_queue) == 0:
            websocket = WebSocket(ws, app)
            # bind methods to websocket
            self.app._ws_extension.set_properties(websocket)
            # set default value in properties
            self.app._ws_extension.bind_methods(websocket)
            return websocket, False

        instances = self.factory_queue.pop()
        (websocket, _) = instances
        websocket.ws = ws
        return instances

    def _get(self, app, ws):
        if len(self.factory_queue) == 0:
            response = WebSocket(ws, app)
            return response, False

        instances = self.factory_queue.pop()
        (websocket, _) = instances
        websocket.ws = ws
        return instances

    def _dispose_with_extension(self, instances):
        (websocket, _) = instances
        # dispose ws
        websocket.ws = None
        websocket._cork_handler = None
        websocket._for_each_topic_handler = None
        websocket.socket_data_id = None
        websocket.socket_data = None
        websocket.got_socket_data = False
        # set default value in properties
        self.app._ws_extension.set_properties(websocket)
        self.factory_queue.append(instances)

    def _dispose(self, instances):
        (websocket, _) = instances
        # dispose ws
        websocket.ws = None
        websocket._cork_handler = None
        websocket._for_each_topic_handler = None
        websocket.socket_data_id = None
        websocket.socket_data = None
        websocket.got_socket_data = False
        self.factory_queue.append(instances)


class WSBehaviorHandlers:
    def __init__(self):
        self.upgrade = None
        self.open = None
        self.message = None
        self.drain = None
        self.ping = None
        self.pong = None
        self.close = None
        self.subscription = None