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
