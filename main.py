import asyncio
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI(title="Sniper Roulette Engine")

# ==========================================
# 1. MATRIZ DE ESTRATÉGIAS ("Puxadas")
# ==========================================
MATRIZ_PUXADAS: Dict[int, List[int]] = {
    10: [12, 35, 3, 26],
    20: [1, 14, 31, 9],
    0:  [26, 32, 15, 19],
    7:  [18, 29, 28, 12]
}

historico_rodadas: List[int] = []

# ==========================================
# 2. GERENCIADOR DE WEBSOCKETS (Tempo Real)
# ==========================================
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

# ==========================================
# 3. MOTOR DE ANÁLISE DE SINAIS
# ==========================================
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

# ==========================================
# 4. INTERFACE HTML EMBUTIDA
# ==========================================
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sniper Roulette Monitor</title>
    <style>
        body { background-color: #121212; color: #fff; font-family: sans-serif; display: flex; justify-content: center; padding: 20px; }
        .card { width: 100%; max-width: 400px; background: #1e1e1e; padding: 20px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); text-align: center; }
        #status { font-size: 12px; margin-bottom: 10px; color: #ff3333; }
        .online { color: #00ff00 !important; }
        .ball { width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: bold; margin: 0 auto 20px; border: 4px solid #fff; }
        .red { background-color: #d32f2f; }
        .black { background-color: #000; }
        .green { background-color: #2e7d32; }
        #alert-box { background: #2a2a2a; border: 2px solid #ffd700; padding: 15px; border-radius: 8px; display: none; margin-top: 20px; }
        .pulse { animation: pulse-red 2s infinite; }
        @keyframes pulse-red { 0% { box-shadow: 0 0 0 0 rgba(255, 215, 0, 0.7); } 70% { box-shadow: 0 0 0 10px rgba(255, 215, 0, 0); } }
        .history { display: flex; gap: 5px; justify-content: center; margin-top: 20px; overflow-x: auto; }
        .hist-item { width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; }
    </style>
</head>
<body>
<div class="card">
    <h2>Immersive Roulette</h2>
    <div id="status">Desconectado</div>
    <div id="ball" class="ball" style="display:none">0</div>
    <div id="alert-box" class="pulse">
        <h3 style="color: #ffd700;">🎯 ENTRADA SNIPER</h3>
        <p id="msg-sniper">Aguardando...</p>
    </div>
    <div class="history" id="history"></div>
</div>

<script>
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const WS_URL = `${protocol}//${window.location.host}/ws`;
    const socket = new WebSocket(WS_URL);
    
    const statusDiv = document.getElementById('status');
    const ballDiv = document.getElementById('ball');
    const alertBox = document.getElementById('alert-box');
    const msgSniper = document.getElementById('msg-sniper');
    const historyDiv = document.getElementById('history');

    socket.onopen = () => { statusDiv.innerText = "Conectado"; statusDiv.classList.add('online'); };
    socket.onclose = () => { statusDiv.innerText = "Desconectado"; statusDiv.classList.remove('online'); };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.ultimo_numero !== undefined) {
            ballDiv.style.display = "flex";
            ballDiv.innerText = data.ultimo_numero;
            ballDiv.className = `ball ${getColorClass(data.ultimo_numero)}`;

            if (data.alerta) {
                alertBox.style.display = "block";
                msgSniper.innerText = data.mensagem;
            } else {
                alertBox.style.display = "none";
            }

            historyDiv.innerHTML = "";
            data.historico.forEach(num => {
                const span = document.createElement('div');
                span.className = `hist-item ${getColorClass(num)}`;
                span.innerText = num;
                historyDiv.appendChild(span);
            });
        }
    };

    function getColorClass(num) {
        if (num === 0) return 'green';
        const redNumbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36];
        return redNumbers.includes(num) ? 'red' : 'black';
    }
</script>
</body>
</html>
"""

# ==========================================
# 5. ROTAS DO SERVIDOR
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_CONTENT

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
