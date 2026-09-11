"""Roda os sete cenarios pela Simulacao e confere o quadro resumo oficial.

Diferente de teste_convencoes.py, que refaz a conta com as convencoes, aqui
os numeros saem da execucao completa: pilhas, meio fisico e falhas. Alem da
tabela de validacao, confere a demultiplexacao de E3 (as duas mensagens
chegam intactas, cada uma a sua sessao, mesmo com os segmentos dos dois
fluxos intercalados em H4), a execucao passo a passo, os enderecos fisicos
de E2 e E4 e a ausencia das camadas 4 a 7 no roteador.

Executar com:  python testes/teste_cenarios.py
"""

import os
import sys
from dataclasses import replace

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from simulador.dispositivos import Computador, Roteador  # noqa: E402
from simulador.rede import Topologia  # noqa: E402
from simulador.simulador import CENARIOS, MENSAGEM_E7, Simulacao  # noqa: E402

TOPOLOGIA = Topologia.carregar()

# Tabela de validacao oficial: quadros, octetos transmitidos e eficiencia em
# porcentagem, ou None quando o cenario termina sem entrega.
TABELA = {
    "E1": (1, 92, 45.7),
    "E2": (4, 368, 11.4),
    "E3": (8, 736, 11.4),
    "E4": (4, 368, 11.4),
    "E5": (1, 92, None),
    "E6": (3, 276, None),
    "E7": (12, 968, 10.3),
}


def rodar(cenario):
    sim = Simulacao(TOPOLOGIA, cenario)
    sim.executar()
    return sim


# ----------------------------------------------------------------------
# Casos
# ----------------------------------------------------------------------

def caso_tabela_oficial():
    print(f"   {'Cenario':<26}{'Quadros':>8}{'Octetos':>9}{'Uteis':>7}{'Eficiencia':>12}"
          f"{'Sobrecarga':>12}")
    falhas = 0
    for codigo, cenario in CENARIOS.items():
        resumo = rodar(cenario).resumo()
        quadros_esp, octetos_esp, efic_esp = TABELA[codigo]
        efic = round(resumo.eficiencia * 100, 1)

        if efic_esp is None:
            ok_efic = resumo.octetos_uteis == 0 and resumo.eficiencia == 0
            exibida = "sem entrega"
        else:
            ok_efic = efic == efic_esp
            exibida = f"{efic:.1f}%"
        passou = (resumo.quadros == quadros_esp
                  and resumo.octetos_transmitidos == octetos_esp and ok_efic)
        falhas += 0 if passou else 1

        nome = f"{codigo} {cenario.nome}"
        print(f"   {nome:<26}{resumo.quadros:>8}{resumo.octetos_transmitidos:>9}"
              f"{resumo.octetos_uteis:>7}{exibida:>12}{resumo.sobrecarga * 100:>11.1f}%"
              f"   {'ok' if passou else 'FALHOU'}")
        if not passou:
            print(f"      esperado: {quadros_esp} quadros, {octetos_esp} octetos, {efic_esp}")
    return falhas == 0


def caso_mensagens_coerentes():
    """Cada mensagem cita o destino para onde vai e tem o tamanho de referencia."""
    ok = True
    for codigo, cenario in CENARIOS.items():
        esperado = 100 if codigo == "E7" else 42
        for fluxo in cenario.fluxos:
            destino = cenario.falhas.destino_inalcancavel or fluxo.destino
            octetos = len(fluxo.mensagem.encode("utf-8"))
            certo = octetos == esperado and destino in fluxo.mensagem
            ok = ok and certo
            print(f"   {codigo} {fluxo.origem} -> {destino:<10} {octetos:>3} octetos  "
                  f"{fluxo.mensagem[:44]!r}{'...' if len(fluxo.mensagem) > 44 else ''}"
                  f"{'' if certo else '   FALHOU'}")
    return ok


def caso_e3_demultiplexacao():
    cenario = CENARIOS["E3"]
    sim = rodar(cenario)
    for linha in sim.registro.linhas():
        if " | H4 | L4 | " in linha or " | H4 | L5 | " in linha or " | H4 | L7 | " in linha:
            print(f"   {linha}")

    obtidas = {(e.sessao, e.portas[0], e.logicos[0], e.processo, e.mensagem)
               for e in sim.entregas}
    esperadas = {
        ("S-0001", 5210, "10.0.1.10", "servidorWeb", cenario.fluxos[0].mensagem),
        ("S-0002", 6120, "10.0.1.11", "servidorWeb", cenario.fluxos[1].mensagem),
    }
    for e in sim.entregas:
        print(f"   entregue em {e.dispositivo}: sessao {e.sessao}, porta {e.portas[0]} -> "
              f"{e.portas[1]}, de {e.logicos[0]}: {e.mensagem!r}")
    distintas = cenario.fluxos[0].mensagem != cenario.fluxos[1].mensagem
    print(f"   duas entregas, cada mensagem na sua sessao e no seu fluxo: {obtidas == esperadas}")
    return len(sim.entregas) == 2 and obtidas == esperadas and distintas


def caso_e3_segmentos_intercalados():
    """E3 com mensagens de 100 octetos: tres segmentos por fluxo, alternados em H4.

    Aqui a separacao pela porta de origem e posta a prova: se a camada 4
    guardasse os segmentos em um unico conjunto, os de H2 completariam a
    mensagem de H1.
    """
    h1, h2 = CENARIOS["E3"].fluxos
    mensagem_h2 = MENSAGEM_E7.replace("H1", "H2")
    cenario = replace(CENARIOS["E3"], fluxos=(
        replace(h1, mensagem=MENSAGEM_E7), replace(h2, mensagem=mensagem_h2),
    ))
    sim = Simulacao(TOPOLOGIA, cenario)
    chegada = []
    while (evento := sim.passo()) is not None:
        if (evento.dispositivo, evento.camada) == ("H4", 4):
            chegada.append((evento.acao, sim.unidade.portas[0]))

    print(f"   L4 de H4, na ordem: {chegada}")
    alternados = [porta for _, porta in chegada] == [5210, 6120] * 3
    por_porta = {e.portas[0]: (e.sessao, e.mensagem) for e in sim.entregas}
    intactas = por_porta == {5210: ("S-0001", MENSAGEM_E7), 6120: ("S-0002", mensagem_h2)}
    print(f"   segmentos alternados: {alternados};  mensagens intactas e separadas: {intactas};"
          f"  {sim.resumo().quadros} quadros")
    return alternados and intactas and len(sim.entregas) == 2


def caso_passo_a_passo():
    sim = Simulacao(TOPOLOGIA, CENARIOS["E7"])
    numeros, terminou = [], []
    while (evento := sim.passo()) is not None:
        numeros.append(evento.passo)
        # Depois de cada evento: False em todos, True logo apos o ultimo.
        terminou.append(sim.terminou)
        if sim.unidade is None:
            print("   passo sem unidade associada")
            return False

    completa = rodar(CENARIOS["E7"])
    sequenciais = numeros == list(range(1, len(numeros) + 1))
    iguais = sim.registro.linhas() == completa.registro.linhas()
    so_no_fim = terminou == [False] * (len(terminou) - 1) + [True]
    print(f"   {len(numeros)} eventos pedidos um a um;  numeracao sequencial: {sequenciais};"
          f"  iguais a executar(): {iguais};  terminou exatamente no ultimo: {so_no_fim}")
    return sequenciais and iguais and so_no_fim and sim.passo() is None


def caso_e6_sem_camada_3_em_r3():
    sim = rodar(CENARIOS["E6"])
    for linha in sim.registro.linhas()[-3:]:
        print(f"   {linha}")
    em_r3 = [(e.camada, e.acao) for e in sim.eventos if e.dispositivo == "R3"]
    print(f"   eventos em R3: {em_r3}")
    return em_r3 == [(1, "RECEBE"), (2, "DESCARTA")] and sim.entregas == []


def caso_enderecos_fisicos_e2_e4():
    esperados = {
        "E2": [("AA:00:00:00:01:0A", "BB:00:00:00:01:00"),
               ("BB:00:00:00:01:01", "BB:00:00:00:04:00"),
               ("BB:00:00:00:04:01", "BB:00:00:00:03:00"),
               ("BB:00:00:00:03:02", "AA:00:00:00:03:0A")],
        "E4": [("AA:00:00:00:01:0A", "BB:00:00:00:01:00"),
               ("BB:00:00:00:01:02", "BB:00:00:00:02:00"),
               ("BB:00:00:00:02:01", "BB:00:00:00:03:01"),
               ("BB:00:00:00:03:02", "AA:00:00:00:03:0A")],
    }
    ok = True
    for codigo, pares in esperados.items():
        sim = rodar(CENARIOS[codigo])
        obtidos = [t.quadro.fisicos for t in sim.transmissoes]
        enlaces = " ".join(f"{t.de}-{t.para}" for t in sim.transmissoes)
        logicos = {t.quadro.logicos for t in sim.transmissoes}
        certo = obtidos == pares and len(logicos) == 1
        ok = ok and certo
        print(f"   {codigo}: {enlaces};  fisicos conferem: {obtidos == pares};"
              f"  par logico unico: {logicos}")
    return ok


def caso_roteador_sem_camadas_superiores():
    roteador = Roteador("R1", TOPOLOGIA)
    computador = Computador("H1", TOPOLOGIA)
    nomes = [type(c).__name__ for c in roteador.pilha]
    print(f"   R1: camadas {roteador.numeros_das_camadas} {nomes};"
          f"  H1: camadas {computador.numeros_das_camadas}")
    return (roteador.numeros_das_camadas == [3, 2, 1]
            and computador.numeros_das_camadas == [7, 6, 5, 4, 3, 2, 1])


def caso_falha_nao_vaza():
    rodar(CENARIOS["E4"])
    rota = TOPOLOGIA.rota_para("R1", "10.0.3.10")
    print(f"   depois de E4, a topologia recebida segue com R1 -> Rede C via {rota.proximo_salto};"
          f"  enlaces derrubados: {TOPOLOGIA.enlaces_derrubados or 'nenhum'}")
    return rota.proximo_salto == "R4" and not TOPOLOGIA.enlaces_derrubados


CASOS = [
    ("tabela de validacao oficial", caso_tabela_oficial),
    ("mensagens coerentes com o destino", caso_mensagens_coerentes),
    ("E3 demultiplexacao por porta", caso_e3_demultiplexacao),
    ("E3 com segmentos dos dois fluxos intercalados", caso_e3_segmentos_intercalados),
    ("execucao passo a passo", caso_passo_a_passo),
    ("E6 sem camada 3 em R3", caso_e6_sem_camada_3_em_r3),
    ("enderecos fisicos de E2 e E4", caso_enderecos_fisicos_e2_e4),
    ("roteador so com as camadas 3, 2 e 1", caso_roteador_sem_camadas_superiores),
    ("falha de enlace nao vaza para a topologia", caso_falha_nao_vaza),
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
