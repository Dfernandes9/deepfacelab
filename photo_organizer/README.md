# Organizador de Fotos

Ferramenta simples e **segura** para colocar ordem numa biblioteca de fotos
bagunçada. Ela resolve tudo de uma vez:

1. **Junta fotos E vídeos numa só árvore** (`Biblioteca/Ano/Ano-Mês`), acabando
   com as inúmeras pastas espalhadas que sempre voltam. Como todos os arquivos
   saem das pastas antigas, elas ficam vazias e são removidas — o número de
   pastas cai drasticamente.
2. **Remove fotos duplicadas** — de cada grupo de cópias, mantém a de melhor
   qualidade.
3. **Separa fotos de má qualidade** — tremidas, borradas ou pequenas demais.
4. **Separa fotos tiradas de vídeo** — quadros de gravação, prints de tela e
   capturas.

> **Nada é apagado, nenhuma foto ou vídeo se perde.** Os vídeos são só movidos
> para a pasta da data certa (nunca analisados nem descartados). As fotos ruins
> e duplicadas vão para uma pasta de quarentena (`_rejeitadas/`), separadas por
> motivo — você revisa com calma e apaga só o que quiser.

---

## Instalação (uma vez só)

Precisa de Python 3.8+ e de duas bibliotecas:

```bash
pip install -r requirements.txt
```

## Como usar

### 1. Primeiro, veja o que aconteceria (não move nada)

```bash
python organizar_fotos.py "/caminho/das/suas/fotos"
```

Isso é uma **simulação**: mostra quantas fotos seriam organizadas, quantas
seriam separadas como duplicadas / de vídeo / má qualidade, e alguns exemplos.
Nenhum arquivo é tocado.

### 2. Gostou? Efetive com `--aplicar`

```bash
python organizar_fotos.py "/caminho/das/suas/fotos" --aplicar
```

Se preferir manter as originais intactas e mandar o resultado para outra pasta:

```bash
python organizar_fotos.py "/entrada" --saida "/fotos_organizadas" --aplicar
```

### 3. Quer TUDO numa pasta única? (para importar no app Fotos)

Se a ideia é só juntar tudo numa **única pasta plana** — sem milhares de
subpastas — e deixar o **app Fotos (Apple)** ou o **Google Fotos** organizarem
por data depois (eles fazem isso sozinhos, pela data de cada arquivo), use
`--uma-pasta`:

```bash
python organizar_fotos.py "/caminho/das/suas/fotos" --uma-pasta --aplicar
```

Resultado: uma pasta `Biblioteca/` com **todas as fotos e vídeos bons juntos**,
sem subpastas. As duplicadas e as ruins continuam indo para `_rejeitadas/`, para
a `Biblioteca/` chegar limpa no app. Depois é só arrastar a `Biblioteca/` para
dentro do Fotos.

## Resultado

Antes (bagunça típica — dezenas de pastas):

```
Fotos/
├── WhatsApp Images/…
├── WhatsApp Video/movie.mov
├── Nova pasta/
├── Nova pasta (2)/
├── Câmera/2023-01/…
├── DCIM/100ANDRO/VID_2023.mp4
├── videos/frame_0001.jpg
└── prints/Screenshot.png
```

Depois — **uma só árvore** (`Biblioteca/`), fotos e vídeos juntos por data:

```
Fotos/
├── Biblioteca/                 ← tudo organizado numa única árvore
│   ├── 2023/
│   │   ├── 2023-01/            ← fotos e vídeos do mês, juntos
│   │   └── 2023-05/
│   └── 2024/
│       └── 2024-12/
└── _rejeitadas/                ← só o que você vai revisar/apagar
    ├── baixa_qualidade/
    ├── de_video/
    └── duplicadas/
```

- A pasta-raiz chama-se `Biblioteca/` por padrão. Troque o nome com
  `--pasta-raiz "Meu Álbum"`, ou use `--pasta-raiz ""` para pôr as pastas de
  data direto no destino (sem a raiz).
- Quer o mínimo absoluto de pastas? Use `--por-ano` — aí fica só uma pasta por
  ano (`Biblioteca/2023/`, `Biblioteca/2024/`, …).

**Pode rodar quantas vezes quiser**: fotos já organizadas ficam onde estão e a
quarentena não é reprocessada. Rodar de novo não bagunça nada — por isso as
pastas param de "voltar".

## Ajustes finos (opcionais)

| Opção                    | O que faz                                                        | Padrão |
|--------------------------|------------------------------------------------------------------|--------|
| `--aplicar`              | Efetiva de verdade. Sem isto, só simula.                         | (off)  |
| `--saida PASTA`          | Manda o resultado para outra pasta em vez da própria entrada.    | entrada|
| `--pasta-raiz NOME`      | Nome da pasta-raiz única da árvore. `""` = sem raiz.             | Biblioteca |
| `--suave`                | Afrouxa os limiares (ver tabela abaixo).                         | (off)  |
| `--limite-nitidez N`     | Abaixo disso a foto é considerada borrada. Maior = mais rígido.  | 300    |
| `--min-megapixels N`     | Fotos menores que isso viram "baixa qualidade".                  | 4.0    |
| `--limite-duplicata N`   | Quão parecidas duas fotos precisam ser p/ virar duplicata (0-10).| 10     |
| `--por-ano`              | Agrupa só por ANO (`2023/`) — o mínimo de pastas.                | (off)  |
| `--uma-pasta`            | Junta tudo numa pasta única, sem subpastas (bom p/ app Fotos).   | (off)  |
| `--nao-limpar-vazias`    | Não remove as pastas que ficaram vazias.                         | (off)  |

> **Sobre os vídeos:** são movidos junto das fotos, para a pasta da data de
> gravação (lida da data do arquivo). Nunca são analisados nem apagados. Como
> alguns programas de cópia/download alteram a data do arquivo, um vídeo pode
> eventualmente cair no mês errado — mas ele nunca se perde e continua
> organizado.

### Níveis de rigor

O padrão já é o modo **rigoroso** (o mais exigente). Se estiver separando fotos
boas demais, use `--suave` para afrouxar:

| Nível                     | Nitidez mín. | Resolução mín. | Duplicatas |
|---------------------------|:------------:|:--------------:|:----------:|
| **Padrão (rigoroso)**     | 300          | 4.0 MP         | 10         |
| `--suave`                 | 150          | 2.0 MP         | 8          |

Qualquer valor que você informe explicitamente tem prioridade sobre o preset.
Exemplos:

```bash
# Padrão já é rigoroso:
python organizar_fotos.py "/fotos" --aplicar

# Mais tolerante:
python organizar_fotos.py "/fotos" --suave --aplicar

# Rigoroso, mas afrouxando só a resolução mínima:
python organizar_fotos.py "/fotos" --min-megapixels 2 --aplicar
```

> **Dica:** rode primeiro em simulação (sem `--aplicar`) e olhe o resumo. Se
> separar fotos boas demais, baixe o `--limite-nitidez`; se separar de menos,
> aumente. O cabeçalho mostra sempre os limiares em uso.

## Como ela decide

- **Borrada / tremida**: usa a *variância do Laplaciano* (mesma técnica de
  detecção de foco usada por ferramentas profissionais). Imagem nítida tem
  muitas bordas; borrada tem poucas.
- **Duplicada**: gera uma "impressão digital" visual (*average hash*) de cada
  foto e agrupa as muito parecidas, mantendo a mais nítida.
- **De vídeo / print**: pelo nome do arquivo (`frame`, `VID_`, `screenshot`,
  `captura de tela`, `vlcsnap`…) ou pela resolução exata de vídeo
  (1920×1080, 1280×720…) sem dados de câmera no EXIF. A detecção é
  conservadora para não separar foto boa por engano.

## Segurança

- Modo simulação por padrão — você sempre vê antes de mexer.
- Nunca apaga arquivos; só move para quarentena.
- Conflitos de nome são resolvidos com sufixo (`foto.jpg`, `foto_1.jpg`), nunca
  sobrescrevendo.
- Arquivos ilegíveis/corrompidos vão para `_rejeitadas/com_erro/` para você ver.
