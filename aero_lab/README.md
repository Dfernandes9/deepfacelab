# AERO LAB — Head Swap Foundation

## Missão
Laboratório modular para produção audiovisual autorizada: substituição de cabeça completa, avaliação de integração visual e, em fase posterior, síntese vocal com novas falas e sincronização labial.

## Estado verificado no repositório
- `facelib/FaceType.py`: enumera `HEAD` e `HEAD_NO_ALIGN`.
- `mainscripts/Extractor.py`: aciona landmarks 3D quando `face_type >= FaceType.HEAD`.
- `models/Model_SAEHD/Model.py`: oferece `head` como opção e documenta necessidade de XSeg nos dois conjuntos.
- `main.py`: expõe `extract`, `train`, `merge`, `exportdfm` e comandos de vídeo.
- `requirements-cuda.txt`: usa TensorFlow GPU 2.4.0 e bibliotecas legadas. Compatibilidade moderna não comprovada.

## Etapas e condições de avanço
1. **Inventário estático** (este commit): validar integridade sintática das entradas e presença de pontos de integração. Não prova execução.
2. **Teste não destrutivo**: executar em máquina compatível, com mídia sintética ou autorizada e amostras copiadas.
3. **Head Swap**: extração `head`, alinhamento, máscaras XSeg de origem/destino, SAEHD, composição e avaliação frame a frame.
4. **Controle de qualidade**: rastrear artefatos de contorno/cabelo/pescoço, oclusão, estabilidade temporal, cor, iluminação, identidade e descontinuidade.
5. **Voz posterior**: síntese de voz expressamente autorizada, novas falas, avaliação de timbre/prosódia, sincronização fonema-lábio e composição; manter independente do treinamento facial.

## Segurança dos materiais
- Não modificar nem sobrescrever `master`, originais, modelos treinados ou clones de voz existentes.
- Antes de movimentar arquivos, criar manifesto de hashes SHA-256 e trabalhar sobre cópias.
- Exigir autorização específica das identidades de imagem e voz envolvidas; registrar proveniência e identificar a saída como sintética.
- Não inferir consentimento, emoção ou intenção a partir de aparência de um vídeo.
- Esta branch não executa substituição facial, clonagem vocal nem treinamento.

## Verificação
Na raiz do repositório:
```sh
python3 aero_lab/verify_foundation.py
```
O verificador depende apenas da biblioteca padrão de Python. Ele devolve status PASS/FAIL dos contratos estáticos existentes, sem escrever em qualquer arquivo. O resultado não substitui testes de runtime, GPU, resultados visuais ou segurança.

## Escopo universal: identidade desacoplada do vídeo
Este é um laboratório multi-identidade e multi-projeto. Os cinco vídeos iniciais são apenas amostras de referência, não definem uma pessoa fixa nem um único gênero, formato, iluminação ou cenário. A identidade de origem e o vídeo-alvo são entradas independentes, selecionadas por projeto, com permissões verificáveis.

- **Identity Registry**: uma ou mais coleções de referência autorizadas, com IDs opacos, versões, direitos de uso e origem comprovada. Nenhum nome pessoal é codificado no motor.
- **Media Registry**: qualquer arquivo suportado mediante validação de contêiner, codec, resolução, FPS, orientação, áudio e direitos de uso. A entrada não precisa ter a mesma duração ou câmera das referências.
- **Job Manifest**: associação explícita entre `source_identity_id`, `target_asset_id`, `profile` e opções de saída. Uma identidade pode ser usada em múltiplos vídeos autorizados, e um vídeo pode receber diferentes execuções em projetos separados.
- **Head pipeline**: detecção, tracking, landmarks, XSeg, adaptação geométrica, composição com atenção a cabelo, pescoço, iluminação, oclusão e consistência temporal.
- **Quality Gate**: diagnósticos por frame, detecção de falha e revisão de amostras; falhar com informação explícita em vez de declarar universalidade ou perfeição.
- **Voice stage (futura)**: referência de voz e roteiro configuráveis por job, sem acoplamento a uma identidade fixa; sempre com autorização específica.

A compatibilidade é **orientada a variedade de vídeos**, não uma promessa de resultado impecável para todo vídeo. Perfis, planos difíceis, baixa resolução, oclusões e movimentos bruscos podem exigir revisão manual.

Contrato de configuração e exemplo sem dados pessoais: [UNIVERSAL_PROJECT_SPEC.md](UNIVERSAL_PROJECT_SPEC.md).
