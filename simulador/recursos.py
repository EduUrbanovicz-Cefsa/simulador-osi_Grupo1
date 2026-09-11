"""Localizacao de arquivos ao lado do programa.

Este modulo existe por causa de um requisito especifico: a rede simulada e
lida de um arquivo externo que deve poder ser trocado ao lado do executavel,
sem gerar outro executavel e sem caminho absoluto no codigo.

Quando o programa e empacotado, o interpretador extrai os modulos em uma
pasta temporaria. Nesse estado, o caminho derivado de ``__file__`` aponta
para a pasta temporaria, e nao para a pasta onde o usuario colocou o
executavel: um arquivo trocado ali nunca seria lido. A funcao abaixo
distingue os dois casos.
"""

import os
import sys


def pasta_do_programa():
    """Devolve a pasta em que o usuario ve o programa.

    Empacotado, e a pasta do executavel. Executado a partir do codigo-fonte,
    e a raiz do projeto, um nivel acima deste modulo.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def caminho_de(nome_do_arquivo):
    """Monta o caminho de um arquivo ao lado do programa."""
    return os.path.join(pasta_do_programa(), nome_do_arquivo)
