import asyncio
from typing import List, Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.responses import HTMLResponse

app = FastAPI(title="Sniper Roulette Engine - Auto Dynamic Strategy")

# ==========================================
# 1. RACETRACK EUROPEIA E VIZINHOS
# ==========================================
RACETRACK_EUROPEIA = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
    5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

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
# 2. FAMÍLIAS DE ESTRATÉGIAS DIVIDIDAS
# ==========================================
ESTRATEGIAS: Dict[str, Dict[int, List[int]]] = {
    "Estratégia dos Terminais do Zero / Voisins (0, 10, 20, 30)": {
        0: [20, 30, 10], 8: [30, 0, 20], 10: [0, 20, 30], 11: [30, 0, 20],
        20: [17, 7, 20], 23: [0, 10, 30], 26: [0, 10, 30], 30: [0, 20, 30], 32: [0, 10, 20]
    },
    "Estratégia do 3, 15, 25 e 33 (Família Ímpar Baixa)": {
        3: [3, 33], 5: [25, 15, 35], 12: [33, 15], 15: [9, 5, 35],
        16: [3, 33], 24: [35, 15, 25], 33: [3, 33], 35: [3, 33, 15]
    },
    "Estratégia do 7, 17 e 20 (Setor Orphelins/Tier)": {
        1: [17, 7], 6: [20, 17, 7], 7: [7, 17, 20], 13: [20, 7], 14: [17, 7],
        17: [17, 20, 7], 27: [17, 7, 20], 28: [7, 17, 20], 29: [7, 17, 20], 34: [7, 20]
    },
    "Estratégia do 2 e 22 (Duplas Espelhadas)": {
        2: [2, 22], 18: [2, 22], 21: [2, 22], 22: [2, 22], 25: [20, 22]
    },
    "Estratégia do 9 e 19 (Terminais de 9)": {
        4: [21, 9], 9: [9, 19], 19: [19, 9], 31: [9, 19]
    }
}

historico_rodadas: List[int] = []
placar_geral = {"greens": 0, "reds": 0}
ultimos_alvos_cobertura: Set[int] = set()

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
# 3. MOTOR DE BACKTEST AUTOMÁTICO (100 RODADAS)
# ==========================================
def avaliar_estratégia(nome_estratégia: str, matriz: Dict[int, List[int]], historico: List[int]) -> dict:
    wins = 0
    losses = 0
    total = 0
    
    # Avalia do número mais antigo para o mais recente no histórico (até 100 rodadas)
    sub_hist = list(reversed(historico[:100]))
    for i in range(len(sub_hist) - 1):
        num_atual = sub_hist[i]
        num_proximo = sub_hist[i+1]
        
        alvos = matriz.get(num_atual, [])
        if alvos:
            cobertura = set()
            for a in alvos:
                cobertura.update(obter_vizinhos_racetrack(a, raio=3))
            
            total += 1
            if num_proximo in cobertura:
                wins += 1
            else:
                losses += 1
                
    taxa_win = round((wins / total * 100), 1) if total > 0 else 0.0
    return {
        "nome": nome_estratégia,
        "wins": wins,
        "losses": losses,
        "total": total,
        "assertividade": taxa_win
    }

def processar_numero(numero: int) -> dict:
    global ultimos_alvos_cobertura
    
    # 1. Valida resultado da rodada anterior
    resultado_rodada = "SEM_SINAL"
    if ultimos_alvos_cobertura:
        if numero in ultimos_alvos_cobertura:
            placar_geral["greens"] += 1
            resultado_rodada = "WIN"
        else:
            placar_geral["reds"] += 1
            resultado_rodada = "RED"

    historico_rodadas.insert(0, numero)
    if len(historico_rodadas) > 100:
        historico_rodadas.pop()

    # 2. Executa Backtest de todas as estratégias nos últimos 100 números
    ranking_estratégias = []
    for nome, matriz in ESTRATEGIAS.items():
        res = avaliar_estratégia(nome, matriz, historico_rodadas)
        ranking_estratégias.append(res)
        
    # Ordena para pegar a melhor estratégia no topo
    ranking_estratégias.sort(key=lambda x: x["assertividade"], reverse=True)
    melhor_estratégia = ranking_estratégias[0] if ranking_estratégias else None

    # 3. Pega os alvos do novo número baseado na MELHOR estratégia ativa
    alvos_principais = []
    cobertura_total: Set[int] = set()
    
    if melhor_estratégia and melhor_estratégia["assertividade"] > 0:
        matriz_ativa = ESTRATEGIAS[melhor_estratégia["nome"]]
        alvos_principais = matriz_ativa.get(numero, [])
        for alvo in alvos_principais:
            cobertura_total.update(obter_vizinhos_racetrack(alvo, raio=3))

    ultimos_alvos_cobertura = cobertura_total.copy()

    return {
        "tipo": "NOVA_RODADA",
        "ultimo_numero": numero,
        "resultado_rodada": resultado_rodada,
        "historico": historico_rodadas,
        "alerta": len(alvos_principais) > 0,
        "alvos_principais": alvos_principais,
        "sugestoes": list(cobertura_total),
        "melhor_estratégia": melhor_estratégia["nome"] if melhor_estratégia else "NENHUMA",
        "ranking": ranking_estratégias,
        "mensagem": f"ENTRAR NOS ALVOS {alvos_principais} + 3 VIZINHOS" if alvos_principais else "AGUARDANDO GATILHO DA MELHOR ESTRATÉGIA",
        "placar": placar_geral
    }

# ==========================================
# 4. DASHBOARD FRONTEND HTML (Injetado via App)
# ==========================================
# (Aguardando o seu index.html customizado para substituição)

# ==========================================
# 5. ROTAS DE API
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def home():
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Arquivo index.html não encontrado na pasta templates/</h1>"

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

@app.post("/injetar-lote")
async def injetar_lote(payload: dict = Body(...)):
    """
    Injeta múltiplos números de uma só vez (ex: "15, 32, 0, 12, 5" ou "15 32 0 12")
    """
    raw_text = payload.get("numeros", "")
    try:
        cleaned_text = raw_text.replace(',', ' ').replace(';', ' ').replace('\n', ' ')
        numeros = [int(n) for n in cleaned_text.split() if n.strip().isdigit()]
        validos = [n for n in numeros if 0 <= n <= 36]
        
        # Limpa histórico antigo e reinicia placar para a nova análise dos 100 números
        global historico_rodadas, placar_geral, ultimos_alvos_cobertura
        historico_rodadas = []
        placar_geral = {"greens": 0, "reds": 0}
        ultimos_alvos_cobertura = set()
        
        # Processa do mais antigo para o mais recente
        dados_finais = None
        for num in validos:
            dados_finais = processar_numero(num)
            
        if dados_finais:
            await manager.broadcast(dados_finais)
            return {"status": "sucesso", "total_processado": len(validos), "dados": dados_finais}
            
        return {"status": "erro", "mensagem": "Nenhum número válido encontrado na sequência."}
    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}
