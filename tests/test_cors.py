from socketify_extra import Socketify, Response, Request, MiddlewareRouter
import re

app = Socketify()

def home(res, req):
    res.get_json()
    res.end("hello word")

def cors_middleware(res: Response, req:Request, data=None):
    origin = req.get_header('origin')
    if origin:
        allowed_origins = ['http://localhost:8080', 'https://yourdomain.com']
        if any(re.match(allowed_origin, origin) for allowed_origin in allowed_origins):
            res.write_header(b'Access-Control-Allow-Origin', origin.encode())
            res.write_header(b'Access-Control-Allow-Methods', b'GET, POST, PUT, DELETE, OPTIONS')
            res.write_header(b'Access-Control-Allow-Headers', b'Content-Type, Authorization')
            if req.get_method() == 'OPTIONS':
                # Pre-flight request, just return 204 No Content
                res.write_status(204).end_without_body()
                return False
    return data

auth_router = MiddlewareRouter(app, cors_middleware)

app.get("/", home)
app.listen(
    8080,
    lambda config: print("Listening on port http://localhost:%d now\n" % config.port),
)
app.run()

