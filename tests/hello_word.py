from socketify_extra import Socketify

app = Socketify()

async def hello(res, req):
    res.write_header("Server", "myserver")
    res.get_json()
    res.end("hello word")
    

app.get("/", hello)
app.listen(8000, lambda config: print(f"Listening in http://localhost:{config.port}"))
app.run()