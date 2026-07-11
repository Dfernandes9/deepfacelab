#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Organizador de Fotos — "excelência"
===================================

Ferramenta autônoma para colocar ordem numa biblioteca de fotos bagunçada:

  1. JUNTA tudo numa árvore limpa por data (Ano/Ano-Mês), acabando com as
     inúmeras pastas espalhadas que sempre voltam.
  2. REMOVE fotos duplicadas (mantém a de melhor qualidade de cada grupo).
  3. SEPARA fotos de má qualidade (tremidas / borradas / minúsculas).
  4. SEPARA fotos que são quadros tirados de vídeo (frames, prints, gravações).

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

def coletar_imagens(raiz, pasta_saida):
    """Percorre a árvore ignorando as pastas geradas pela ferramenta."""
    saida_abs = os.path.abspath(pasta_saida)
    for dir_atual, subdirs, arquivos in os.walk(raiz):
        # Não reprocessa a quarentena nem a própria saída.
        subdirs[:] = [d for d in subdirs if d != PASTA_REJEITADAS]
        if os.path.abspath(dir_atual).startswith(os.path.join(saida_abs, PASTA_REJEITADAS)):
            continue
        for nome in arquivos:
            if os.path.splitext(nome)[1].lower() in EXTENSOES_IMAGEM:
                yield os.path.join(dir_atual, nome)


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
    executor = Executor(args.aplicar)

    print("=" * 64)
    print("  ORGANIZADOR DE FOTOS")
    print("=" * 64)
    print(f"  Entrada : {raiz}")
    print(f"  Saída   : {saida}")
    modo = "APLICAR (arquivos serão movidos)" if args.aplicar else "SIMULAÇÃO (nada será movido)"
    print(f"  Modo    : {modo}")
    rigor = "RIGOROSO" if args.rigoroso else "normal"
    print(f"  Rigor   : {rigor}  (nitidez>={args.limite_nitidez:.0f}, "
          f">={args.min_megapixels:.1f} MP, duplicata<={args.limite_duplicata})")
    print("-" * 64)

    caminhos = list(coletar_imagens(raiz, saida))
    print(f"  Encontradas {len(caminhos)} imagens. Analisando...")

    fotos = []
    for i, caminho in enumerate(caminhos, 1):
        fotos.append(analisar(caminho))
        if i % 200 == 0:
            print(f"    ... {i}/{len(caminhos)}")

    contadores = defaultdict(int)

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

        pasta_data = pasta_por_data(saida, foto.data, args.plano)
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


def pasta_por_data(saida, data, plano):
    if plano:
        return os.path.join(saida, "Fotos")
    return os.path.join(saida, f"{data.year:04d}", f"{data.year:04d}-{data.month:02d}")


def _relatorio(executor, contadores, pastas_vazias, args):
    print("-" * 64)
    print("  RESUMO")
    print("-" * 64)
    rotulos = [
        ("organizada", "Organizadas por data"),
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
                        "(padrão: 150; com --rigoroso: 300).")
    p.add_argument("--min-megapixels", type=float, default=None,
                   help="Fotos menores que isto são baixa qualidade "
                        "(padrão: 2.0 MP; com --rigoroso: 4.0 MP).")
    p.add_argument("--limite-duplicata", type=int, default=None,
                   help="Distância máx. de hash para considerar duplicata "
                        "(padrão: 8; com --rigoroso: 10).")
    p.add_argument("--rigoroso", action="store_true",
                   help="Modo mais rígido: separa mais fotos borradas, exige "
                        "resolução maior e agrupa mais duplicadas.")
    p.add_argument("--plano", action="store_true",
                   help="Junta tudo numa pasta única em vez de subpastas por data.")
    p.add_argument("--nao-limpar-vazias", dest="limpar_vazias",
                   action="store_false", help="Não remove pastas que ficaram vazias.")
    p.add_argument("--exemplos", type=int, default=15,
                   help="Quantos exemplos mostrar na simulação (padrão: 15).")
    p.set_defaults(limpar_vazias=True)
    return p


# Presets de rigor: (limite_nitidez, min_megapixels, limite_duplicata)
PRESET_NORMAL = (150.0, 2.0, 8)
PRESET_RIGOROSO = (300.0, 4.0, 10)


def aplicar_presets(args):
    """Resolve os limiares: flag explícita > preset --rigoroso > padrão normal."""
    base = PRESET_RIGOROSO if args.rigoroso else PRESET_NORMAL
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
