from .uws import ffi, lib
from .websocket import WebSocket
from .background import OpCode
from .request import AppRequest
from .response import AppResponse
from .dataclasses import AppListenOptions


import logging
import inspect
import traceback


@ffi.callback("void(const char*, size_t, void*)")
def uws_missing_server_name(hostname, hostname_length, user_data):
    if user_data != ffi.NULL:
        try:
            app = ffi.from_handle(user_data)
            if hostname == ffi.NULL:
                data = None
            else:
                data = ffi.unpack(hostname, hostname_length).decode("utf-8")

            handler = app._missing_server_handler
            if inspect.iscoroutinefunction(handler):
                app.run_async(handler(data))
            else:
                handler(data)
        except Exception:
            logging.error(
                "Uncaught Exception:\n %s" % traceback.format_exc()
            )  # just log in console the error to call attention

@ffi.callback("void(uws_websocket_t*, void*)")
def uws_websocket_factory_drain_handler(ws, user_data):
    if user_data != ffi.NULL:
        handlers, app = ffi.from_handle(user_data)
        app.loop.is_idle = False
        instances = app._ws_factory.get(app, ws)
        ws, dispose = instances
        try:
            handler = handlers.drain
            if inspect.iscoroutinefunction(handler):

                if dispose:

                    async def wrapper(app, instances, handler, ws):
                        try:
                            await handler(ws)
                        finally:
                            app._ws_factory.dispose(instances)

                    app.run_async(wrapper(app, instances, handler, ws))
                else:
                    app.run_async(handler(ws))
            else:
                handler(ws)
                if dispose:
                    app._ws_factory.dispose(instances)
        except Exception:
            if dispose:
                app._ws_factory.dispose(instances)
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, void*)")
def uws_websocket_drain_handler_with_extension(ws, user_data):
    if user_data != ffi.NULL:
        try:
            handlers, app = ffi.from_handle(user_data)
            ws = WebSocket(ws, app)
            app.loop.is_idle = False
            # bind methods to websocket
            app._ws_extension.set_properties(ws)
            # set default value in properties
            app._ws_extension.bind_methods(ws)
            handler = handlers.drain
            if inspect.iscoroutinefunction(handler):
                app.run_async(handler(ws))
            else:
                handler(ws)
        except Exception:
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, void*)")
def uws_websocket_drain_handler(ws, user_data):
    if user_data != ffi.NULL:
        try:
            handlers, app = ffi.from_handle(user_data)
            ws = WebSocket(ws, app)
            app.loop.is_idle = False
            handler = handlers.drain
            if inspect.iscoroutinefunction(handler):
                app.run_async(handler(ws))
            else:
                handler(ws)
        except Exception:
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, const char *, size_t, int, int, void*)")
def uws_websocket_factory_subscription_handler(
    ws,
    topic_name,
    topic_name_length,
    new_number_of_subscriber,
    old_number_of_subscriber,
    user_data,
):
    if user_data != ffi.NULL:
        handlers, app = ffi.from_handle(user_data)
        app.loop.is_idle = False
        instances = app._ws_factory.get(app, ws)
        ws, dispose = instances
        try:

            if topic_name == ffi.NULL:
                topic = None
            else:
                topic = ffi.unpack(topic_name, topic_name_length).decode("utf-8")

            handler = handlers.subscription
            if inspect.iscoroutinefunction(handler):

                if dispose:

                    async def wrapper(
                        app,
                        instances,
                        handler,
                        ws,
                        topic,
                        new_number_of_subscriber,
                        old_number_of_subscriber,
                    ):
                        try:
                            await handler(
                                ws,
                                topic,
                                new_number_of_subscriber,
                                old_number_of_subscriber,
                            )
                        finally:
                            app._ws_factory.dispose(instances)

                    app.run_async(
                        wrapper(
                            app,
                            instances,
                            handler,
                            ws,
                            topic,
                            int(new_number_of_subscriber),
                            int(old_number_of_subscriber),
                        )
                    )
                else:
                    app.run_async(
                        handler(
                            ws,
                            topic,
                            int(new_number_of_subscriber),
                            int(old_number_of_subscriber),
                        )
                    )
            else:
                handler(
                    ws,
                    topic,
                    int(new_number_of_subscriber),
                    int(old_number_of_subscriber),
                )
                if dispose:
                    app._ws_factory.dispose(instances)
        except Exception:
            if dispose:
                app._ws_factory.dispose(instances)
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, const char *, size_t, int, int, void*)")
def uws_websocket_subscription_handler(
    ws,
    topic_name,
    topic_name_length,
    new_number_of_subscriber,
    old_number_of_subscriber,
    user_data,
):
    if user_data != ffi.NULL:
        try:
            handlers, app = ffi.from_handle(user_data)
            app.loop.is_idle = False
            ws = WebSocket(ws, app)
            handler = handlers.subscription

            if topic_name == ffi.NULL:
                topic = None
            else:
                topic = ffi.unpack(topic_name, topic_name_length).decode("utf-8")

            if inspect.iscoroutinefunction(handler):
                app.run_async(
                    handler(
                        ws,
                        topic,
                        int(new_number_of_subscriber),
                        int(old_number_of_subscriber),
                    )
                )
            else:
                handler(
                    ws,
                    topic,
                    int(new_number_of_subscriber),
                    int(old_number_of_subscriber),
                )
        except Exception:
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, const char *, size_t, int, int, void*)")
def uws_websocket_subscription_handler_with_extension(
    ws,
    topic_name,
    topic_name_length,
    new_number_of_subscriber,
    old_number_of_subscriber,
    user_data,
):
    if user_data != ffi.NULL:
        try:
            handlers, app = ffi.from_handle(user_data)
            app.loop.is_idle = False
            ws = WebSocket(ws, app)
            # bind methods to websocket
            app._ws_extension.set_properties(ws)
            # set default value in properties
            app._ws_extension.bind_meth
            handler = handlers.subscription

            if topic_name == ffi.NULL:
                topic = None
            else:
                topic = ffi.unpack(topic_name, topic_name_length).decode("utf-8")

            if inspect.iscoroutinefunction(handler):
                app.run_async(
                    handler(
                        ws,
                        topic,
                        int(new_number_of_subscriber),
                        int(old_number_of_subscriber),
                    )
                )
            else:
                handler(
                    ws,
                    topic,
                    int(new_number_of_subscriber),
                    int(old_number_of_subscriber),
                )
        except Exception:
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, void*)")
def uws_websocket_factory_open_handler(ws, user_data):
    if user_data != ffi.NULL:
        handlers, app = ffi.from_handle(user_data)
        app.loop.is_idle = False
        instances = app._ws_factory.get(app, ws)
        ws, dispose = instances
        try:
            handler = handlers.open
            if inspect.iscoroutinefunction(handler):
                if dispose:

                    async def wrapper(app, instances, handler, ws):
                        try:
                            await handler(ws)
                        finally:
                            app._ws_factory.dispose(instances)

                    app.run_async(wrapper(app, instances, handler, ws))
                else:
                    app.run_async(handler(ws))
            else:
                handler(ws)
                if dispose:
                    app._ws_factory.dispose(instances)
        except Exception:
            if dispose:
                app._ws_factory.dispose(instances)
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, void*)")
def uws_websocket_open_handler_with_extension(ws, user_data):

    if user_data != ffi.NULL:
        try:
            handlers, app = ffi.from_handle(user_data)
            app.loop.is_idle = False
            ws = WebSocket(ws, app)
            # bind methods to websocket
            app._ws_extension.set_properties(ws)
            # set default value in properties
            app._ws_extension.bind_meth
            handler = handlers.open
            if inspect.iscoroutinefunction(handler):
                app.run_async(handler(ws))
            else:
                handler(ws)
        except Exception:
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, void*)")
def uws_websocket_open_handler(ws, user_data):

    if user_data != ffi.NULL:
        try:
            handlers, app = ffi.from_handle(user_data)
            app.loop.is_idle = False
            ws = WebSocket(ws, app)
            handler = handlers.open
            if inspect.iscoroutinefunction(handler):
                app.run_async(handler(ws))
            else:
                handler(ws)
        except Exception:
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, const char*, size_t, uws_opcode_t, void*)")
def uws_websocket_factory_message_handler(ws, message, length, opcode, user_data):
    if user_data != ffi.NULL:
        handlers, app = ffi.from_handle(user_data)
        app.loop.is_idle = False
        instances = app._ws_factory.get(app, ws)
        ws, dispose = instances
        try:
            if message == ffi.NULL:
                data = None
            else:
                data = ffi.unpack(message, length)
            opcode = OpCode(opcode)
            if opcode == OpCode.TEXT:
                data = data.decode("utf-8")

            handler = handlers.message
            if inspect.iscoroutinefunction(handler):
                if dispose:

                    async def wrapper(app, instances, handler, ws, data):
                        try:
                            await handler(ws, data)
                        finally:
                            app._ws_factory.dispose(instances)

                    app.run_async(wrapper(app, instances, handler, ws, data))
                else:
                    app.run_async(handler(ws, data))
            else:
                handler(ws, data, opcode)
                if dispose:
                    app._ws_factory.dispose(instances)

        except Exception:
            if dispose:
                app._ws_factory.dispose(instances)
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, const char*, size_t, uws_opcode_t, void*)")
def uws_websocket_message_handler_with_extension(
    ws, message, length, opcode, user_data
):
    if user_data != ffi.NULL:
        try:
            handlers, app = ffi.from_handle(user_data)
            app.loop.is_idle = False
            ws = WebSocket(ws, app)
            # bind methods to websocket
            app._ws_extension.set_properties(ws)
            # set default value in properties
            app._ws_extension.bind_meth

            if message == ffi.NULL:
                data = None
            else:
                data = ffi.unpack(message, length)
            opcode = OpCode(opcode)
            if opcode == OpCode.TEXT:
                data = data.decode("utf-8")

            handler = handlers.message
            if inspect.iscoroutinefunction(handler):
                app.run_async(handler(ws, data, opcode))
            else:
                handler(ws, data, opcode)

        except Exception:
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, const char*, size_t, uws_opcode_t, void*)")
def uws_websocket_message_handler(ws, message, length, opcode, user_data):
    if user_data != ffi.NULL:
        try:
            handlers, app = ffi.from_handle(user_data)
            app.loop.is_idle = False
            ws = WebSocket(ws, app)

            if message == ffi.NULL:
                data = None
            else:
                data = ffi.unpack(message, length)
            opcode = OpCode(opcode)
            if opcode == OpCode.TEXT:
                data = data.decode("utf-8")

            handler = handlers.message
            if inspect.iscoroutinefunction(handler):
                app.run_async(handler(ws, data, opcode))
            else:
                handler(ws, data, opcode)

        except Exception:
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, const char*, size_t, void*)")
def uws_websocket_factory_pong_handler(ws, message, length, user_data):
    if user_data != ffi.NULL:
        handlers, app = ffi.from_handle(user_data)
        app.loop.is_idle = False
        instances = app._ws_factory.get(app, ws)
        ws, dispose = instances
        try:
            if message == ffi.NULL:
                data = None
            else:
                data = ffi.unpack(message, length)

            handler = handlers.pong
            if inspect.iscoroutinefunction(handler):
                if dispose:

                    async def wrapper(app, instances, handler, ws, data):
                        try:
                            await handler(ws, data)
                        finally:
                            app._ws_factory.dispose(instances)

                    app.run_async(wrapper(app, instances, handler, ws, data))
                else:
                    app.run_async(handler(ws, data))
            else:
                handler(ws, data)
                if dispose:
                    app._ws_factory.dispose(instances)

        except Exception:
            if dispose:
                app._ws_factory.dispose(instances)
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, const char*, size_t, void*)")
def uws_websocket_pong_handler_with_extension(ws, message, length, user_data):
    if user_data != ffi.NULL:
        try:
            handlers, app = ffi.from_handle(user_data)
            app.loop.is_idle = False
            ws = WebSocket(ws, app)
            # bind methods to websocket
            app._ws_extension.set_properties(ws)
            # set default value in properties
            app._ws_extension.bind_meth
            if message == ffi.NULL:
                data = None
            else:
                data = ffi.unpack(message, length)

            handler = handlers.pong
            if inspect.iscoroutinefunction(handler):
                app.run_async(handler(ws, data))
            else:
                handler(ws, data)
        except Exception:
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, const char*, size_t, void*)")
def uws_websocket_pong_handler(ws, message, length, user_data):
    if user_data != ffi.NULL:
        try:
            handlers, app = ffi.from_handle(user_data)
            app.loop.is_idle = False
            ws = WebSocket(ws, app)
            if message == ffi.NULL:
                data = None
            else:
                data = ffi.unpack(message, length)

            handler = handlers.pong
            if inspect.iscoroutinefunction(handler):
                app.run_async(handler(ws, data))
            else:
                handler(ws, data)
        except Exception:
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, const char*, size_t, void*)")
def uws_websocket_factory_ping_handler(ws, message, length, user_data):
    if user_data != ffi.NULL:
        handlers, app = ffi.from_handle(user_data)
        app.loop.is_idle = False
        instances = app._ws_factory.get(app, ws)
        ws, dispose = instances

        try:
            if message == ffi.NULL:
                data = None
            else:
                data = ffi.unpack(message, length)

            handler = handlers.ping
            if inspect.iscoroutinefunction(handler):
                if dispose:

                    async def wrapper(app, instances, handler, ws, data):
                        try:
                            await handler(ws, data)
                        finally:
                            app._ws_factory.dispose(instances)

                    app.run_async(wrapper(app, instances, handler, ws, data))
                else:
                    app.run_async(handler(ws, data))
            else:
                handler(ws, data)
                if dispose:
                    app._ws_factory.dispose(instances)

        except Exception:
            if dispose:
                app._ws_factory.dispose(instances)
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, const char*, size_t, void*)")
def uws_websocket_ping_handler_with_extension(ws, message, length, user_data):
    if user_data != ffi.NULL:
        try:
            handlers, app = ffi.from_handle(user_data)
            app.loop.is_idle = False
            ws = WebSocket(ws, app)
            # bind methods to websocket
            app._ws_extension.set_properties(ws)
            # set default value in properties
            app._ws_extension.bind_meth

            if message == ffi.NULL:
                data = None
            else:
                data = ffi.unpack(message, length)

            handler = handlers.ping
            if inspect.iscoroutinefunction(handler):
                app.run_async(handler(ws, data))
            else:
                handler(ws, data)

        except Exception:
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, const char*, size_t, void*)")
def uws_websocket_ping_handler(ws, message, length, user_data):
    if user_data != ffi.NULL:
        try:
            handlers, app = ffi.from_handle(user_data)
            app.loop.is_idle = False
            ws = WebSocket(ws, app)

            if message == ffi.NULL:
                data = None
            else:
                data = ffi.unpack(message, length)

            handler = handlers.ping
            if inspect.iscoroutinefunction(handler):
                app.run_async(handler(ws, data))
            else:
                handler(ws, data)

        except Exception:
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, int, const char*, size_t, void*)")
def uws_websocket_factory_close_handler(ws, code, message, length, user_data):
    if user_data != ffi.NULL:
        handlers, app = ffi.from_handle(user_data)
        app.loop.is_idle = False
        instances = app._ws_factory.get(app, ws)
        ws, dispose = instances

        try:
            if message == ffi.NULL:
                data = None
            else:
                data = ffi.unpack(message, length)

            handler = handlers.close

            if handler is None:
                if dispose:
                    app._ws_factory.dispose(instances)
                return

            if inspect.iscoroutinefunction(handler):

                async def wrapper(app, instances, handler, ws, code, data, dispose):
                    try:
                        return await handler(ws, code, data)
                    finally:
                        key = ws.get_user_data_uuid()
                        if key is not None:
                            app._socket_refs.pop(key, None)
                        if dispose:
                            app._ws_factory.dispose(instances)

                app.run_async(
                    wrapper(app, instances, handler, ws, int(code), data, dispose)
                )
            else:
                handler(ws, int(code), data)
                key = ws.get_user_data_uuid()
                if key is not None:
                    app._socket_refs.pop(key, None)
                if dispose:
                    app._ws_factory.dispose(instances)

        except Exception:
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, int, const char*, size_t, void*)")
def uws_websocket_close_handler_with_extension(ws, code, message, length, user_data):
    if user_data != ffi.NULL:
        try:
            handlers, app = ffi.from_handle(user_data)
            app.loop.is_idle = False
            # pass to free data on WebSocket if needed
            ws = WebSocket(ws, app)
            # bind methods to websocket
            app._ws_extension.set_properties(ws)
            # set default value in properties
            app._ws_extension.bind_meth

            if message == ffi.NULL:
                data = None
            else:
                data = ffi.unpack(message, length)

            handler = handlers.close

            if handler is None:
                return

            if inspect.iscoroutinefunction(handler):

                async def wrapper(app, handler, ws, code, data):
                    try:
                        return await handler(ws, code, data)
                    finally:
                        key = ws.get_user_data_uuid()
                        if key is not None:
                            app._socket_refs.pop(key, None)

                app.run_async(wrapper(app, handler, ws, int(code), data))
            else:
                handler(ws, int(code), data)
                key = ws.get_user_data_uuid()
                if key is not None:
                    app._socket_refs.pop(key, None)

        except Exception:
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_websocket_t*, int, const char*, size_t, void*)")
def uws_websocket_close_handler(ws, code, message, length, user_data):
    if user_data != ffi.NULL:
        try:
            handlers, app = ffi.from_handle(user_data)
            app.loop.is_idle = False
            # pass to free data on WebSocket if needed
            ws = WebSocket(ws, app)

            if message == ffi.NULL:
                data = None
            else:
                data = ffi.unpack(message, length)

            handler = handlers.close

            if handler is None:
                return

            if inspect.iscoroutinefunction(handler):

                async def wrapper(app, handler, ws, code, data):
                    try:
                        return await handler(ws, code, data)
                    finally:
                        key = ws.get_user_data_uuid()
                        if key is not None:
                            app._socket_refs.pop(key, None)

                app.run_async(wrapper(app, handler, ws, int(code), data))
            else:
                handler(ws, int(code), data)
                key = ws.get_user_data_uuid()
                if key is not None:
                    app._socket_refs.pop(key, None)

        except Exception:
            logging.error(
                "Uncaught Exception: %s" % traceback.format_exc()
            )  # just log in console the error to call attention


@ffi.callback("void(uws_res_t*, uws_req_t*, void*)")
def uws_generic_factory_method_handler(res, req, user_data):
    if user_data != ffi.NULL:
        (handler, app) = ffi.from_handle(user_data)
        app.loop.is_idle = False
        instances = app._factory.get(app, res, req)
        (response, request, dispose) = instances
        try:
            if inspect.iscoroutinefunction(handler):
                response.grab_aborted_handler()
                if dispose:

                    async def wrapper(app, instances, handler, response, request):
                        try:
                            await handler(response, request)
                        finally:
                            app._factory.dispose(instances)

                    response.run_async(
                        wrapper(app, instances, handler, response, request)
                    )
                else:
                    response.run_async(handler(response, request))
            else:
                handler(response, request)
                if dispose:
                    app._factory.dispose(instances)

        except Exception as err:
            response.grab_aborted_handler()
            app.trigger_error(err, response, request)
            if dispose:
                app._factory.dispose(instances)


@ffi.callback("void(uws_res_t*, uws_req_t*, uws_socket_context_t*, void*)")
def uws_websocket_factory_upgrade_handler(res, req, context, user_data):
    if user_data != ffi.NULL:
        handlers, app = ffi.from_handle(user_data)
        app.loop.is_idle = False
        instances = app._factory.get(app, res, req)
        (response, request, dispose) = instances
        try:
            handler = handlers.upgrade

            if inspect.iscoroutinefunction(handler):
                response.grab_aborted_handler()
                if dispose:

                    async def wrapper(
                        app, instances, handler, response, request, context
                    ):
                        try:
                            await handler(response, request, context)
                        finally:
                            app._factadd_done_callbackory.dispose(instances)

                    response.run_async(
                        wrapper(app, instances, handler, response, request, context)
                    )
                else:
                    response.run_async(handler(response, request, context))
            else:
                handler(response, request, context)
                if dispose:
                    app._factory.dispose(instances)
        except Exception as err:
            response.grab_aborted_handler()
            app.trigger_error(err, response, request)
            if dispose:
                app._factory.dispose(instances)


@ffi.callback("void(uws_res_t*, uws_req_t*, uws_socket_context_t*, void*)")
def uws_websocket_upgrade_handler_with_extension(res, req, context, user_data):
    if user_data != ffi.NULL:
        handlers, app = ffi.from_handle(user_data)
        app.loop.is_idle = False
        response = AppResponse(res, app)
        # set default value in properties
        app._response_extension.set_properties(response)
        # bind methods to response
        app._response_extension.bind_methods(response)
        request = AppRequest(req, app)
        # set default value in properties
        app._request_extension.set_properties(request)
        # bind methods to request
        app._request_extension.bind_methods(request)

        try:
            handler = handlers.upgrade
            if inspect.iscoroutinefunction(handler):
                response.run_async(handler(response, request, context))
            else:
                handler(response, request, context)

        except Exception as err:
            response.grab_aborted_handler()
            app.trigger_error(err, response, request)


@ffi.callback("void(uws_res_t*, uws_req_t*, uws_socket_context_t*, void*)")
def uws_websocket_upgrade_handler(res, req, context, user_data):
    if user_data != ffi.NULL:
        handlers, app = ffi.from_handle(user_data)
        app.loop.is_idle = False
        response = AppResponse(res, app)
        request = AppRequest(req, app)
        try:
            handler = handlers.upgrade
            if inspect.iscoroutinefunction(handler):
                response.run_async(handler(response, request, context))
            else:
                handler(response, request, context)

        except Exception as err:
            response.grab_aborted_handler()
            app.trigger_error(err, response, request)



@ffi.callback("void(uws_res_t*, uws_req_t*, void*)")
def uws_generic_method_handler_with_extension(res, req, user_data):
    if user_data != ffi.NULL:
        (handler, app) = ffi.from_handle(user_data)
        app.loop.is_idle = False
        response = AppResponse(res, app)
        # set default value in properties
        app._response_extension.set_properties(response)
        # bind methods to response
        app._response_extension.bind_methods(response)
        request = AppRequest(req, app)
        # set default value in properties
        app._request_extension.set_properties(request)
        # bind methods to request
        app._request_extension.bind_methods(request)

        try:
            if inspect.iscoroutinefunction(handler):
                response.grab_aborted_handler()
                response.run_async(handler(response, request))
            else:
                handler(response, request)
        except Exception as err:
            response.grab_aborted_handler()
            app.trigger_error(err, response, request)


@ffi.callback("void(uws_res_t*, uws_req_t*, void*)")
def uws_generic_method_handler(res, req, user_data):
    if user_data != ffi.NULL:
        (handler, app) = ffi.from_handle(user_data)
        app.loop.is_idle = False
        response = AppResponse(res, app)
        request = AppRequest(req, app)

        try:
            if inspect.iscoroutinefunction(handler):
                response.grab_aborted_handler()
                response.run_async(handler(response, request))
            else:
                handler(response, request)
        except Exception as err:
            response.grab_aborted_handler()
            app.trigger_error(err, response, request)


@ffi.callback("void(struct us_listen_socket_t*, const char*, size_t,int, void*)")
def uws_generic_listen_domain_handler(
    listen_socket, domain, length, _options, user_data
):
    domain = ffi.unpack(domain, length).decode("utf8")
    if listen_socket == ffi.NULL:
        raise RuntimeError("Failed to listen on domain %s" % domain)

    if user_data != ffi.NULL:

        app = ffi.from_handle(user_data)
        if hasattr(app, "_listen_handler") and hasattr(app._listen_handler, "__call__"):
            app.socket = listen_socket
            app._listen_handler(AppListenOptions(domain=domain, options=int(_options)))


@ffi.callback("void(struct us_listen_socket_t*, uws_app_listen_config_t, void*)")
def uws_generic_listen_handler(listen_socket, config, user_data):
    if listen_socket == ffi.NULL:
        raise RuntimeError("Failed to listen on port %d" % int(config.port))

    if user_data != ffi.NULL:
        app = ffi.from_handle(user_data)
        app.loop.is_idle = False
        config.port = lib.us_socket_local_port(app.SSL, listen_socket)
        if hasattr(app, "_listen_handler") and hasattr(app._listen_handler, "__call__"):
            app.socket = listen_socket
            host = ""
            try:
                host = ffi.string(config.host).decode("utf8")
            except Exception:
                pass
            app._listen_handler(
                None
                if config == ffi.NULL
                else AppListenOptions(
                    port=int(config.port),
                    host=None
                    if config.host == ffi.NULL or listen_socket == ffi.NULL
                    else host,
                    options=int(config.options),
                )
            )


@ffi.callback("bool(uws_res_t*, uintmax_t, void*)")
def uws_generic_on_writable_handler(res, offset, user_data):
    if user_data != ffi.NULL:
        res = ffi.from_handle(user_data)
        res.app.loop.is_idle = False
        result = res.trigger_writable_handler(offset)
        return result
    return False
