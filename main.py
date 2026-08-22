import asyncio
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI(title="Sniper Roulette Engine - Pro")

# ==========================================
# 1. MATRIZ DE ESTRATÉGIAS ("Puxadas")
# ==========================================
MATRIZ_PUXADAS: Dict[int, List[int]] = {
    10: [12, 35, 3, 26],
    20: [1, 14, 31, 9],
    0:  [26, 32, 15, 19],
    7:  [18, 29, 28, 12],
    14: [1, 20, 31, 9]
}

historico_rodadas: List[int] = []
placar = {"greens": 0, "reds": 0}

# ==========================================
# 2. GERENCIADOR DE WEBSOCKETS
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
# 3. MOTOR DE ANÁLISE E ESTATÍSTICAS
# ==========================================
RED_NUMBERS = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]

def calcular_estatisticas(historico: List[int]) -> dict:
    if not historico:
        return {"red_pct": 0, "black_pct": 0, "even_pct": 0, "odd_pct": 0}
    
    total = len(historico)
    reds = sum(1 for n in historico if n in RED_NUMBERS)
    blacks = sum(1 for n in historico if n != 0 and n not in RED_NUMBERS)
    evens = sum(1 for n in historico if n != 0 and n % 2 == 0)
    odds = sum(1 for n in historico if n % 2 != 0)

    return {
        "red_pct": round((reds / total) * 100),
        "black_pct": round((blacks / total) * 100),
        "even_pct": round((evens / total) * 100),
        "odd_pct": round((odds / total) * 100)
    }

def processar_numero(numero: int) -> dict:
    # Checa se o resultado anterior bateu com o sinal enviado
    sugestoes_anteriores = MATRIZ_PUXADAS.get(historico_rodadas[0], []) if historico_rodadas else []
    if sugestoes_anteriores:
        if numero in sugestoes_anteriores:
            placar["greens"] += 1
        else:
            placar["reds"] += 1

    historico_rodadas.insert(0, numero)
    if len(historico_rodadas) > 20:
        historico_rodadas.pop()

    sugestoes = MATRIZ_PUXADAS.get(numero, [])
    stats = calcular_estatisticas(historico_rodadas)

    return {
        "tipo": "NOVA_RODADA",
        "ultimo_numero": numero,
        "historico": historico_rodadas,
        "alerta": len(sugestoes) > 0,
        "sugestoes": sugestoes,
        "mensagem": f"ALVO SNIPER: Apostar nos números {sugestoes}" if sugestoes else "Analisando padrões...",
        "stats": stats,
        "placar": placar
    }

# ==========================================
# 4. DASHBOARD HTML PRO
# ==========================================
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sniper Roulette - Dashboard Pro</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background-color: #0d0f12; color: #e1e1e6; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; display: flex; justify-content: center; padding: 15px; }
        .container { width: 100%; max-width: 480px; display: flex; flex-direction: column; gap: 15px; }
        
        .header-card { background: #16181e; padding: 15px; border-radius: 12px; border: 1px solid #292d3e; text-align: center; }
        .title { font-size: 20px; font-weight: bold; color: #fff; letter-spacing: 1px; }
        #status { font-size: 11px; margin-top: 4px; color: #ff5555; text-transform: uppercase; font-weight: bold; }
        .online { color: #00ff88 !important; }

        /* Placar */
        .score-board { display: flex; justify-content: space-around; margin-top: 10px; background: #0d0f12; padding: 8px; border-radius: 8px; }
        .score-item { font-size: 13px; font-weight: bold; }
        .green-text { color: #00ff88; }
        .red-text { color: #ff5555; }

        /* Destaque do Número Sorteado */
        .last-number-box { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 15px; }
        .ball { width: 75px; height: 75px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 32px; font-weight: bold; border: 4px solid #ffffff22; box-shadow: 0 0 20px rgba(0,0,0,0.8); }
        .red { background: linear-gradient(145deg, #e63946, #b71c1c); color: #fff; }
        .black { background: linear-gradient(145deg, #2b2d42, #11111d); color: #fff; }
        .green { background: linear-gradient(145deg, #2a9d8f, #1b4332); color: #fff; }

        /* Alerta Sniper */
        #alert-box { background: linear-gradient(145deg, #221f10, #141208); border: 2px solid #ffd700; padding: 15px; border-radius: 12px; text-align: center; display: none; }
        .pulse { animation: pulse-gold 1.5s infinite; }
        @keyframes pulse-gold { 0% { box-shadow: 0 0 0 0 rgba(255, 215, 0, 0.6); } 70% { box-shadow: 0 0 0 12px rgba(255, 215, 0, 0); } }

        /* Histórico */
        .section-title { font-size: 12px; color: #828a9e; text-transform: uppercase; margin-bottom: 8px; font-weight: bold; }
        .history { display: flex; gap: 6px; overflow-x: auto; padding-bottom: 5px; }
        .hist-item { min-width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: bold; }

        /* Racetrack (Mesa Vetorial) */
        .racetrack-grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 3px; background: #0d0f12; padding: 8px; border-radius: 8px; border: 1px solid #292d3e; }
        .race-cell { padding: 8px 0; text-align: center; font-size: 11px; font-weight: bold; border-radius: 4px; opacity: 0.4; transition: all 0.3s; }
        .race-cell.active-target { opacity: 1 !important; transform: scale(1.15); border: 2px solid #ffd700; box-shadow: 0 0 10px #ffd700; z-index: 2; }

        /* Estatísticas */
        .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .stat-card { background: #16181e; padding: 10px; border-radius: 8px; border: 1px solid #292d3e; font-size: 12px; }
        .stat-bar-bg { background: #0d0f12; height: 8px; border-radius: 4px; overflow: hidden; margin-top: 5px; display: flex; }
        .stat-bar-fill { height: 100%; transition: width 0.5s; }
    </style>
</head>
<body>

<div class="container">
    <!-- Header & Placar -->
    <div class="header-card">
        <div class="title">🎯 IMMERSIVE SNIPER</div>
        <div id="status">Desconectado</div>
        
        <div class="score-board">
            <span class="score-item green-text">GREENS: <span id="greens-cnt">0</span></span>
            <span class="score-item red-text">REDS: <span id="reds-cnt">0</span></span>
        </div>
    </div>

    <!-- Número Atual -->
    <div class="header-card last-number-box">
        <div id="ball" class="ball" style="display:none">0</div>
    </div>

    <!-- Caixa de Alerta -->
    <div id="alert-box" class="pulse">
        <h3 style="color: #ffd700; font-size: 16px; margin-bottom: 5px;">🎯 SINAL SNIPER CONFIRMADO</h3>
        <p id="msg-sniper" style="font-size: 14px; font-weight: bold; color: #fff;"></p>
    </div>

    <!-- Histórico Recente -->
    <div class="header-card">
        <div class="section-title">Últimos Resultados</div>
        <div class="history" id="history"></div>
    </div>

    <!-- Estatísticas -->
    <div class="stats-grid">
        <div class="stat-card">
            <div>Vermelho x Preto</div>
            <div class="stat-bar-bg">
                <div id="bar-red" class="stat-bar-fill" style="width: 50%; background: #e63946;"></div>
                <div id="bar-black" class="stat-bar-fill" style="width: 50%; background: #2b2d42;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 3px; font-size: 10px;">
                <span id="txt-red" style="color: #e63946;">50%</span>
                <span id="txt-black" style="color: #a0a0a0;">50%</span>
            </div>
        </div>
        <div class="stat-card">
            <div>Par x Ímpar</div>
            <div class="stat-bar-bg">
                <div id="bar-even" class="stat-bar-fill" style="width: 50%; background: #00ff88;"></div>
                <div id="bar-odd" class="stat-bar-fill" style="width: 50%; background: #ffaa00;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 3px; font-size: 10px;">
                <span id="txt-even" style="color: #00ff88;">50%</span>
                <span id="txt-odd" style="color: #ffaa00;">50%</span>
            </div>
        </div>
    </div>

    <!-- Racetrack Visual -->
    <div class="header-card">
        <div class="section-title">Mapa da Roleta (Alvos)</div>
        <div class="racetrack-grid" id="racetrack"></div>
    </div>
</div>

<script>
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const WS_URL = `${protocol}//${window.location.host}/ws`;
    const socket = new WebSocket(WS_URL);

    const redNumbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36];

    // Gerar Racetrack
    const racetrackDiv = document.getElementById('racetrack');
    for (let i = 0; i <= 36; i++) {
        const cell = document.createElement('div');
        cell.id = `race-${i}`;
        cell.className = `race-cell ${getColorClass(i)}`;
        cell.innerText = i;
        cell.style.opacity = "0.6";
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
            // Atualiza Bola Principal
            const ball = document.getElementById('ball');
            ball.style.display = "flex";
            ball.innerText = data.ultimo_numero;
            ball.className = `ball ${getColorClass(data.ultimo_numero)}`;

            // Atualiza Placar
            if (data.placar) {
                document.getElementById('greens-cnt').innerText = data.placar.greens;
                document.getElementById('reds-cnt').innerText = data.placar.reds;
            }

            // Limpa alvos no Racetrack
            document.querySelectorAll('.race-cell').forEach(c => c.classList.remove('active-target'));

            // Atualiza Alerta e destaca alvos no Racetrack
            const alertBox = document.getElementById('alert-box');
            if (data.alerta) {
                alertBox.style.display = "block";
                document.getElementById('msg-sniper').innerText = data.mensagem;
                data.sugestoes.forEach(num => {
                    const targetCell = document.getElementById(`race-${num}`);
                    if (targetCell) targetCell.classList.add('active-target');
                });
            } else {
                alertBox.style.display = "none";
            }

            // Atualiza Histórico
            const histDiv = document.getElementById('history');
            histDiv.innerHTML = "";
            data.historico.forEach(num => {
                const item = document.createElement('div');
                item.className = `hist-item ${getColorClass(num)}`;
                item.innerText = num;
                histDiv.appendChild(item);
            });

            // Atualiza Barras de Estatística
            if (data.stats) {
                document.getElementById('bar-red').style.width = `${data.stats.red_pct}%`;
                document.getElementById('bar-black').style.width = `${data.stats.black_pct}%`;
                document.getElementById('txt-red').innerText = `${data.stats.red_pct}% Vermelho`;
                document.getElementById('txt-black').innerText = `${data.stats.black_pct}% Preto`;

                document.getElementById('bar-even').style.width = `${data.stats.even_pct}%`;
                document.getElementById('bar-odd').style.width = `${data.stats.odd_pct}%`;
                document.getElementById('txt-even').innerText = `${data.stats.even_pct}% Par`;
                document.getElementById('txt-odd').innerText = `${data.stats.odd_pct}% Ímpar`;
            }
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
# 5. ROTAS DA APLICAÇÃO
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
