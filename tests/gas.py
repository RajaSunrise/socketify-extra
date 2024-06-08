from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Menambahkan middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["www.anjingreteryeqergergh.com"],  # Bisa disesuaikan dengan domain Anda, atau "*" untuk menerima dari semua domain.
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Metode HTTP yang diizinkan.
    allow_headers=[""],  # Header yang diizinkan.
)

# Route sederhana untuk pengujian CORS
@app.get("/")
async def read_root():
    return {"message": "Hello, CORS"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
