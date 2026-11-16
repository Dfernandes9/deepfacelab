# Head Swap — quality gate (proposta)

## Pré-condições
- Confirmação documentada de autorização para todas as identidades utilizadas.
- Entradas originais preservadas, hashes, cópias de trabalho, resolução/fps e metadados documentados.
- Hardware/GPU e ambiente Python reproduzíveis; teste de import e smoke test aprovados.
- Facesets head de origem e destino, alinhamento e máscaras XSeg revisadas.
 
## Métricas e revisão
| Etapa | Verificação | Critério |
| --- | --- | --- |
| Extração | Detecção e landmarks em planos frontal, perfil e oclusões | Reportar falhas com timestamps |
| Segmentação | Máscaras XSeg nos dois conjuntos | Revisão manual em frames difíceis |
| Geometria | Cabeça, pescoço, escala e perspectiva | Sem distorção anatômica evidente |
| Composição | Cor, bordas, cabelos e iluminação | Sem halos e recortes perceptíveis |
| Temporal | Consistência em movimento | Sem flicker, saltos ou trocas de identidade |
| Render | FPS, sincronismo, áudio e duração | Igualdade com especificação de projeto |
| Proveniência | Modelo, parâmetros, hashes e autorização | Rastreável e saída identificada como sintética |

Não há benchmark ou limiar de aceitação numérico validado nesta branch. Definir após o primeiro material de teste autorizado.

## Fase 2: voz e novas falas
Manter síntese e sincronização separadas da troca de cabeça. Registrar autorização de voz, referência, versão do sintetizador, roteiro, áudio gerado, alinhamento temporal e testes auditivos. Não sobrescrever vozes/clones anteriores.

## Restrições atuais
O verificador estático não demonstra compatibilidade CUDA/TensorFlow, treinamento bem-sucedido, qualidade visual nem sincronização labial.
