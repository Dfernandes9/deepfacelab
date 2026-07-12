#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Organizador de Fotos — "excelência"
===================================

Ferramenta autônoma para colocar ordem numa biblioteca de fotos bagunçada:

  1. JUNTA fotos E vídeos numa só árvore por data (Biblioteca/Ano/Ano-Mês),
     acabando com as inúmeras pastas espalhadas que sempre voltam. Como tudo
     sai das pastas antigas, elas esvaziam e são removidas.
  2. REMOVE fotos duplicadas (mantém a de melhor qualidade de cada grupo).
  3. SEPARA fotos de má qualidade (tremidas / borradas / minúsculas).
  4. SEPARA fotos que são quadros tirados de vídeo (frames, prints, gravações).

Vídeos são apenas movidos por data (nunca analisados nem descartados).

SEGURANÇA
---------
- Por padrão roda em modo *simulação* (dry-run): mostra o que faria e não
  toca em nenhum arquivo. Para efetivar, use --aplicar.
- Nada é apagado. As fotos ruins e duplicadas vão para uma pasta de
  quarentena (`_rejeitadas/`) separada por motivo. Você revisa e apaga
  manualmente se quiser.
- Os arquivos são movidos preservando data e nome (com sufixo se houver
  conflito).

Dependências: Python 3.8+, Pillow, numpy.
    pip install Pillow numpy

Exemplos
--------
    # 1) Ver o que aconteceria (não move nada):
    python organizar_fotos.py "/caminho/das/fotos"

    # 2) Efetivar, organizando dentro da própria pasta:
    python organizar_fotos.py "/caminho/das/fotos" --aplicar

    # 3) Efetivar mandando o resultado para outra pasta:
    python organizar_fotos.py "/entrada" --saida "/organizadas" --aplicar
"""

import argparse
import hashlib
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime

try:
    import numpy as np
    from PIL import Image, ImageOps, ExifTags
    from PIL.Image import Resampling
except ImportError as e:  # pragma: no cover - mensagem amigável
    sys.stderr.write(
        "\nFaltam dependências. Instale com:\n    pip install Pillow numpy\n\n"
        f"Detalhe: {e}\n"
    )
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Configuração
# --------------------------------------------------------------------------- #

EXTENSOES_IMAGEM = {
    ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff",
    ".webp", ".heic", ".heif",
}

# Vídeos são organizados por data também (sem análise de qualidade),
# para que nenhuma pasta fique "presa" por causa de um vídeo e o número
# total de pastas caia de verdade. Nenhum vídeo é apagado.
EXTENSOES_VIDEO = {
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".3gp", ".3g2", ".webm",
    ".wmv", ".flv", ".mts", ".m2ts", ".mpg", ".mpeg", ".mpe", ".mp2",
    ".ogv", ".vob", ".mxf",
}

# Pastas geradas por esta ferramenta — nunca são reprocessadas.
PASTA_REJEITADAS = "_rejeitadas"
SUBPASTA_BAIXA_QUALIDADE = "baixa_qualidade"
SUBPASTA_DE_VIDEO = "de_video"
SUBPASTA_DUPLICADAS = "duplicadas"

# Padrões de nome típicos de quadros de vídeo, prints e gravações de tela.
PADROES_NOME_VIDEO = [
    r"vlcsnap",              # VLC snapshot
    r"vid[-_ ]?\d",          # VID_20230101, VID-...
    r"mov[-_ ]?\d",          # MOV_...
    r"movie",
    r"video",
    r"\bframe[s]?\b",        # frame, frames
    r"frame[-_ ]?\d",        # frame_0001
    r"screen[-_ ]?shot",     # screenshot / screen shot
    r"screenshot",
    r"captura[-_ ]?de[-_ ]?tela",  # português
    r"print[-_ ]?screen",
    r"snapshot",
    r"gravacao",             # gravação de tela (sem acento após normalizar)
    r"grab",
    r"still[-_ ]?\d",
]
_RE_NOME_VIDEO = re.compile("|".join(PADROES_NOME_VIDEO), re.IGNORECASE)

# Resoluções exatas comuns de vídeo (largura, altura) — orientação livre.
RESOLUCOES_VIDEO = {
    (1920, 1080), (1280, 720), (3840, 2160), (2560, 1440),
    (854, 480), (640, 360), (1024, 576), (720, 480), (720, 576),
}


# --------------------------------------------------------------------------- #
# Utilidades de imagem
# --------------------------------------------------------------------------- #

def _tag_exif(id_para_nome, exif, nome):
    """Lê uma tag EXIF pelo nome legível (ex.: 'DateTimeOriginal')."""
    for tag_id, valor in exif.items():
        if id_para_nome.get(tag_id) == nome:
            return valor
    return None


def ler_exif(img):
    """Retorna dict simplificado do EXIF: data, fabricante, modelo."""
    info = {"data": None, "make": None, "model": None}
    try:
        exif = img.getexif()
    except Exception:
        return info
    if not exif:
        return info

    id_para_nome = ExifTags.TAGS
    make = _tag_exif(id_para_nome, exif, "Make")
    model = _tag_exif(id_para_nome, exif, "Model")
    info["make"] = str(make).strip() if make else None
    info["model"] = str(model).strip() if model else None

    # A data original costuma estar no IFD de Exif.
    data_str = None
    for nome_tag in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
        try:
            ifd = exif.get_ifd(0x8769)  # Exif IFD
        except Exception:
            ifd = {}
        for tag_id, valor in list(ifd.items()) + list(exif.items()):
            if id_para_nome.get(tag_id) == nome_tag and valor:
                data_str = str(valor)
                break
        if data_str:
            break

    if data_str:
        for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                info["data"] = datetime.strptime(data_str.strip(), fmt)
                break
            except ValueError:
                continue
    return info


def data_da_foto(caminho, exif):
    """Melhor estimativa da data: EXIF > data de modificação do arquivo."""
    if exif["data"]:
        return exif["data"]
    try:
        return datetime.fromtimestamp(os.path.getmtime(caminho))
    except OSError:
        return datetime.now()


def _cinza_pequeno(img, lado=256):
    """Converte para tons de cinza e reduz, para métricas rápidas."""
    g = ImageOps.exif_transpose(img).convert("L")
    g.thumbnail((lado, lado), Resampling.BILINEAR)
    return np.asarray(g, dtype=np.float64)


def nitidez(arr_cinza):
    """
    Variância do Laplaciano — mesma ideia usada por ferramentas de foco.
    Valor alto = imagem nítida; valor baixo = borrada/tremida.
    """
    lap = (
        -4 * arr_cinza
        + np.roll(arr_cinza, 1, axis=0)
        + np.roll(arr_cinza, -1, axis=0)
        + np.roll(arr_cinza, 1, axis=1)
        + np.roll(arr_cinza, -1, axis=1)
    )
    # Descarta bordas (o roll distorce as extremidades).
    interior = lap[1:-1, 1:-1]
    return float(interior.var())


def hash_perceptual(arr_cinza):
    """
    aHash (average hash) de 64 bits para achar fotos iguais/quase iguais.
    Duas fotos com hashes próximos (distância de Hamming pequena) são
    consideradas a mesma imagem.
    """
    peq = np.asarray(
        Image.fromarray(arr_cinza.astype(np.uint8)).resize((8, 8), Resampling.BILINEAR),
        dtype=np.float64,
    )
    media = peq.mean()
    bits = (peq > media).flatten()
    valor = 0
    for b in bits:
        valor = (valor << 1) | int(b)
    return valor


def distancia_hamming(a, b):
    return bin(a ^ b).count("1")


# --------------------------------------------------------------------------- #
# Classificação
# --------------------------------------------------------------------------- #

class Foto:
    __slots__ = ("caminho", "largura", "altura", "nitidez", "hash", "exif",
                 "data", "erro")

    def __init__(self, caminho):
        self.caminho = caminho
        self.largura = self.altura = 0
        self.nitidez = 0.0
        self.hash = None
        self.exif = {"data": None, "make": None, "model": None}
        self.data = None
        self.erro = None

    @property
    def megapixels(self):
        return (self.largura * self.altura) / 1_000_000

    @property
    def nome(self):
        return os.path.basename(self.caminho)


def analisar(caminho):
    """Abre a imagem e coleta todas as métricas necessárias."""
    foto = Foto(caminho)
    try:
        with Image.open(caminho) as img:
            img.load()
            foto.largura, foto.altura = img.size
            foto.exif = ler_exif(img)
            cinza = _cinza_pequeno(img)
        foto.nitidez = nitidez(cinza)
        foto.hash = hash_perceptual(cinza)
        foto.data = data_da_foto(caminho, foto.exif)
    except Exception as e:  # arquivo corrompido / formato não suportado
        foto.erro = str(e)
    return foto


def eh_de_video(foto):
    """
    Heurística conservadora para 'quadro de vídeo / print de tela'.
    Retorna (True/False, motivo).
    """
    nome = foto.nome.lower()

    # 1) Sinal forte: o nome do arquivo denuncia a origem.
    if _RE_NOME_VIDEO.search(nome):
        return True, "nome indica vídeo/captura de tela"

    # 2) Sinal médio: resolução EXATA de vídeo + sem dados de câmera no EXIF.
    #    (Fotos de câmera real quase sempre têm Make/Model e proporção 4:3/3:2.)
    res = (foto.largura, foto.altura)
    res_invertida = (foto.altura, foto.largura)
    sem_camera = not (foto.exif["make"] or foto.exif["model"])
    if sem_camera and (res in RESOLUCOES_VIDEO or res_invertida in RESOLUCOES_VIDEO):
        return True, f"resolução de vídeo {foto.largura}x{foto.altura} sem dados de câmera"

    return False, None


def eh_baixa_qualidade(foto, limite_nitidez, min_megapixels):
    """Retorna (True/False, motivo)."""
    if foto.megapixels < min_megapixels:
        return True, f"resolução baixa ({foto.megapixels:.1f} MP)"
    if foto.nitidez < limite_nitidez:
        return True, f"borrada/tremida (nitidez {foto.nitidez:.0f})"
    return False, None


# --------------------------------------------------------------------------- #
# Coleta de arquivos
# --------------------------------------------------------------------------- #

def coletar_arquivos(raiz, pasta_saida, pasta_biblioteca=None):
    """
    Percorre a árvore ignorando as pastas geradas pela ferramenta (a
    quarentena e a própria biblioteca já organizada, para não reprocessar).
    Retorna (caminho, eh_video) para cada foto ou vídeo encontrado.
    """
    saida_abs = os.path.abspath(pasta_saida)
    rejeitadas_abs = os.path.join(saida_abs, PASTA_REJEITADAS)
    biblioteca_abs = os.path.abspath(pasta_biblioteca) if pasta_biblioteca else None

    def ignorar(caminho_abs):
        if caminho_abs == rejeitadas_abs:
            return True
        # A biblioteca só é ignorada se for uma subpasta distinta da raiz
        # (evita ignorar tudo quando não há pasta-raiz própria).
        if biblioteca_abs and biblioteca_abs != saida_abs and caminho_abs == biblioteca_abs:
            return True
        return False

    for dir_atual, subdirs, arquivos in os.walk(raiz):
        # Poda as pastas geradas para não descer nelas.
        subdirs[:] = [d for d in subdirs
                      if not ignorar(os.path.abspath(os.path.join(dir_atual, d)))]
        for nome in arquivos:
            ext = os.path.splitext(nome)[1].lower()
            if ext in EXTENSOES_IMAGEM:
                yield os.path.join(dir_atual, nome), False
            elif ext in EXTENSOES_VIDEO:
                yield os.path.join(dir_atual, nome), True


# --------------------------------------------------------------------------- #
# Movimentação segura
# --------------------------------------------------------------------------- #

def destino_sem_conflito(pasta, nome):
    """Gera um caminho livre em `pasta`, adicionando _1, _2... se preciso."""
    base, ext = os.path.splitext(nome)
    destino = os.path.join(pasta, nome)
    n = 1
    while os.path.exists(destino):
        destino = os.path.join(pasta, f"{base}_{n}{ext}")
        n += 1
    return destino


class Executor:
    """Aplica (ou apenas simula) as operações de mover arquivos."""

    def __init__(self, aplicar):
        self.aplicar = aplicar
        self.movimentos = []  # (origem, destino, categoria)

    def mover(self, origem, pasta_destino, categoria):
        # Se o arquivo já está exatamente onde deveria ficar, não faz nada
        # (torna a ferramenta segura para rodar várias vezes na mesma pasta).
        destino_natural = os.path.join(pasta_destino, os.path.basename(origem))
        if os.path.abspath(origem) == os.path.abspath(destino_natural):
            self.movimentos.append((origem, destino_natural, categoria))
            return destino_natural

        if self.aplicar:
            os.makedirs(pasta_destino, exist_ok=True)
        destino = destino_sem_conflito(pasta_destino, os.path.basename(origem))
        self.movimentos.append((origem, destino, categoria))
        if self.aplicar:
            shutil.move(origem, destino)
        return destino


def remover_pastas_vazias(raiz, aplicar):
    """Depois de mover tudo, elimina as pastas que ficaram vazias."""
    removidas = 0
    for dir_atual, subdirs, arquivos in os.walk(raiz, topdown=False):
        if os.path.abspath(dir_atual) == os.path.abspath(raiz):
            continue
        try:
            if not os.listdir(dir_atual):
                removidas += 1
                if aplicar:
                    os.rmdir(dir_atual)
        except OSError:
            pass
    return removidas


# --------------------------------------------------------------------------- #
# Pipeline principal
# --------------------------------------------------------------------------- #

def organizar(args):
    raiz = os.path.abspath(args.entrada)
    saida = os.path.abspath(args.saida) if args.saida else raiz
    if not os.path.isdir(raiz):
        sys.stderr.write(f"Pasta não encontrada: {raiz}\n")
        return 1

    pasta_rejeitadas = os.path.join(saida, PASTA_REJEITADAS)
    # Pasta-raiz única que abriga toda a árvore por data (fotos + vídeos).
    # Vazia ("" / "." / "/") = coloca as pastas de data direto no destino.
    nome_raiz = (args.pasta_raiz or "").strip().strip("/\\").strip(".")
    biblioteca = os.path.join(saida, nome_raiz) if nome_raiz else saida
    executor = Executor(args.aplicar)

    print("=" * 64)
    print("  ORGANIZADOR DE FOTOS")
    print("=" * 64)
    print(f"  Entrada    : {raiz}")
    print(f"  Saída      : {saida}")
    print(f"  Biblioteca : {biblioteca}")
    modo = "APLICAR (arquivos serão movidos)" if args.aplicar else "SIMULAÇÃO (nada será movido)"
    print(f"  Modo       : {modo}")
    rigor = "suave" if args.suave else "RIGOROSO (padrão)"
    print(f"  Rigor      : {rigor}  (nitidez>={args.limite_nitidez:.0f}, "
          f">={args.min_megapixels:.1f} MP, duplicata<={args.limite_duplicata})")
    print("-" * 64)

    coletados = list(coletar_arquivos(raiz, saida, biblioteca))
    caminhos_foto = [c for c, ev in coletados if not ev]
    caminhos_video = [c for c, ev in coletados if ev]
    print(f"  Encontradas {len(caminhos_foto)} fotos e "
          f"{len(caminhos_video)} vídeos. Analisando...")

    fotos = []
    for i, caminho in enumerate(caminhos_foto, 1):
        fotos.append(analisar(caminho))
        if i % 200 == 0:
            print(f"    ... {i}/{len(caminhos_foto)}")

    contadores = defaultdict(int)

    # --- Vídeos: organizados por data (pela data do arquivo), nunca --------- #
    # analisados nem descartados. Isso esvazia as pastas antigas para que
    # elas sumam e o número total de pastas caia drasticamente.
    for caminho in caminhos_video:
        try:
            data = datetime.fromtimestamp(os.path.getmtime(caminho))
        except OSError:
            data = datetime.now()
        pasta_data = pasta_por_data(biblioteca, data, args.plano, args.por_ano)
        executor.mover(caminho, pasta_data, "video")
        contadores["video"] += 1

    # --- Passo 1: classifica erro / vídeo / baixa qualidade. -------------- #
    # Fazemos isto ANTES da deduplicação para que um quadro de vídeo ou uma
    # foto borrada nunca seja rotulada apenas como "duplicada".
    candidatas_boas = []
    for foto in fotos:
        if foto.erro is not None:
            executor.mover(foto.caminho,
                           os.path.join(pasta_rejeitadas, "com_erro"), "erro")
            contadores["erro"] += 1
            continue

        de_video, _ = eh_de_video(foto)
        if de_video:
            executor.mover(foto.caminho,
                           os.path.join(pasta_rejeitadas, SUBPASTA_DE_VIDEO), "de_video")
            contadores["de_video"] += 1
            continue

        baixa, _ = eh_baixa_qualidade(foto, args.limite_nitidez, args.min_megapixels)
        if baixa:
            executor.mover(foto.caminho,
                           os.path.join(pasta_rejeitadas, SUBPASTA_BAIXA_QUALIDADE),
                           "baixa_qualidade")
            contadores["baixa_qualidade"] += 1
            continue

        candidatas_boas.append(foto)

    # --- Passo 2: deduplica apenas entre as fotos boas restantes. --------- #
    grupos = agrupar_duplicatas(
        [f for f in candidatas_boas if f.hash is not None], args.limite_duplicata
    )
    duplicadas_descartaveis = set()  # id() das que perdem para uma melhor
    for grupo in grupos:
        if len(grupo) > 1:
            melhor = max(grupo, key=lambda f: (f.nitidez, f.megapixels))
            for f in grupo:
                if f is not melhor:
                    duplicadas_descartaveis.add(id(f))

    # --- Passo 3: move duplicadas para quarentena e o resto por data. ----- #
    for foto in candidatas_boas:
        if id(foto) in duplicadas_descartaveis:
            executor.mover(foto.caminho,
                           os.path.join(pasta_rejeitadas, SUBPASTA_DUPLICADAS), "duplicada")
            contadores["duplicada"] += 1
            continue

        pasta_data = pasta_por_data(biblioteca, foto.data, args.plano, args.por_ano)
        executor.mover(foto.caminho, pasta_data, "organizada")
        contadores["organizada"] += 1

    pastas_vazias = 0
    if args.limpar_vazias:
        pastas_vazias = remover_pastas_vazias(raiz, args.aplicar)

    _relatorio(executor, contadores, pastas_vazias, args)
    return 0


def agrupar_duplicatas(fotos, limite):
    """
    Agrupa fotos cujos hashes perceptuais estão a até `limite` bits de
    distância. União simples por varredura — suficiente para bibliotecas
    pessoais.
    """
    grupos = []
    for foto in fotos:
        colocada = False
        for grupo in grupos:
            if distancia_hamming(foto.hash, grupo[0].hash) <= limite:
                grupo.append(foto)
                colocada = True
                break
        if not colocada:
            grupos.append([foto])
    return grupos


def pasta_por_data(base, data, plano, por_ano=False):
    if plano:
        return base
    if por_ano:
        # Uma única pasta por ano — o mínimo de pastas possível mantendo ordem.
        return os.path.join(base, f"{data.year:04d}")
    return os.path.join(base, f"{data.year:04d}", f"{data.year:04d}-{data.month:02d}")


def _relatorio(executor, contadores, pastas_vazias, args):
    print("-" * 64)
    print("  RESUMO")
    print("-" * 64)
    rotulos = [
        ("organizada", "Fotos organizadas por data"),
        ("video", "Vídeos organizados por data"),
        ("duplicada", "Duplicadas (quarentena)"),
        ("de_video", "Quadros de vídeo/print (quarentena)"),
        ("baixa_qualidade", "Baixa qualidade (quarentena)"),
        ("erro", "Com erro/ilegíveis (quarentena)"),
    ]
    for chave, rotulo in rotulos:
        print(f"    {rotulo:.<44} {contadores[chave]:>6}")
    total = sum(contadores.values())
    print(f"    {'TOTAL':.<44} {total:>6}")
    if args.limpar_vazias:
        print(f"    {'Pastas vazias removidas':.<44} {pastas_vazias:>6}")
    print("-" * 64)

    if not args.aplicar:
        print("  Isto foi uma SIMULAÇÃO. Nada foi movido.")
        print("  Para efetivar, rode de novo adicionando:  --aplicar")
        if args.exemplos and executor.movimentos:
            print("\n  Exemplos do que seria feito:")
            for origem, destino, cat in executor.movimentos[: args.exemplos]:
                print(f"    [{cat}] {os.path.basename(origem)}")
                print(f"        -> {destino}")
    else:
        print("  Concluído. Fotos ruins/duplicadas estão em:")
        print(f"    {os.path.join(os.path.abspath(args.saida or args.entrada), PASTA_REJEITADAS)}")
        print("  Revise essa pasta e apague o que não quiser manter.")
    print("=" * 64)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def construir_parser():
    p = argparse.ArgumentParser(
        description="Organiza uma biblioteca de fotos: junta por data, remove "
                    "duplicadas e separa fotos ruins e quadros de vídeo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("entrada", help="Pasta com as fotos a organizar.")
    p.add_argument("--saida", default=None,
                   help="Pasta de destino (padrão: organiza dentro da própria entrada).")
    p.add_argument("--aplicar", action="store_true",
                   help="Efetiva os movimentos. Sem isto, apenas simula.")
    # Padrões deixados como None para sabermos se o usuário os informou
    # explicitamente (o que tem prioridade sobre o preset --rigoroso).
    p.add_argument("--limite-nitidez", type=float, default=None,
                   help="Abaixo deste valor a foto é considerada borrada "
                        "(padrão rigoroso: 300; com --suave: 150).")
    p.add_argument("--min-megapixels", type=float, default=None,
                   help="Fotos menores que isto são baixa qualidade "
                        "(padrão rigoroso: 4.0 MP; com --suave: 2.0 MP).")
    p.add_argument("--limite-duplicata", type=int, default=None,
                   help="Distância máx. de hash para considerar duplicata "
                        "(padrão rigoroso: 10; com --suave: 8).")
    p.add_argument("--suave", action="store_true",
                   help="Afrouxa os limiares (150 / 2.0 MP / 8). Sem isto, "
                        "roda no modo rigoroso, que é o padrão.")
    p.add_argument("--rigoroso", action="store_true",
                   help="Modo rigoroso (já é o padrão). Mantido por "
                        "compatibilidade; sem efeito extra.")
    p.add_argument("--pasta-raiz", dest="pasta_raiz", default="Biblioteca",
                   help="Nome da pasta-raiz única que abriga toda a árvore por "
                        "data (padrão: 'Biblioteca'). Use \"\" para pôr as pastas "
                        "de data direto no destino.")
    p.add_argument("--por-ano", dest="por_ano", action="store_true",
                   help="Agrupa só por ANO (Ano/) em vez de Ano/Ano-Mês. "
                        "Reduz ainda mais o número de pastas.")
    p.add_argument("--uma-pasta", "--plano", dest="plano", action="store_true",
                   help="Junta TUDO (fotos + vídeos) numa pasta única, sem "
                        "subpastas por data. Ideal para depois importar no app "
                        "Fotos (Apple) / Google Fotos, que organizam sozinhos.")
    p.add_argument("--nao-limpar-vazias", dest="limpar_vazias",
                   action="store_false", help="Não remove pastas que ficaram vazias.")
    p.add_argument("--exemplos", type=int, default=15,
                   help="Quantos exemplos mostrar na simulação (padrão: 15).")
    p.set_defaults(limpar_vazias=True)
    return p


# Presets de rigor: (limite_nitidez, min_megapixels, limite_duplicata)
# O modo rigoroso é o PADRÃO; --suave afrouxa.
PRESET_SUAVE = (150.0, 2.0, 8)
PRESET_RIGOROSO = (300.0, 4.0, 10)


def aplicar_presets(args):
    """Resolve os limiares: flag explícita > preset. Rigoroso é o padrão."""
    base = PRESET_SUAVE if args.suave else PRESET_RIGOROSO
    if args.limite_nitidez is None:
        args.limite_nitidez = base[0]
    if args.min_megapixels is None:
        args.min_megapixels = base[1]
    if args.limite_duplicata is None:
        args.limite_duplicata = base[2]
    return args


def main(argv=None):
    args = aplicar_presets(construir_parser().parse_args(argv))
    return organizar(args)


if __name__ == "__main__":
    raise SystemExit(main())
