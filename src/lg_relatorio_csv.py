#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para gerar relatório via API LG (SOAP) e baixar CSV automaticamente.
Ideal para integração com Power BI (carregamento diário).
"""

import requests
import time
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
import json

# ==============================
# CONFIGURAÇÕES GERAIS
# ==============================
USUARIO = "gdsilva@metrorio.com.br"
SENHA = "Gabi@1982"
TENANT_GUID = "5DC483F3-8920-4BC6-BE83-10E8A4B794FD"
AMBIENTE = "270"
EMPRESA = "1"
NOME_RELATORIO = "01.Relaçao de Funcionários.fpl"

# Pasta onde o CSV será salvo
PASTA_DESTINO = Path(r"C:\RelatoriosLG")
PASTA_DESTINO.mkdir(parents=True, exist_ok=True)

# Nome fixo do arquivo (para Power BI ler sempre o mesmo)
NOME_ARQUIVO = "relatorio_funcionarios.csv"

# Tempo máximo de espera (segundos) e intervalo entre checagens
TEMPO_MAXIMO = 600  # 10 minutos
INTERVALO = 10      # 10 segundos


# ==============================
# FUNÇÕES AUXILIARES
# ==============================

def gerar_relatorio():
    """Chama a API LG para gerar o relatório e retorna o IdTarefa."""
    xml = f"""
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                      xmlns:dto="lg.com.br/svc/dto"
                      xmlns:v1="lg.com.br/api/v1"
                      xmlns:v11="lg.com.br/api/dto/v1">
        <soapenv:Header>
            <dto:LGAutenticacao>
                <dto:TokenUsuario>
                    <dto:Senha>{SENHA}</dto:Senha>
                    <dto:Usuario>{USUARIO}</dto:Usuario>
                    <dto:GuidTenant>{TENANT_GUID}</dto:GuidTenant>
                </dto:TokenUsuario>
            </dto:LGAutenticacao>
            <dto:LGContextoAmbiente>
                <dto:Ambiente>{AMBIENTE}</dto:Ambiente>
            </dto:LGContextoAmbiente>
        </soapenv:Header>
        <soapenv:Body>
            <v1:GerarRelatorioPorNome>
                <v1:filtroDeRelatorio>
                    <v11:Empresa><v11:Codigo>{EMPRESA}</v11:Codigo></v11:Empresa>
                    <v11:NomeDoRelatorio>{NOME_RELATORIO}</v11:NomeDoRelatorio>
                    <v11:Parametros/>
                </v1:filtroDeRelatorio>
            </v1:GerarRelatorioPorNome>
        </soapenv:Body>
    </soapenv:Envelope>
    """.strip()

    headers = {
        "Content-Type": "text/xml;charset=UTF-8",
        "SOAPAction": "lg.com.br/api/v1/ServicoDeRelatorio/GerarRelatorioPorNome"
    }

    r = requests.post("https://hml-api1.lg.com.br/v1/servicoderelatorio", data=xml.encode("utf-8"), headers=headers)
    r.raise_for_status()

    root = ET.fromstring(r.text)
    idtarefa = root.find(".//{lg.com.br/api/dto/v1}IdTarefa")
    if idtarefa is None:
        raise ValueError("Não foi possível extrair o IdTarefa da resposta.")
    return idtarefa.text.strip()


def consultar_status(id_tarefa):
    """Consulta o status do relatório via API LG e retorna (status, url)."""
    xml = f"""
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                      xmlns:dto="lg.com.br/svc/dto"
                      xmlns:v1="lg.com.br/api/v1"
                      xmlns:v11="lg.com.br/api/dto/v1">
        <soapenv:Header>
            <dto:LGAutenticacao>
                <dto:TokenUsuario>
                    <dto:Senha>{SENHA}</dto:Senha>
                    <dto:Usuario>{USUARIO}</dto:Usuario>
                    <dto:GuidTenant>{TENANT_GUID}</dto:GuidTenant>
                </dto:TokenUsuario>
            </dto:LGAutenticacao>
            <dto:LGContextoAmbiente>
                <dto:Ambiente>{AMBIENTE}</dto:Ambiente>
            </dto:LGContextoAmbiente>
        </soapenv:Header>
        <soapenv:Body>
            <v1:ConsultarTarefa>
                <v1:filtroDeTarefa>
                    <v11:IdTarefa>{id_tarefa}</v11:IdTarefa>
                </v1:filtroDeTarefa>
            </v1:ConsultarTarefa>
        </soapenv:Body>
    </soapenv:Envelope>
    """.strip()

    headers = {
        "Content-Type": "text/xml;charset=UTF-8",
        "SOAPAction": "lg.com.br/api/v1/ServicoDeRelatorio/ConsultarTarefa"
    }

    r = requests.post("https://hml-api1.lg.com.br/v1/servicoderelatorio", data=xml.encode("utf-8"), headers=headers)
    r.raise_for_status()

    root = ET.fromstring(r.text)
    status_el = root.find(".//{lg.com.br/api/dto/v1}StatusProcessamento")
    url_el = root.find(".//{lg.com.br/api/dto/v1}Url")

    status = int(status_el.text) if status_el is not None and status_el.text.isdigit() else None
    url = url_el.text.strip().replace("&amp;", "&") if url_el is not None and url_el.text else None
    return status, url


def baixar_csv(url, destino):
    """Baixa o arquivo CSV e salva no destino."""
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    with open(destino, "wb") as f:
        f.write(r.content)
    return destino


# ==============================
# EXECUÇÃO PRINCIPAL
# ==============================
def main():
    inicio = datetime.now()
    print(f"[INFO] Iniciando geração do relatório LG...")

    try:
        id_tarefa = gerar_relatorio()
        print(f"[OK] Relatório solicitado. IdTarefa: {id_tarefa}")

        tempo_total = 0
        url = None
        status = None

        while tempo_total < TEMPO_MAXIMO:
            status, url = consultar_status(id_tarefa)
            print(f"[INFO] Status: {status or 'N/A'} | Tempo: {tempo_total}s")

            if status == 3551 and url:
                print(f"[OK] Relatório pronto! URL: {url[:80]}...")
                break

            time.sleep(INTERVALO)
            tempo_total += INTERVALO

        if not url:
            raise TimeoutError("Tempo máximo atingido sem que o relatório estivesse pronto.")

        destino = PASTA_DESTINO / NOME_ARQUIVO
        baixar_csv(url, destino)
        print(f"[OK] Arquivo CSV salvo em: {destino}")

    except Exception as e:
        print(f"[ERRO] {e}")

    fim = datetime.now()
    print(f"[INFO] Execução finalizada. Duração total: {(fim - inicio).seconds}s")


if __name__ == "__main__":
    main()
