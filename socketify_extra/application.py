import inspect
import json
import signal
import logging
import traceback

from .uws import ffi, lib
from .loop import Loop
from .helpers import static_route
from .helpers import DecoratorRouter
from .response import RequestResponseFactory
from .websocket import WebSocketFactory, WSBehaviorHandlers
from .background import OpCode


from .uwebsocket_cffi import (
    uws_generic_factory_method_handler, uws_generic_method_handler_with_extension,
    uws_generic_method_handler, uws_missing_server_name,
    uws_websocket_factory_upgrade_handler, uws_websocket_factory_open_handler,
    uws_websocket_upgrade_handler_with_extension, uws_websocket_upgrade_handler,
    uws_websocket_factory_message_handler, uws_websocket_ping_handler_with_extension,
    uws_websocket_open_handler_with_extension, uws_websocket_ping_handler,
    uws_websocket_message_handler_with_extension, uws_websocket_drain_handler,
    uws_websocket_message_handler, uws_websocket_pong_handler_with_extension,
    uws_websocket_pong_handler, uws_websocket_factory_ping_handler,
    uws_websocket_open_handler, uws_websocket_drain_handler_with_extension,
    uws_websocket_factory_drain_handler, uws_websocket_factory_pong_handler,
    uws_websocket_close_handler, uws_websocket_factory_subscription_handler,
    uws_websocket_factory_close_handler, uws_websocket_close_handler_with_extension,
    uws_websocket_subscription_handler_with_extension, uws_websocket_subscription_handler,
    uws_generic_listen_handler, uws_generic_listen_domain_handler 

)

class App:
    def __init__(
        self,
        options=None,
        request_response_factory_max_items=0,
        websocket_factory_max_items=0,
        task_factory_max_items=100_000,
        lifespan=True,
    ):

        socket_options_ptr = ffi.new("struct us_socket_context_options_t *")
        socket_options = socket_options_ptr[0]
        self._options = options
        self._template = None
        self.lifespan = lifespan
        # keep socket data alive for CFFI
        self._socket_refs = {}
        self._native_options = []
        if options is not None:
            self.is_ssl = True
            self.SSL = ffi.cast("int", 1)

            key_filename = (
                ffi.NULL
                if options.key_file_name is None
                else ffi.new("char[]", options.key_file_name.encode("utf-8"))
            )
            self._native_options.append(key_filename)
            socket_options.key_file_name = key_filename

            cert_file_name = (
                ffi.NULL
                if options.cert_file_name is None
                else ffi.new("char[]", options.cert_file_name.encode("utf-8"))
            )

            self._native_options.append(cert_file_name)
            socket_options.cert_file_name = cert_file_name

            passphrase = (
                ffi.NULL
                if options.passphrase is None
                else ffi.new("char[]", options.passphrase.encode("utf-8"))
            )

            self._native_options.append(passphrase)
            socket_options.passphrase = passphrase

            dh_params_file_name = (
                ffi.NULL
                if options.dh_params_file_name is None
                else ffi.new("char[]", options.dh_params_file_name.encode("utf-8"))
            )

            self._native_options.append(dh_params_file_name)
            socket_options.dh_params_file_name = dh_params_file_name

            ca_file_name = (
                ffi.NULL
                if options.ca_file_name is None
                else ffi.new("char[]", options.ca_file_name.encode("utf-8"))
            )

            self._native_options.append(ca_file_name)
            socket_options.ca_file_name = ca_file_name

            ssl_ciphers = (
                ffi.NULL
                if options.ssl_ciphers is None
                else ffi.new("char[]", options.ssl_ciphers.encode("utf-8"))
            )

            self._native_options.append(ssl_ciphers)
            socket_options.ssl_ciphers = ssl_ciphers

            socket_options.ssl_prefer_low_memory_usage = ffi.cast(
                "int", options.ssl_prefer_low_memory_usage
            )

        else:
            self.is_ssl = False
            self.SSL = ffi.cast("int", 0)

        self.loop = Loop(
            lambda loop, context, response: self.trigger_error(context, response, None),
            task_factory_max_items,
        )
        self.run_async = self.loop.run_async
        
        lib.uws_get_loop_with_native(self.loop.get_native_loop())
        self.app = lib.uws_create_app(self.SSL, socket_options)
        self._ptr = ffi.new_handle(self)
        if bool(lib.uws_constructor_failed(self.SSL, self.app)):
            raise RuntimeError("Failed to create connection")

        self.handlers = []
        self.error_handler = None
        self._missing_server_handler = None

        if (
            request_response_factory_max_items
            and request_response_factory_max_items >= 1
        ):
            self._factory = RequestResponseFactory(
                self, request_response_factory_max_items
            )
        else:
            self._factory = None

        if websocket_factory_max_items and websocket_factory_max_items >= 1:
            self._ws_factory = WebSocketFactory(self, websocket_factory_max_items)
        else:
            self._ws_factory = None
        self._json_serializer = json
        self._request_extension = None
        self._response_extension = None
        self._ws_extension = None
        self._on_start_handler = None
        self._on_shutdown_handler = None

    def on_start(self, method: callable):
        self._on_start_handler = method
        return method

    def on_shutdown(self, method: callable):
        self._on_shutdown_handler = method
        return method

    def router(self, prefix: str = "", *middlewares):
        return DecoratorRouter(self, prefix, middlewares)

    def register(self, extension):
        if self._request_extension is None:
            self._request_extension = AppExtension()
        if self._response_extension is None:
            self._response_extension = AppExtension()
        if self._ws_extension is None:
            self._ws_extension = AppExtension()

        extension(self._request_extension, self._response_extension, self._ws_extension)

        if self._factory is not None and (
            not self._request_extension.empty or not self._response_extension.empty
        ):
            self._factory.update_extensions()
        if self._ws_factory is not None and not self._ws_extension.empty:
            self._ws_factory.update_extensions()

    def template(self, template_engine):
        self._template = template_engine

    def json_serializer(self, json_serializer):
        self._json_serializer = json_serializer

    def static(self, route, directory):
        static_route(self, route, directory)
        return self

    def get(self, path, handler):
        user_data = ffi.new_handle((handler, self))
        self.handlers.append(user_data)  # Keep alive handler
        if self._factory:
            handler = uws_generic_factory_method_handler
        elif self._response_extension and (
            not self._response_extension.empty or not self._request_extension.empty
        ):
            handler = uws_generic_method_handler_with_extension
        else:
            handler = uws_generic_method_handler

        lib.uws_app_get(
            self.SSL,
            self.app,
            path.encode("utf-8"),
            handler,
            user_data,
        )
        return self

    def post(self, path, handler):
        user_data = ffi.new_handle((handler, self))
        self.handlers.append(user_data)  # Keep alive handler
        if self._factory:
            handler = uws_generic_factory_method_handler
        elif self._response_extension and (
            not self._response_extension.empty or not self._request_extension.empty
        ):
            handler = uws_generic_method_handler_with_extension
        else:
            handler = uws_generic_method_handler

        lib.uws_app_post(
            self.SSL,
            self.app,
            path.encode("utf-8"),
            handler,
            user_data,
        )
        return self

    def options(self, path, handler):
        user_data = ffi.new_handle((handler, self))
        self.handlers.append(user_data)  # Keep alive handler
        if self._factory:
            handler = uws_generic_factory_method_handler
        elif self._response_extension and (
            not self._response_extension.empty or not self._request_extension.empty
        ):
            handler = uws_generic_method_handler_with_extension
        else:
            handler = uws_generic_method_handler

        lib.uws_app_options(
            self.SSL,
            self.app,
            path.encode("utf-8"),
            handler,
            user_data,
        )
        return self

    def delete(self, path, handler):
        user_data = ffi.new_handle((handler, self))
        self.handlers.append(user_data)  # Keep alive handler
        if self._factory:
            handler = uws_generic_factory_method_handler
        elif self._response_extension and (
            not self._response_extension.empty or not self._request_extension.empty
        ):
            handler = uws_generic_method_handler_with_extension
        else:
            handler = uws_generic_method_handler

        lib.uws_app_delete(
            self.SSL,
            self.app,
            path.encode("utf-8"),
            handler,
            user_data,
        )
        return self

    def patch(self, path, handler):
        user_data = ffi.new_handle((handler, self))
        self.handlers.append(user_data)  # Keep alive handler
        if self._factory:
            handler = uws_generic_factory_method_handler
        elif self._response_extension and (
            not self._response_extension.empty or not self._request_extension.empty
        ):
            handler = uws_generic_method_handler_with_extension
        else:
            handler = uws_generic_method_handler

        lib.uws_app_patch(
            self.SSL,
            self.app,
            path.encode("utf-8"),
            handler,
            user_data,
        )
        return self

    def put(self, path, handler):
        user_data = ffi.new_handle((handler, self))
        self.handlers.append(user_data)  # Keep alive handler
        if self._factory:
            handler = uws_generic_factory_method_handler
        elif self._response_extension and (
            not self._response_extension.empty or not self._request_extension.empty
        ):
            handler = uws_generic_method_handler_with_extension
        else:
            handler = uws_generic_method_handler

        lib.uws_app_put(
            self.SSL,
            self.app,
            path.encode("utf-8"),
            handler,
            user_data,
        )
        return self

    def head(self, path, handler):
        user_data = ffi.new_handle((handler, self))
        self.handlers.append(user_data)  # Keep alive handler
        if self._factory:
            handler = uws_generic_factory_method_handler
        elif self._response_extension and (
            not self._response_extension.empty or not self._request_extension.empty
        ):
            handler = uws_generic_method_handler_with_extension
        else:
            handler = uws_generic_method_handler

        lib.uws_app_head(
            self.SSL,
            self.app,
            path.encode("utf-8"),
            handler,
            user_data,
        )
        return self

    def connect(self, path, handler):
        user_data = ffi.new_handle((handler, self))
        self.handlers.append(user_data)  # Keep alive handler
        if self._factory:
            handler = uws_generic_factory_method_handler
        elif self._response_extension and (
            not self._response_extension.empty or not self._request_extension.empty
        ):
            handler = uws_generic_method_handler_with_extension
        else:
            handler = uws_generic_method_handler

        lib.uws_app_connect(
            self.SSL,
            self.app,
            path.encode("utf-8"),
            handler,
            user_data,
        )
        return self

    def trace(self, path, handler):
        user_data = ffi.new_handle((handler, self))
        self.handlers.append(user_data)  # Keep alive handler
        if self._factory:
            handler = uws_generic_factory_method_handler
        elif self._response_extension and (
            not self._response_extension.empty or not self._request_extension.empty
        ):
            handler = uws_generic_method_handler_with_extension
        else:
            handler = uws_generic_method_handler

        lib.uws_app_trace(
            self.SSL,
            self.app,
            path.encode("utf-8"),
            handler,
            user_data,
        )
        return self

    def any(self, path, handler):
        user_data = ffi.new_handle((handler, self))
        self.handlers.append(user_data)  # Keep alive handler
        if self._factory:
            handler = uws_generic_factory_method_handler
        elif self._response_extension and (
            not self._response_extension.empty or not self._request_extension.empty
        ):
            handler = uws_generic_method_handler_with_extension
        else:
            handler = uws_generic_method_handler

        lib.uws_app_any(
            self.SSL,
            self.app,
            path.encode("utf-8"),
            handler,
            user_data,
        )
        return self

    def get_native_handle(self):
        return lib.uws_get_native_handle(self.SSL, self.app)

    def num_subscribers(self, topic):
        if isinstance(topic, str):
            topic_data = topic.encode("utf-8")
        elif isinstance(topic, bytes):
            topic_data = topic
        else:
            raise RuntimeError("topic need to be an String or Bytes")
        return int(
            lib.uws_num_subscribers(self.SSL, self.app, topic_data, len(topic_data))
        )

    def publish(self, topic, message, opcode=OpCode.BINARY, compress=False):
        self.loop.is_idle = False

        if isinstance(topic, str):
            topic_data = topic.encode("utf-8")
        elif isinstance(topic, bytes):
            topic_data = topic
        else:
            return False

        if isinstance(message, str):
            message_data = message.encode("utf-8")
        elif isinstance(message, bytes):
            message_data = message
        elif message is None:
            message_data = b""
        else:
            message_data = self._json_serializer.dumps(message).encode("utf-8")

        return bool(
            lib.uws_publish(
                self.SSL,
                self.app,
                topic_data,
                len(topic_data),
                message_data,
                len(message_data),
                int(opcode),
                bool(compress),
            )
        )

    def remove_server_name(self, hostname):
        if isinstance(hostname, str):
            hostname_data = hostname.encode("utf-8")
        elif isinstance(hostname, bytes):
            hostname_data = hostname
        else:
            raise RuntimeError("hostname need to be an String or Bytes")

        lib.uws_remove_server_name(
            self.SSL, self.app, hostname_data, len(hostname_data)
        )
        return self

    def add_server_name(self, hostname, options=None):
        if isinstance(hostname, str):
            hostname_data = hostname.encode("utf-8")
        elif isinstance(hostname, bytes):
            hostname_data = hostname
        else:
            raise RuntimeError("hostname need to be an String or Bytes")

        if options is None:
            lib.uws_add_server_name(
                self.SSL, self.app, hostname_data, len(hostname_data)
            )
        else:
            socket_options_ptr = ffi.new("struct us_socket_context_options_t *")
            socket_options = socket_options_ptr[0]
            socket_options.key_file_name = (
                ffi.NULL
                if options.key_file_name is None
                else ffi.new("char[]", options.key_file_name.encode("utf-8"))
            )
            socket_options.key_file_name = (
                ffi.NULL
                if options.key_file_name is None
                else ffi.new("char[]", options.key_file_name.encode("utf-8"))
            )
            socket_options.cert_file_name = (
                ffi.NULL
                if options.cert_file_name is None
                else ffi.new("char[]", options.cert_file_name.encode("utf-8"))
            )
            socket_options.passphrase = (
                ffi.NULL
                if options.passphrase is None
                else ffi.new("char[]", options.passphrase.encode("utf-8"))
            )
            socket_options.dh_params_file_name = (
                ffi.NULL
                if options.dh_params_file_name is None
                else ffi.new("char[]", options.dh_params_file_name.encode("utf-8"))
            )
            socket_options.ca_file_name = (
                ffi.NULL
                if options.ca_file_name is None
                else ffi.new("char[]", options.ca_file_name.encode("utf-8"))
            )
            socket_options.ssl_ciphers = (
                ffi.NULL
                if options.ssl_ciphers is None
                else ffi.new("char[]", options.ssl_ciphers.encode("utf-8"))
            )
            socket_options.ssl_prefer_low_memory_usage = ffi.cast(
                "int", options.ssl_prefer_low_memory_usage
            )
            lib.uws_add_server_name_with_options(
                self.SSL, self.app, hostname_data, len(hostname_data), socket_options
            )
        return self

    def missing_server_name(self, handler):
        self._missing_server_handler = handler
        lib.uws_missing_server_name(
            self.SSL, self.app, uws_missing_server_name, self._ptr
        )

    def ws(self, path, behavior):
        native_options = ffi.new("uws_socket_behavior_t *")
        native_behavior = native_options[0]

        max_payload_length = None
        idle_timeout = None
        max_backpressure = None
        close_on_backpressure_limit = None
        reset_idle_timeout_on_send = None
        send_pings_automatically = None
        max_lifetime = None
        compression = None
        upgrade_handler = None
        open_handler = None
        message_handler = None
        drain_handler = None
        ping_handler = None
        pong_handler = None
        close_handler = None
        subscription_handler = None

        if behavior is None:
            raise RuntimeError("behavior must be an dict or WSBehavior")
        elif isinstance(behavior, dict):
            max_payload_length = behavior.get("max_payload_length", 16 * 1024)
            idle_timeout = behavior.get("idle_timeout", 60 * 2)
            max_backpressure = behavior.get("max_backpressure", 64 * 1024)
            close_on_backpressure_limit = behavior.get(
                "close_on_backpressure_limit", False
            )
            reset_idle_timeout_on_send = behavior.get(
                "reset_idle_timeout_on_send", False
            )
            send_pings_automatically = behavior.get("send_pings_automatically", False)
            max_lifetime = behavior.get("max_lifetime", 0)
            compression = behavior.get("compression", 0)
            upgrade_handler = behavior.get("upgrade", None)
            open_handler = behavior.get("open", None)
            message_handler = behavior.get("message", None)
            drain_handler = behavior.get("drain", None)
            ping_handler = behavior.get("ping", None)
            pong_handler = behavior.get("pong", None)
            close_handler = behavior.get("close", None)
            subscription_handler = behavior.get("subscription", None)

        native_behavior.maxPayloadLength = ffi.cast(
            "unsigned int",
            max_payload_length if isinstance(max_payload_length, int) else 16 * 1024,
        )
        native_behavior.idleTimeout = ffi.cast(
            "unsigned short",
            idle_timeout if isinstance(idle_timeout, int) else 16 * 1024,
        )
        native_behavior.maxBackpressure = ffi.cast(
            "unsigned int",
            max_backpressure if isinstance(max_backpressure, int) else 64 * 1024,
        )
        native_behavior.compression = ffi.cast(
            "uws_compress_options_t", compression if isinstance(compression, int) else 0
        )
        native_behavior.maxLifetime = ffi.cast(
            "unsigned short", max_lifetime if isinstance(max_lifetime, int) else 0
        )
        native_behavior.closeOnBackpressureLimit = ffi.cast(
            "int", 1 if close_on_backpressure_limit else 0
        )
        native_behavior.resetIdleTimeoutOnSend = ffi.cast(
            "int", 1 if reset_idle_timeout_on_send else 0
        )
        native_behavior.sendPingsAutomatically = ffi.cast(
            "int", 1 if send_pings_automatically else 0
        )

        handlers = WSBehaviorHandlers()
        if upgrade_handler:
            handlers.upgrade = upgrade_handler

            if self._factory:
                native_behavior.upgrade = uws_websocket_factory_upgrade_handler
            elif self._response_extension and (
                not self._response_extension.empty or not self._request_extension.empty
            ):
                native_behavior.upgrade = uws_websocket_upgrade_handler_with_extension
            else:
                native_behavior.upgrade = uws_websocket_upgrade_handler

        else:
            native_behavior.upgrade = ffi.NULL

        if open_handler:
            handlers.open = open_handler

            if self._factory:
                native_behavior.open = uws_websocket_factory_open_handler
            elif self._ws_extension and not self._ws_extension.empty:
                native_behavior.open = uws_websocket_open_handler_with_extension
            else:
                native_behavior.open = uws_websocket_open_handler

        else:
            native_behavior.open = ffi.NULL

        if message_handler:
            handlers.message = message_handler

            if self._factory:
                native_behavior.message = uws_websocket_factory_message_handler
            elif self._ws_extension and not self._ws_extension.empty:
                native_behavior.message = uws_websocket_message_handler_with_extension
            else:
                native_behavior.message = uws_websocket_message_handler

        else:
            native_behavior.message = ffi.NULL

        if drain_handler:
            handlers.drain = drain_handler

            if self._factory:
                native_behavior.drain = uws_websocket_factory_drain_handler
            elif self._ws_extension and not self._ws_extension.empty:
                native_behavior.drain = uws_websocket_drain_handler_with_extension
            else:
                native_behavior.drain = uws_websocket_drain_handler

            native_behavior.drain = ffi.NULL

        if ping_handler:
            handlers.ping = ping_handler

            if self._factory:
                native_behavior.ping = uws_websocket_factory_ping_handler
            elif self._ws_extension and not self._ws_extension.empty:
                native_behavior.ping = uws_websocket_ping_handler_with_extension
            else:
                native_behavior.ping = uws_websocket_ping_handler

        else:
            native_behavior.ping = ffi.NULL

        if pong_handler:
            handlers.pong = pong_handler

            if self._factory:
                native_behavior.pong = uws_websocket_factory_pong_handler
            elif self._ws_extension and not self._ws_extension.empty:
                native_behavior.pong = uws_websocket_pong_handler_with_extension
            else:
                native_behavior.pong = uws_websocket_pong_handler

        else:
            native_behavior.pong = ffi.NULL

        if close_handler:
            handlers.close = close_handler

            if self._factory:
                native_behavior.close = uws_websocket_factory_close_handler
            elif self._ws_extension and not self._ws_extension.empty:
                native_behavior.close = uws_websocket_close_handler_with_extension
            else:
                native_behavior.close = uws_websocket_close_handler

        else:  # always keep an close
            native_behavior.close = uws_websocket_close_handler

        if subscription_handler:
            handlers.subscription = subscription_handler

            if self._factory:
                native_behavior.subscription = (
                    uws_websocket_factory_subscription_handler
                )
            elif self._ws_extension and not self._ws_extension.empty:
                native_behavior.subscription = (
                    uws_websocket_subscription_handler_with_extension
                )
            else:
                native_behavior.subscription = uws_websocket_subscription_handler

            native_behavior.subscription = (
                uws_websocket_factory_subscription_handler
                if self._ws_factory
                else uws_websocket_subscription_handler
            )
        else:  # always keep an close
            native_behavior.subscription = ffi.NULL

        user_data = ffi.new_handle((handlers, self))
        self.handlers.append(user_data)  # Keep alive handlers
        lib.uws_ws(self.SSL, self.app, path.encode("utf-8"), native_behavior, user_data)
        return self

    def listen(self, port_or_options=None, handler=None):
        if self.lifespan:

            async def task_wrapper(task):
                try:
                    if inspect.iscoroutinefunction(task):
                        await task()
                    else:
                        task()
                except Exception as error:
                    try:
                        self.trigger_error(error, None, None)
                    finally:
                        return None

            # start lifespan
            if self._on_start_handler:
                self.loop.run_until_complete(task_wrapper(self._on_start_handler))

        # actual listen to server
        self._listen_handler = handler
        if port_or_options is None:
            lib.uws_app_listen(
                self.SSL,
                self.app,
                ffi.cast("int", 0),
                uws_generic_listen_handler,
                self._ptr,
            )
        elif isinstance(port_or_options, int):
            lib.uws_app_listen(
                self.SSL,
                self.app,
                ffi.cast("int", port_or_options),
                uws_generic_listen_handler,
                self._ptr,
            )
        elif isinstance(port_or_options, dict):
            native_options = ffi.new("uws_app_listen_config_t *")
            options = native_options[0]
            port = port_or_options.get("port", 0)
            options = port_or_options.get("options", 0)
            host = port_or_options.get("host", "0.0.0.0")
            options.port = (
                ffi.cast("int", port, 0)
                if isinstance(port, int)
                else ffi.cast("int", 0)
            )
            options.host = (
                ffi.new("char[]", host.encode("utf-8"))
                if isinstance(host, str)
                else ffi.NULL
            )
            options.options = (
                ffi.cast("int", port)
                if isinstance(options, int)
                else ffi.cast("int", 0)
            )
            self.native_options_listen = native_options  # Keep alive native_options
            lib.uws_app_listen_with_config(
                self.SSL, self.app, options, uws_generic_listen_handler, self._ptr
            )
        else:
            if port_or_options.domain:
                domain = port_or_options.domain.encode("utf8")
                lib.uws_app_listen_domain_with_options(
                    self.SSL,
                    self.app,
                    domain,
                    len(domain),
                    int(port_or_options.options),
                    uws_generic_listen_domain_handler,
                    self._ptr,
                )
            else:
                native_options = ffi.new("uws_app_listen_config_t *")
                options = native_options[0]
                options.port = ffi.cast("int", port_or_options.port)
                options.host = (
                    ffi.NULL
                    if port_or_options.host is None
                    else ffi.new("char[]", port_or_options.host.encode("utf-8"))
                )
                options.options = ffi.cast("int", port_or_options.options)
                self.native_options_listen = native_options  # Keep alive native_options
                lib.uws_app_listen_with_config(
                    self.SSL, self.app, options, uws_generic_listen_handler, self._ptr
                )

        return self


    def run(self):
        # populate factories
        if self._factory is not None:
            self._factory.populate()
        if self._ws_factory is not None:
            self._ws_factory.populate()
    
        def signal_handler(sig, frame):
            self.close()
            exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        self.loop.run()
        if self.lifespan:

            async def task_wrapper(task):
                try:
                    if inspect.iscoroutinefunction(task):
                        await task()
                    else:
                        task()
                except Exception as error:
                    try:
                        self.trigger_error(error, None, None)
                    finally:
                        return None

            # shutdown lifespan
            if self._on_shutdown_handler:
                self.loop.run_until_complete(task_wrapper(self._on_shutdown_handler))

        return self

    def close(self):
        if hasattr(self, "socket"):
            if self.socket != ffi.NULL:
                lib.us_listen_socket_close(self.SSL, self.socket)
                self.socket = ffi.NULL
        self.loop.stop()
        return self

    def on_error(self, handler):
        self.set_error_handler(handler)
        return handler

    def set_error_handler(self, handler):
        if hasattr(handler, "__call__"):
            self.error_handler = handler
        else:
            self.error_handler = None

    def trigger_error(self, error, response, request):
        if self.error_handler is None:
            try:
                logging.error(
                    "Uncaught Exception: %s" % traceback.format_exc()
                )  # just log in console the error to call attention
                response.write_status(500).end("Internal Error")
            finally:
                return
        else:
            try:
                if inspect.iscoroutinefunction(self.error_handler):
                    self.run_async(
                        self.error_handler(error, response, request), response
                    )
                else:
                    self.error_handler(error, response, request)
            except Exception as error:
                try:
                    # Error handler got an error :D
                    logging.error(
                        "Uncaught Exception: %s" % traceback.format_exc()
                    )  # just log in console the error to call attention
                    response.write_status(500).end("Internal Error")
                finally:
                    pass

    def dispose(self):
        if self.app:  # only destroy if exists
            self.close()
            lib.uws_app_destroy(self.SSL, self.app)
            self.app = None

        if self.loop:
            self.loop.dispose()
            self.loop = None

    def __del__(self):
        try:
            if self.app:  # only destroy if exists
                self.close()
                lib.uws_app_destroy(self.SSL, self.app)
            if self.loop:
                self.loop.dispose()
                self.loop = None
        except Exception:
            pass


class AppExtension:
    def __init__(self):
        self.properties = []
        self.methods = []
        self.empty = True

    def bind_methods(self, instance: any):
        for (name, method) in self.methods:
            
            bound_method = method.__get__(instance, instance.__class__)
            setattr(instance, name, bound_method)

    def set_properties(self, instance: any):
        for (name, property) in self.properties:
            setattr(instance, name, property)

    def method(self, method: callable):
        self.empty = False
        self.methods.append((method.__name__, method))
        return method

    def property(self, name: str, default_value: any = None):
        self.empty = False
        self.properties.append((name, default_value))