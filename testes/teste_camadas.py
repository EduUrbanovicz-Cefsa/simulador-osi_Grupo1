"""Confere as sete camadas sobre a topologia real de topologia.json.

Aqui o proprio teste faz o papel das pilhas dos dispositivos e do meio
fisico, levando cada unidade de camada em camada e cada quadro de salto em
salto. Alem dos tamanhos pedidos (42 -> 92 e a segmentacao 40/40/24),
confere a remontagem no destino, o caso central E2 com a linha 011 do log da
especificacao, os casos E5 e E6, o tamanho em octetos de texto acentuado e o
formato do registro.

Executar com:  python testes/teste_camadas.py
"""

import itertools
import os
import sys
import tempfile
from dataclasses import replace

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from simulador.camadas import (  # noqa: E402
    Aplicacao, Apresentacao, Contexto, Enlace, Fisica, Rede, Sessao, Transporte,
)
from simulador.pdu import PDU  # noqa: E402
from simulador.rede import Topologia  # noqa: E402
from simulador.registro import Registro  # noqa: E402

MENSAGEM_42 = "Ola H2, aqui e o H1 testando a pilha OSI!!"
MENSAGEM_100 = ("Mensagem longa que precisa ser segmentada. " * 3)[:100]


def computador():
    return [Aplicacao(), Apresentacao(), Sessao(), Transporte(), Rede(), Enlace(), Fisica()]


def roteador():
    # R1 por estrutura: o roteador nao tem as camadas 4 a 7.
    return [Rede(), Enlace(), Fisica()]


class Simulacao:
    """Pilhas, meio fisico e registro, so para este teste."""

    def __init__(self):
        self.topologia = Topologia.carregar()
        self.registro = Registro()
        self.quadros = []  # cada quadro na forma em que entrou em um enlace
        self._contextos, self._pilhas = {}, {}
        self._passos, self._numeros = itertools.count(1), itertools.count(1)

    def contexto(self, nome):
        if nome not in self._contextos:
            self._contextos[nome] = Contexto(
                nome, self.topologia, passos=self._passos, quadros=self._numeros,
            )
            eh_roteador = nome in self.topologia.roteadores
            self._pilhas[nome] = roteador() if eh_roteador else computador()
        return self._contextos[nome]

    def passar(self, sentido, nome, unidades, ate=None):
        """Leva as unidades pela pilha de um dispositivo; devolve saida e tamanhos."""
        contexto = self.contexto(nome)
        camadas = self._pilhas[nome][:ate]
        if sentido == "subir":
            camadas = list(reversed(camadas))
        tamanhos = []
        for camada in camadas:
            saidas = []
            for unidade in unidades:
                novas, eventos = getattr(camada, sentido)(unidade, contexto)
                saidas.extend(novas)
                self.registro.registrar(eventos)
            unidades = saidas
            tamanhos.append([u.tamanho for u in unidades])
        return unidades, tamanhos

    def enviar(self, origem, destino, texto, corromper=None):
        """Leva a mensagem ate o destino, salto a salto.

        corromper = (n, funcao) aplica a funcao ao quadro do n-esimo enlace.
        Devolve o que chegou a camada 7 do destino.
        """
        self.contexto(origem).destino = destino
        quadros, _ = self.passar("descer", origem, [PDU(dados=texto)])
        entregue = []
        for quadro in quadros:
            atual = self.contexto(origem).proximo_salto
            while True:
                self.quadros.append(quadro)
                if corromper and len(self.quadros) == corromper[0]:
                    quadro = corromper[1](quadro)
                if atual not in self.topologia.roteadores:
                    entregue += self.passar("subir", atual, [quadro])[0]
                    break
                pacotes, _ = self.passar("subir", atual, [quadro])
                seguintes, _ = self.passar("descer", atual, pacotes)
                if not seguintes:
                    break
                quadro, atual = seguintes[0], self.contexto(atual).proximo_salto
        return entregue

    def eventos(self, **filtro):
        return [e for e in self.registro.eventos
                if all(getattr(e, k) == v for k, v in filtro.items())]


def imprimir(linhas):
    for linha in linhas:
        print(f"   {linha}")


def inverter_bit_no_destino_logico(quadro):
    """Erro de bit que cai no cabecalho da camada 3, e nao nos dados."""
    cabecalho = quadro.cabecalho_da_camada(3)
    destino = cabecalho.campos["destino"]
    alterado = destino[:-1] + chr(ord(destino[-1]) ^ 0x01)
    novo = replace(cabecalho, campos={**cabecalho.campos, "destino": alterado})
    return replace(quadro, cabecalhos=tuple(
        novo if c is cabecalho else c for c in quadro.cabecalhos
    ))


# ----------------------------------------------------------------------
# Casos
# ----------------------------------------------------------------------

def caso_tamanhos_42():
    sim = Simulacao()
    sim.contexto("H1").destino = "10.0.1.11"
    _, tamanhos = sim.passar("descer", "H1", [PDU(dados=MENSAGEM_42)])
    imprimir(sim.registro.linhas())

    por_camada = [t[0] for t in tamanhos]
    esperado = [42, 42, 46, 54, 74, 92]
    print(f"   L7..L2: {por_camada[:6]}  (esperado {esperado});  L1: {por_camada[6]} B")
    linha_004 = sim.registro.linhas()[3]
    print(f"   linha 004 e SEGMENTA: {linha_004.startswith('004 | H1 | L4 | SEGMENTA | ')}")
    return (por_camada[:6] == esperado and por_camada[6] == 92
            and linha_004.startswith("004 | H1 | L4 | SEGMENTA | ")
            and linha_004.endswith(" 54 B"))


def caso_segmentacao_100():
    sim = Simulacao()
    segmentos, _ = sim.passar("descer", "H1", [PDU(dados=MENSAGEM_100)], ate=4)
    imprimir(sim.registro.linhas())

    cabecalho_l4 = sim.topologia.convencoes["cabecalhos"]["4"]
    cargas = [s.tamanho - cabecalho_l4 for s in segmentos]
    acoes_l4 = [e.acao for e in sim.eventos(camada=4)]
    print(f"   carga dos segmentos: {cargas}  (esperado [40, 40, 24]);"
          f"  com cabecalho L4: {[s.tamanho for s in segmentos]}")
    return cargas == [40, 40, 24] and acoes_l4 == ["SEGMENTA"] * 3


def caso_remontagem_100():
    sim = Simulacao()
    entregue = sim.enviar("H1", "10.0.1.11", MENSAGEM_100)
    imprimir(sim.registro.linhas()[-6:])

    l4_h2 = [e.acao for e in sim.eventos(dispositivo="H2", camada=4)]
    ok = (l4_h2 == ["RECEBE", "RECEBE", "REMONTA"]
          and len(entregue) == 1 and entregue[0].dados == MENSAGEM_100
          and sim.contexto("H2").processo == "servidorWeb")
    print(f"   L4 em H2: {l4_h2};  entregue a '{sim.contexto('H2').processo}': {ok}")
    return ok


def caso_central_e2():
    sim = Simulacao()
    entregue = sim.enviar("H1", "10.0.3.10", MENSAGEM_42)
    imprimir(sim.registro.linhas())

    quadros = sim.quadros
    for q in quadros:
        print(f"   {q.numero_quadro}: {q.fisicos[0]} -> {q.fisicos[1]}   "
              f"logicos {q.logicos[0]} -> {q.logicos[1]}   portas {q.portas}   {q.tamanho} B")

    linha_011 = sim.registro.linhas()[10]
    esperado_011 = "011 | R1 | L3 | ROTEIA | 10.0.3.0/24 via R4, custo 2, interface e1"
    r2 = (len({id(q) for q in quadros}) == 4
          and len({q.numero_quadro for q in quadros}) == 4
          and len({q.fisicos for q in quadros}) == 4)
    r3 = len({q.logicos for q in quadros}) == 1
    portas = all(q.portas == (5210, 443) for q in quadros)
    entrega = (len(entregue) == 1 and entregue[0].dados == MENSAGEM_42
               and sim.contexto("H4").processo == "servidorWeb")
    total = sum(q.tamanho for q in quadros)
    print(f"   linha 011 confere: {linha_011.startswith(esperado_011)};  R2: {r2};  R3: {r3};"
          f"  portas 5210->443: {portas};  entregue: {entrega};  {total} octetos (esperado 368)")
    return linha_011.startswith(esperado_011) and r2 and r3 and portas and entrega and total == 368


def caso_inalcancavel_e5():
    sim = Simulacao()
    entregue = sim.enviar("H1", "10.0.9.10", MENSAGEM_42)
    imprimir(sim.registro.linhas()[-4:])
    ultimo = sim.registro.eventos[-1]
    total = sum(q.tamanho for q in sim.quadros)
    print(f"   quadros: {len(sim.quadros)};  {total} octetos (esperado 92)")
    return (entregue == [] and len(sim.quadros) == 1 and total == 92
            and (ultimo.dispositivo, ultimo.camada, ultimo.acao) == ("R1", 3, "DESCARTA"))


def caso_erro_de_bit_e6():
    sim = Simulacao()
    entregue = sim.enviar("H1", "10.0.3.10", MENSAGEM_42,
                          corromper=(3, inverter_bit_no_destino_logico))
    imprimir(sim.registro.linhas()[-3:])
    ultimo = sim.registro.eventos[-1]
    total = sum(q.tamanho for q in sim.quadros)
    print(f"   bit invertido no cabecalho L3 do 3o enlace;  quadros: {len(sim.quadros)};"
          f"  {total} octetos (esperado 276)")
    return (entregue == [] and len(sim.quadros) == 3 and total == 276
            and (ultimo.dispositivo, ultimo.camada, ultimo.acao) == ("R3", 2, "DESCARTA"))


def caso_texto_acentuado():
    sim = Simulacao()
    texto = "Olá, H2! Comunicação de Dados"
    octetos = len(texto.encode("utf-8"))
    sim.enviar("H1", "10.0.1.11", texto)
    gera = sim.eventos(acao="GERA")[0].tamanho
    codifica = sim.eventos(acao="CODIFICA")[0].tamanho
    entrega = sim.eventos(camada=7, acao="ENTREGA")[0].tamanho
    print(f"   {len(texto)} caracteres, {octetos} octetos;  "
          f"L7 GERA {gera} B, L6 CODIFICA {codifica} B, L7 ENTREGA {entrega} B")
    return gera == codifica == entrega == octetos


def caso_registro_em_arquivo():
    sim = Simulacao()
    sim.enviar("H1", "10.0.1.11", MENSAGEM_42)
    with tempfile.TemporaryDirectory() as pasta:
        caminho = os.path.join(pasta, "registro.txt")
        sim.registro.salvar_em_arquivo(caminho)
        with open(caminho, encoding="utf-8") as arquivo:
            gravadas = arquivo.read().splitlines()
    formato = all(
        len(partes := linha.split(" | ", 4)) == 5
        and len(partes[0]) == 3 and partes[0].isdigit()
        and partes[2].startswith("L") and linha.endswith(" B")
        for linha in gravadas
    )
    print(f"   {len(gravadas)} linhas gravadas;  iguais ao registro: "
          f"{gravadas == sim.registro.linhas()};  formato NNN | DISP | LN | ACAO | ... TAM B: {formato}")
    return gravadas == sim.registro.linhas() and formato and gravadas[0].startswith("001 | H1 | L7 | GERA | ")


CASOS = [
    ("descida de 42 octetos (E1)", caso_tamanhos_42),
    ("segmentacao de 100 octetos", caso_segmentacao_100),
    ("remontagem no destino", caso_remontagem_100),
    ("caso central E2: H1 -> R1 -> R4 -> R3 -> H4", caso_central_e2),
    ("E5 destino inalcancavel", caso_inalcancavel_e5),
    ("E6 erro de bit em cabecalho", caso_erro_de_bit_e6),
    ("L7 reporta octetos, nao caracteres", caso_texto_acentuado),
    ("registro salvo em arquivo", caso_registro_em_arquivo),
]


def executar():
    falhas = 0
    for nome, caso in CASOS:
        print(f"\n{nome}")
        passou = caso()
        falhas += 0 if passou else 1
        print(f"   -> {'ok' if passou else 'FALHOU'}")
    print("\n" + ("todos os casos conferem" if falhas == 0 else f"{falhas} caso(s) divergente(s)"))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(executar())
