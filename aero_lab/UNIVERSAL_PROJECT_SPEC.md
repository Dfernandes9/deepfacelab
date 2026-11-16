# AERO LAB — especificação de projeto universal (v0.1)

## Princípio
Nenhuma pessoa ou vídeo deve estar embutido no código. O motor processa jobs independentes, preservando materiais originais e identidade(s) autorizadas. A configuração não contém mídias nem dados biométricos.

## Componentes previstos
1. `identity_registry/`: referências autorizadas com IDs não identificáveis, versões e escopo de consentimento.
2. `media_registry/`: vídeos e imagens de entrada com identificador, hash SHA-256, especificação técnica e proveniência.
3. `jobs/`: manifestos que referenciam identidade, mídia e configurações sem copiar dados pessoais.
4. `engines/head_swap/`: adaptadores de extração `head`, tracking, alinhamento 3D, XSeg, SAEHD, composições e pós-processamento.
5. `engines/voice/` (fase futura): áudio de referência autorizado, falas novas, prosódia e sincronização.
6. `qa/`: relatórios por sequência e timestamps; casos difíceis para avaliação humana.

## Exemplo de manifesto conceitual
```json
{
  "schema_version": "0.1",
  "job_id": "example-job-001",
  "source_identity_id": "authorized-identity-001",
  "target_asset_id": "authorized-video-001",
  "mode": "head",
  "pipeline_profile": "quality",
  "target_features": {
    "preserve_fps": true,
    "preserve_audio": true,
    "temporal_consistency_check": true,
    "manual_review_on_failure": true
  },
  "voice": {
    "enabled": false,
    "voice_reference_id": null,
    "script_asset_id": null
  },
  "output": {
    "synthetic_content_label": true,
    "preserve_original": true
  }
}
```

Este é um **contrato de design**, não um arquivo aceito hoje pelo `main.py`. Não contém caminhos absolutos, nomes de pessoas nem materiais reais.

## Critérios de aceite futuros
- Diversas identidades e vídeos independentes, selecionados por job, sem alterar o código.
- Importação controlada para vídeos verticais/horizontais, fps variável, resoluções e codecs diferentes, com erros explicativos em caso de formato incompatível.
- Geometria plausível da cabeça e pescoço; adequação de cor, luz, cabelo e sombras; rastreamento e consistência entre frames.
- Métricas e revisão humana de falhas de oclusão, perfil, mudança brusca de pose e movimento rápido.
- Logs versionados, hashes de entradas/saídas e proveniência.
- Uso exclusivo de identidade e voz com autorização documentada; evitar falsificação enganosa e conteúdo íntimo não consensual.

## Fora do escopo da implementação atual
- O manifesto ainda não possui parser/runner.
- Não há benchmark comprovando desempenho ou sucesso em qualquer vídeo.
- Não há garantia de perfect head swap nem clone de voz integrado.

## Implementação inicial (16/11/2026)
O validador independente está em [project_loader.py](project_loader.py). Executa apenas leitura, verifica existência e extensões de arquivos, hashes SHA-256, IDs, permissões declaradas e modo de saída. Não realiza extração, troca de cabeça, criação de voz, renderização ou auditoria jurídica da autorização. O campo `authorization_record` é uma referência declaratória, ainda não verificável criptograficamente.

### Comandos
A partir da raiz do repositório e com Python 3.9+:
```sh
python3 -m unittest aero_lab.test_project_loader -v
python3 -m aero_lab.project_loader ./job.json --workspace ./meu_acervo
```

### Campos atualmente obrigatórios do manifesto
`schema_version=0.1`, `job_id`, `identities` (cada uma com `id`, `head_swap_authorized=true`, `authorization_record`), `assets` (cada um com `id`, `kind`, `path`, `sha256`), `source_identity_id`, `target_asset_id`, `target_use_authorized=true`, `target_authorization_record`, `mode=head`, `pipeline_profile=quality|balanced`, `voice.enabled=false`, `output.preserve_original=true`, `output.synthetic_content_label=true`.

Exemplo mínimo (ajustar o hash aos bytes reais do vídeo):
```json
{
  "schema_version": "0.1",
  "job_id": "ensaio-001",
  "identities": [{"id": "identity-001", "head_swap_authorized": true, "authorization_record": "consent-001"}],
  "assets": [{"id": "video-001", "kind": "video", "path": "video.mp4", "sha256": "COLOQUE_AQUI_O_SHA256_REAL"}],
  "source_identity_id": "identity-001",
  "target_asset_id": "video-001",
  "target_use_authorized": true,
  "target_authorization_record": "license-001",
  "mode": "head",
  "pipeline_profile": "quality",
  "voice": {"enabled": false},
  "output": {"preserve_original": true, "synthetic_content_label": true}
}
```

O resultado esperado de uma validação bem-sucedida é `VALIDATED_NOT_RENDERED`. Nenhum vídeo real foi processado ou modelo treinado nesta etapa. A suíte de testes utiliza arquivos sintéticos de bytes e não verifica decodificação de vídeo.
