from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="课堂最小演示")

class EchoRequest(BaseModel):
    message: str = Field(min_length=1, max_length=100)
    times: int = Field(default=1, ge=1, le=10)

@app.post("/echo")
def echo(req: EchoRequest):
    return {"code": 0, "message": "success", "data": {"reply": req.message * req.times}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
