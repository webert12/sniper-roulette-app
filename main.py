import asyncio
from typing import List, Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI(title="Sniper Roulette Engine - Auto")

# ==========================================
# 1. ORDEM OFICIAL DA RACETRACK EUROPEIA
# ==========================================
RACETRACK_EUROPEIA = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
    5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

# Pega o número alvo + 3 vizinhos no sentido horário e 3 no anti-horário
def obter_vizinhos_racetrack(numero: int, raio: int = 3) -> List[int]:
    if numero not in RACETRACK_EUROPEIA:
        return []
    
    idx = RACETRACK_EUROPEIA.index(numero)
    tamanho = len(RACETRACK_EUROPEIA)
    vizinhos = []
    
    for i in range(-raio, raio + 1):
        novo_idx = (idx + i) % tamanho
        vizinhos.append(RACETRACK_EUROPEIA[novo_idx])
        
    return vizinhos

# ==========================================
# 2. MATRIZ DE ESTRATÉGIAS PERSONALIZADA
# ==========================================
MATRIZ_PUXADAS: Dict[int, List[int]] = {
    0:  [20, 30, 10],
    1:  [17, 7, 20],
    2:  [2, 22, 20],
    3:  [3, 33, 15],
    4:  [21, 9, 19],
    5:  [25, 15, 35],
    6:  [20, 17, 7],
    7:  [7, 17, 20],
    8:  [30, 0, 20],
    9:  [9, 19, 31],
    10: [0, 20, 30],
    11: [30, 0, 20],
    12: [33, 15, 35],
    13: [20, 7, 17],
    14: [17, 7, 20],
    15: [9, 5, 35],
    16: [3, 33, 15],
    17: [17, 20, 7],
    18: [2, 22, 20],
    19: [19, 9, 31],
    20: [17, 7, 20],
    21: [2, 22, 20],
    22: [2, 22, 20],
    23: [0, 10, 30],
    24: [35, 15, 25],
    25: [20, 22, 2],
    26: [0, 10, 30],
    27: [17, 7, 20],
    28: [7, 17, 20],
    29: [7, 17, 20],
    30: [0, 20, 30],
    31: [9, 19, 31],
    32: [0, 10, 20],
    33: [3, 33, 15],
    34: [7, 20, 17],
    35: [3, 33, 15],
    36: [20, 30, 0]
}

historico_rodadas: List[int] = []
placar = {"greens": 0, "reds": 0}
ultimos_alvos_cobertura: Set[int] = set()

# ==========================================
# 3. WEBSOCKET MANAGER
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
# 4. PROCESSADOR DE SINAL E VALIDAÇÃO DE VIZINHOS
# ==========================================
def processar_numero(numero: int) -> dict:
    global ultimos_alvos_cobertura
    
    # 1. VALIDAÇÃO DO GREEN / RED (Verifica se o novo número bateu nos vizinhos)
    if ultimos_alvos_cobertura:
        if numero in ultimos_alvos_cobertura:
            placar["greens"] += 1
        else:
            placar["reds"] += 1

    historico_rodadas.insert(0, numero)
    if len(historico_rodadas) > 20:
        historico_rodadas.pop()

    # 2. CALCULA OS NOVO SINAIS E A COBERTURA DE 3 VIZINHOS PARA CADA ALVO
    alvos_principais = MATRIZ_PUXADAS.get(numero, [])
    cobertura_total: Set[int] = set()
    
    for alvo in alvos_principais:
        vizinhos = obter_vizinhos_racetrack(alvo, raio=3)
        cobertura_total.update(vizinhos)

    # Guarda a cobertura total para validar a próxima rodada
    ultimos_alvos_cobertura = cobertura_total.copy()

    return {
        "tipo": "NOVA_RODADA",
        "ultimo_numero": numero,
        "historico": historico_rodadas,
        "alerta": len(alvos_principais) > 0,
        "alvos_principais": alvos_principais,
        "sugestoes": list(cobertura_total),
        "mensagem": f"JOGAR NOS ALVOS {alvos_principais} + 3 VIZINHOS",
        "placar": placar
    }

# ==========================================
# 5. FRONTEND DASHBOARD
# ==========================================
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Immersive Sniper Auto</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background-color: #0d0f12; color: #e1e1e6; font-family: sans-serif; display: flex; justify-content: center; padding: 15px; }
        .container { width: 100%; max-width: 480px; display: flex; flex-direction: column; gap: 15px; }
        
        .header-card { background: #16181e; padding: 15px; border-radius: 12px; border: 1px solid #292d3e; text-align: center; }
        .title { font-size: 20px; font-weight: bold; color: #fff; }
        #status { font-size: 11px; margin-top: 4px; color: #ff5555; text-transform: uppercase; font-weight: bold; }
        .online { color: #00ff88 !important; }

        .score-board { display: flex; justify-content: space-around; margin-top: 10px; background: #0d0f12; padding: 8px; border-radius: 8px; }
        .score-item { font-size: 13px; font-weight: bold; }
        .green-text { color: #00ff88; }
        .red-text { color: #ff5555; }

        .ball { width: 75px; height: 75px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 32px; font-weight: bold; border: 4px solid #ffffff22; margin: 0 auto; }
        .red { background: linear-gradient(145deg, #e63946, #b71c1c); }
        .black { background: linear-gradient(145deg, #2b2d42, #11111d); }
        .green { background: linear-gradient(145deg, #2a9d8f, #1b4332); }

        #alert-box { background: #221f10; border: 2px solid #ffd700; padding: 15px; border-radius: 12px; text-align: center; display: none; }
        .pulse { animation: pulse-gold 1.5s infinite; }
        @keyframes pulse-gold { 0% { box-shadow: 0 0 0 0 rgba(255, 215, 0, 0.6); } 70% { box-shadow: 0 0 0 12px rgba(255, 215, 0, 0); } }

        .section-title { font-size: 12px; color: #828a9e; text-transform: uppercase; margin-bottom: 8px; font-weight: bold; }
        .history { display: flex; gap: 6px; overflow-x: auto; padding-bottom: 5px; }
        .hist-item { min-width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: bold; }

        .racetrack-grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 3px; background: #0d0f12; padding: 8px; border-radius: 8px; border: 1px solid #292d3e; }
        .race-cell { padding: 8px 0; text-align: center; font-size: 11px; font-weight: bold; border-radius: 4px; opacity: 0.25; transition: all 0.3s; }
        .race-cell.active-target { opacity: 1 !important; transform: scale(1.1); border: 2px solid #ffd700; box-shadow: 0 0 8px #ffd700; z-index: 2; }
        .race-cell.main-target { opacity: 1 !important; transform: scale(1.2); border: 2px solid #00ff88; box-shadow: 0 0 10px #00ff88; z-index: 3; }
    </style>
</head>
<body>

<div class="container">
    <div class="header-card">
        <div class="title">🎯 IMMERSIVE SNIPER AUTO</div>
        <div id="status">Aguardando Coletor...</div>
        
        <div class="score-board">
            <span class="score-item green-text">GREENS: <span id="greens-cnt">0</span></span>
            <span class="score-item red-text">REDS: <span id="reds-cnt">0</span></span>
        </div>
    </div>

    <div class="header-card">
        <div id="ball" class="ball" style="display:none">0</div>
    </div>

    <div id="alert-box" class="pulse">
        <h3 style="color: #ffd700; font-size: 15px;">🎯 SINAL CONFIRMADO (3 VIZINHOS)</h3>
        <p id="msg-sniper" style="font-size: 14px; font-weight: bold; margin-top: 5px; color: #fff;"></p>
    </div>

    <div class="header-card">
        <div class="section-title">Últimos Resultados</div>
        <div class="history" id="history"></div>
    </div>

    <div class="header-card">
        <div class="section-title">Racetrack (Alvos + Vizinhos)</div>
        <div class="racetrack-grid" id="racetrack"></div>
    </div>
</div>

<script>
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const WS_URL = `${protocol}//${window.location.host}/ws`;
    const socket = new WebSocket(WS_URL);
    const redNumbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36];

    const racetrackDiv = document.getElementById('racetrack');
    for (let i = 0; i <= 36; i++) {
        const cell = document.createElement('div');
        cell.id = `race-${i}`;
        cell.className = `race-cell ${getColorClass(i)}`;
        cell.innerText = i;
        racetrackDiv.appendChild(cell);
    }

    socket.onopen = () => {
        const st = document.getElementById('status');
        st.innerText = "SISTEMA ONLINE - MONITORE DE PRONTIDÃO";
        st.classList.add('online');
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.ultimo_numero !== undefined) {
            const ball = document.getElementById('ball');
            ball.style.display = "flex";
            ball.innerText = data.ultimo_numero;
            ball.className = `ball ${getColorClass(data.ultimo_numero)}`;

            if (data.placar) {
                document.getElementById('greens-cnt').innerText = data.placar.greens;
                document.getElementById('reds-cnt').innerText = data.placar.reds;
            }

            document.querySelectorAll('.race-cell').forEach(c => {
                c.classList.remove('active-target');
                c.classList.remove('main-target');
            });

            const alertBox = document.getElementById('alert-box');
            if (data.alerta) {
                alertBox.style.display = "block";
                document.getElementById('msg-sniper').innerText = data.mensagem;
                
                // Marca a cobertura total (Vizinhos em Amarelo)
                data.sugestoes.forEach(num => {
                    const targetCell = document.getElementById(`race-${num}`);
                    if (targetCell) targetCell.classList.add('active-target');
                });

                // Destaque Verde nos Alvos Principais
                if (data.alvos_principais) {
                    data.alvos_principais.forEach(num => {
                        const mainCell = document.getElementById(`race-${num}`);
                        if (mainCell) mainCell.classList.add('main-target');
                    });
                }
            } else {
                alertBox.style.display = "none";
            }

            const histDiv = document.getElementById('history');
            histDiv.innerHTML = "";
            data.historico.forEach(num => {
                const item = document.createElement('div');
                item.className = `hist-item ${getColorClass(num)}`;
                item.innerText = num;
                histDiv.appendChild(item);
            });
        }
    };

    function getColorClass(num) {
        if (num === 0) return 'green';
        return redNumbers.includes(num) ? 'red' : 'black';
    }
</script>
</body>
</html>
"""

# ==========================================
# 6. ROTAS DE API
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
