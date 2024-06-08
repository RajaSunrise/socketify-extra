from socketify_extra import Socketify, Response, Request, MiddlewareRouter

app = Socketify()

async def healthcheck(res: Response, _: Request, __=None):
    res.write_header("Server", "myserver")
    res.write_header("Server", "uWebSocket_21")
    res.write_status(200)
    return res.end_without_body(True)


basic_router = MiddlewareRouter(app)
basic_router.head("/health", healthcheck)

app.listen(8000, lambda config: print(f"Listening in http://localhost:{config.port}"))
app.run()