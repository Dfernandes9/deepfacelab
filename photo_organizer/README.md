# Organizador de Fotos

Ferramenta simples e **segura** para colocar ordem numa biblioteca de fotos
bagunçada. Ela resolve quatro problemas de uma vez:

1. **Junta tudo por data** (`Ano/Ano-Mês`), acabando com as inúmeras pastas
   espalhadas que sempre voltam.
2. **Remove fotos duplicadas** — de cada grupo de cópias, mantém a de melhor
   qualidade.
3. **Separa fotos de má qualidade** — tremidas, borradas ou pequenas demais.
4. **Separa fotos tiradas de vídeo** — quadros de gravação, prints de tela e
   capturas.

> **Nada é apagado.** As fotos ruins e duplicadas vão para uma pasta de
> quarentena (`_rejeitadas/`), separadas por motivo. Você revisa com calma e
> apaga só o que quiser.

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

## Resultado

Antes (bagunça típica):

```
Fotos/
├── WhatsApp/…
├── Nova pasta/
├── Nova pasta (2)/
├── Câmera/2023-01/…
├── videos/frame_0001.jpg
└── prints/Screenshot.png
```

Depois:

```
Fotos/
├── 2023/
│   ├── 2023-01/
│   └── 2023-05/
├── 2024/
│   └── 2024-12/
└── _rejeitadas/
    ├── baixa_qualidade/
    ├── de_video/
    └── duplicadas/
```

**Pode rodar quantas vezes quiser**: fotos já organizadas ficam onde estão e a
quarentena não é reprocessada. Rodar de novo não bagunça nada — por isso as
pastas param de "voltar".

## Ajustes finos (opcionais)

| Opção                    | O que faz                                                        | Padrão |
|--------------------------|------------------------------------------------------------------|--------|
| `--aplicar`              | Efetiva de verdade. Sem isto, só simula.                         | (off)  |
| `--saida PASTA`          | Manda o resultado para outra pasta em vez da própria entrada.    | entrada|
| `--suave`                | Afrouxa os limiares (ver tabela abaixo).                         | (off)  |
| `--limite-nitidez N`     | Abaixo disso a foto é considerada borrada. Maior = mais rígido.  | 300    |
| `--min-megapixels N`     | Fotos menores que isso viram "baixa qualidade".                  | 4.0    |
| `--limite-duplicata N`   | Quão parecidas duas fotos precisam ser p/ virar duplicata (0-10).| 10     |
| `--plano`                | Junta tudo numa pasta única em vez de subpastas por data.        | (off)  |
| `--nao-limpar-vazias`    | Não remove as pastas que ficaram vazias.                         | (off)  |

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
