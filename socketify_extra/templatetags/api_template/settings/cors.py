from socketify_extra import Socketify


router = Socketify()


def http_options(res, req):
    # change "*" To CORS example "http://localhost:3000, http://example.domain.com"
    res.write_header("Access-Contoll-Allow-Origin", "*")
    # change your method cors example "GET, POST"
    res.write_header("Access-Controll-Allow-Method", "GET, POST, OPTIONS, DELETE, PUT, PATCH")
    res.write_header("Access-Controll-Allow-Headers", "content-Type")
    res.end("")


def http_handle(res, req):
    if req.get_method() == "OPTIONS":
        http_options(res, req)
    else:
        res.write_header("Access-Contoll-Allow-Origin", "*")  # edit your cors "http://localhost:3000, http://example.domain.com"
    res.write_header("Access-Controll-Allow-Method", "GET, POST, OPTIONS, DELETE, PUT, PATCH")
    res.write_header("Access-Controll-Allow-Headers", "content-Type")
    res.end("Hello from Socketify CORS Enable")


# change your path url example router.any("/api/*")
router.any("/*", http_handle)
