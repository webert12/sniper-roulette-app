import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Dict

app = FastAPI(title="Sniper Roulette Engine")

MATRIZ_PUXADAS: Dict[int, List[int]] = {
    10: [12, 35, 3, 26],
    20: [1, 14, 31, 9],
    0:  [26, 32, 15, 19],
    7:  [18, 29, 28, 12]
}

historico_rodadas: List[int] = []

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

def processar_numero(numero: int) -> dict:
    historico_rodadas.insert(0, numero)
    if len(historico_rodadas) > 20:
        historico_rodadas.pop()

    sugestoes = MATRIZ_PUXADAS.get(numero, [])
    
    return {
        "tipo": "NOVA_RODADA",
        "ultimo_numero": numero,
        "historico": historico_rodadas,
        "alerta": len(sugestoes) > 0,
        "sugestoes": sugestoes,
        "mensagem": f"ENTRADA SNIPER: Apostar nos números {sugestoes}" if sugestoes else "Aguardando sinal..."
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    await websocket.send_json({
        "tipo": "INIT",
        "historico": historico_rodadas
    })
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/injetar-numero/{numero}")
async def injetar_numero(numero: int):
    if 0 <= numero <= 36:
        dados_analise = processar_numero(numero)
        await manager.broadcast(dados_analise)
        return {"status": "sucesso", "dados": dados_analise}
    return {"status": "erro", "mensagem": "Número inválido"}
