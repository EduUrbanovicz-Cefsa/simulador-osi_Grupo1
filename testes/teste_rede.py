"""Confere a topologia e a escolha de rota contra os valores do enunciado.

Os resultados esperados vem do log de exemplo da especificacao e da
descricao dos casos E1, E2, E4 e E5.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulador.rede import Topologia


def executar():
    topologia = Topologia.carregar()
    falhas = []

    def conferir(descricao, obtido, esperado):
        ok = obtido == esperado
        print(f"{'ok    ' if ok else 'FALHOU'} {descricao}")
        if not ok:
            print(f"       obtido:   {obtido}")
            print(f"       esperado: {esperado}")
            falhas.append(descricao)

    print("Tabela de encaminhamento de R1")
    print("-" * 62)
    for rota in topologia.tabela_de_encaminhamento("R1"):
        destino = "entrega direta" if rota.direta else f"via {rota.proximo_salto}"
        print(f"  {rota.prefixo:<15} {destino:<18} custo {rota.custo}  interface {rota.interface_de_saida}")
    print()

    # A linha 011 do log da especificacao: 10.0.3.0/24 via R4, custo 2, interface e1.
    rota = topologia.rota_para("R1", "10.0.3.10")
    conferir("R1 alcanca a Rede C via R4, custo 2, interface e1",
             (rota.proximo_salto, rota.custo, rota.interface_de_saida),
             ("R4", 2, "e1"))

    # E1: H1 e H2 estao na mesma rede, e a entrega dispensa roteador.
    conferir("E1 entrega direta de H1 para H2",
             topologia.caminho_de_dispositivos("H1", "10.0.1.11"),
             ["H1", "H2"])

    # E2: caso central, quatro enlaces e tres roteadores.
    conferir("E2 caminho de H1 ate H4 pelo menor custo",
             topologia.caminho_de_dispositivos("H1", "10.0.3.10"),
             ["H1", "R1", "R4", "R3", "H4"])

    caminho = topologia.caminho_de_dispositivos("H1", "10.0.3.10")
    conferir("E2 percorre quatro enlaces", len(caminho) - 1, 4)

    # E5: endereco fora de qualquer prefixo da topologia.
    conferir("E5 destino 10.0.9.10 nao tem prefixo conhecido",
             topologia.prefixo_de("10.0.9.10"), None)
    conferir("E5 R1 nao encontra rota e o pacote e descartado",
             topologia.rota_para("R1", "10.0.9.10"), None)

    # E4: com o enlace R1-R4 fora de servico, o desvio passa por R2, custo 3.
    topologia.derrubar("R1", "R4")
    rota = topologia.rota_para("R1", "10.0.3.10")
    conferir("E4 desvio por R2 com custo 3",
             (rota.proximo_salto, rota.custo), ("R2", 3))
    conferir("E4 caminho passa a ser H1 R1 R2 R3 H4",
             topologia.caminho_de_dispositivos("H1", "10.0.3.10"),
             ["H1", "R1", "R2", "R3", "H4"])
    conferir("E4 continua com quatro enlaces",
             len(topologia.caminho_de_dispositivos("H1", "10.0.3.10")) - 1, 4)

    topologia.restaurar_enlaces()
    conferir("apos restaurar, a rota volta a passar por R4",
             topologia.rota_para("R1", "10.0.3.10").proximo_salto, "R4")

    print()
    print("todos os casos conferem" if not falhas else f"{len(falhas)} caso(s) divergente(s)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(executar())
