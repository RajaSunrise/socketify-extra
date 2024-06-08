from socketify_extra import Socketify


app = Socketify()




app.listen(8000, lambda config: print(f"Listening in http://localhost:{config.port}"))
app.run()