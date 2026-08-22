import asyncio
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI(title="Sniper Roulette Engine - Auto")

# ==========================================
# 1. REGRAS AVANÇADAS (Puxadas e Terminais)
# ==========================================
MATRIZ_PUXADAS: Dict[int, List[int]] = {
    0:  [26, 32, 15, 19], 1:  [20, 14, 31, 9],  2:  [21, 25, 17, 34],
    3:  [26, 35, 12, 0],  4:  [15, 19, 21, 2],  5:  [10, 23, 24, 16],
    6:  [27, 13, 36, 11], 7:  [18, 29, 28, 12], 8:  [11, 30, 23, 10],
    9:  [31, 14, 1, 20],  10: [12, 35, 3, 26],  11: [36, 13, 30, 8],
    12: [35, 3, 26, 0],   13: [27, 6, 36, 11],  14: [1, 20, 31, 9],
    15: [19, 4, 21, 2],   16: [24, 5, 10, 23],  17: [25, 2, 21, 34],
    18: [29, 7, 28, 12],  19: [15, 4, 21, 2],   20: [1, 14, 31, 9],
    21: [2, 25, 17, 34],  22: [9, 18, 29, 31],  23: [10, 5, 24, 16],
    24: [16, 5, 10, 23],  25: [17, 2, 21, 34],  26: [0, 32, 15, 3],
    27: [6, 13, 36, 11],  28: [12, 18, 29, 7],  29: [18, 7, 28, 12],
    30: [8, 11, 36, 13],  31: [9, 14, 1, 20],   32: [0, 26, 15, 19],
    33: [16, 24, 5, 10],  34: [17, 25, 2, 21],  35: [3, 12, 26, 0],
    36: [11, 13, 27, 6]
}

historico_rodadas: List[int] = []
placar = {"greens": 0, "reds": 0}

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

# Detecta repetição de finais (Terminais)
def analisar_terminais(historico: List[int]) -> List[int]:
    if len(historico) < 2:
        return []
    
    ultimo = historico[0]
    penultimo = historico[1]
    
    final_ultimo = ultimo % 10
    final_penultimo = penultimo % 10
    
    # Se os dois últimos tiverem o mesmo final, sugere a família do terminal
    if final_ultimo == final_penultimo:
        return [f for f in range(37) if f % 10 == final_ultimo and f not in [ultimo, penultimo]]
    return []

def processar_numero(numero: int) -> dict:
    sugestoes_anteriores = MATRIZ_PUXADAS.get(historico_rodadas[0], []) if historico_rodadas else []
    if sugestoes_anteriores:
        if numero in sugestoes_anteriores:
            placar["greens"] += 1
        else:
            placar["reds"] += 1

    historico_rodadas.insert(0, numero)
    if len(historico_rodadas) > 20:
        historico_rodadas.pop()

    # Combina Puxadas + Terminais
    puxadas = MATRIZ_PUXADAS.get(numero, [])
    terminais = analisar_terminais(historico_rodadas)
    
    alvos_unicos = list(set(puxadas + terminais))
    
    padrao_detectado = "NENHUM"
    if terminais and puxadas:
        padrao_detectado = "PUXADA + TERMINAL REPETIDOR"
    elif terminais:
        padrao_detectado = "TERMINAL REPETIDOR"
    elif puxadas:
        padrao_detectado = "NÚMERO PUXA NÚMERO"

    return {
        "tipo": "NOVA_RODADA",
        "ultimo_numero": numero,
        "historico": historico_rodadas,
        "alerta": len(alvos_unicos) > 0,
        "sugestoes": alvos_unicos,
        "padrao": padrao_detectado,
        "mensagem": f"ALVOS: {alvos_unicos}",
        "placar": placar
    }

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
        .race-cell { padding: 8px 0; text-align: center; font-size: 11px; font-weight: bold; border-radius: 4px; opacity: 0.4; }
        .race-cell.active-target { opacity: 1 !important; transform: scale(1.15); border: 2px solid #ffd700; box-shadow: 0 0 10px #ffd700; z-index: 2; }
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
        <h3 style="color: #ffd700; font-size: 15px;" id="padrao-txt">🎯 SINAL CONFIRMADO</h3>
        <p id="msg-sniper" style="font-size: 14px; font-weight: bold; margin-top: 5px;"></p>
    </div>

    <div class="header-card">
        <div class="section-title">Histórico de Leitura ao Vivo</div>
        <div class="history" id="history"></div>
    </div>

    <div class="header-card">
        <div class="section-title">Alvos Mapeados na Roleta</div>
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
        st.innerText = "MONITORANDO EM TEMPO REAL";
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

            document.querySelectorAll('.race-cell').forEach(c => c.classList.remove('active-target'));

            const alertBox = document.getElementById('alert-box');
            if (data.alerta) {
                alertBox.style.display = "block";
                document.getElementById('padrao-txt').innerText = `🎯 PADRÃO: ${data.padrao}`;
                document.getElementById('msg-sniper').innerText = data.mensagem;
                data.sugestoes.forEach(num => {
                    const targetCell = document.getElementById(`race-${num}`);
                    if (targetCell) targetCell.classList.add('active-target');
                });
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
