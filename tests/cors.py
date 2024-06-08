from socketify_extra import Socketify

app = Socketify()


def http_options(res, req):
    res.write_header("Access-Contoll-Allow-Origin", "*")
    res.write_header("Access-Controll-Allow-Method", "GET, POST")
    res.write_header("Access-Controll-Allow-Headers", "content-Type")
    res.end("")


def http_handle(res, req):
    if req.get_method() == "OPTIONs":
        http_options(res, req)
    else:
        res.write_header("Access-Contoll-Allow-Origin", "http://localhost:3000")
    res.write_header("Access-Controll-Allow-Method", "GET, POST, OPTIONS, DELETE, PUT, PATCH")
    res.write_header("Access-Controll-Allow-Headers", "content-Type")
    res.end("Hello Socketify CORS Enable")

async def root_handler(res, req):
    nama = "indra aryadi"
    res.end(f"nama saya indra {nama}")


app.any("/*", http_handle)
app.get("/", root_handler)
app.listen(8000, lambda config: print(f"Listening in http://localhost:{config.port}"))
app.run()