# Proposta local de build remoto do piloto

Estado: correção local do prune e exportação de imagem runtime preparadas, ainda sem nova execução CI. A primeira execução manual real, `40959677691`, falhou antes de npm ci, typecheck e compilação. O fix do prune permanece preservado. Empacotamento da imagem e startup direto são propostas adicionais explícitas para revisão e consentimento antes de publicar/executar. Uma nova execução manual de até 30 minutos ainda não está autorizada.

O executor deste pacote é o repositório **público e separado** já existente, `knilb13-bot/serena-documenso-build`, em runner GitHub hospedado `ubuntu-24.04`. Publicação e execução respeitam a autorização explícita do proprietário e a revisão independente. Este README não amplia essa autorização. Nenhum repositório de app/site será reutilizado.

## Conteúdo a publicar

Publicar exclusivamente os caminhos de `public-files.json`. Não adicionar diretórios irmãos, histórico de trabalho, `.git` local, relatórios do piloto, AGENTS locais, Vault, PDF, envelope, destinatários, bancos, tokens, chaves ou dados de cliente. A lista não inclui este diretório de verificação local. O archive oficial não precisa entrar no repositório: o runner o obtém por commit fixo e confere SHA-256.

- `.github/workflows/build.yml`: build somente por `workflow_dispatch`, confirmação explícita e repositório exato; limite externo total de 30 minutos. O `push` da branch exata `codex/pilot-signing-ui` é uma proposta de diagnóstico de registro: o único job exige explicitamente evento manual e deve ser ignorado no push. Sem cron/PR, Actions checkout ou instalação global.
- `remote_build.py`: aquisição limitada, três contêineres de compilação, hashes e proposta de empacotamento COPY-only da imagem no mesmo CI, seguida de docker image save e gzip. Sem argumento imprime somente plano. `build` exige o executor CI exato e recusa token no ambiente do passo de build.
- `container-build.mjs`: funções derivadas do pipeline já revisado; prune, instalação e build offline. Sem SSH, dados ou credenciais do servidor.
- `patches/signing-ui.patch`: comparação dos cinco arquivos com os bytes do tar oficial fixado. Quatro arquivos substituídos e um helper novo; PDF/envelope/campos/autenticação não fazem parte do patch.
- `patch-manifest.json`: identidade upstream e hashes originais/finais do patch, logo e recursos propostos.
- `Dockerfile.output`: FROM fixado, duas instruções COPY e CMD explícito. A proposta o aplica somente no executor GitHub, sem RUN, dependências, dados da VPS ou credenciais; a VPS receberá imagem exportada, sem compilar.
- `assets/serena-nobre.png`: mesma logomarca pública aprovada, sem redesenho.
- `LICENSE`: texto AGPLv3 preservado byte a byte do archive oficial.

## Correção local do prune

A falha ocorreu ao comparar um arquivo raiz produzido pelo Turbo com a fonte original. A reprodução offline identifica `turbo.json`: o original tem 5.580 bytes e SHA-256 `9b4242cff9e26533fffec58b29ece409ba027f3cec6fa3d1e037a6dd951643fd`; a representação reserializada tem 5.683 bytes e SHA-256 `fcc59601f1ceecc124b943e096e58cfccea79bcdfb5e8c451bd34d65ef878b55`. Ordenação de chaves, formatação e newline diferem; o valor JSON é profundamente equivalente. Esse é o mesmo par preservado na recuperação histórica do piloto. O log genérico da execução atual não informa o caminho ou hashes; o vínculo entre esse run e a reprodução é uma inferência sustentada pelas mesmas fontes, versão Turbo e etapa de falha.

O fix restaura os bytes originais somente para esse nome e esse par exato de hashes. Antes, preserva os bytes derivados em `prune-root-recovery-backup/turbo.derived.json`, fora da árvore compilada; registra os hashes em `root_file_recovery` e no log. Qualquer outro conteúdo divergente continua bloqueado, mesmo se for JSON semanticamente igual. Não altera lock, versão, dependências, limites de memória, workflow, políticas, credenciais ou serviços.

A conferência offline executou 16 testes reais de arquivos: 14 passaram, nenhum falhou e dois foram pulados porque o executor Windows não permite criar symlink. Esses dois guardas permanecem não exercitados nesse executor. O builder anterior reproduziu a falha com os mesmos bytes; o novo preservou backup, restaurou o original e manteve a recusa dos conflitos. O resultado não comprova npm ci, componentes nativos, compilação ou aparência.

O diagnóstico de registro por evento push é anterior a este fix. O único job continua condicionado ao evento manual, confirmação true e repositório exato. A correção não dispara outro evento nem autoriza nova execução.

## Execução proposta após autorização

1. Reconciliar o pacote já publicado com a baseline atual e a revisão independente do fix. O pacote completo muda cinco arquivos públicos em relação à versão inicial executada: container-build.mjs (fix do prune preservado), remote_build.py, Dockerfile.output, .github/workflows/build.yml e README.md. A preparação da imagem acrescenta quatro mudanças sobre o snapshot anterior, sem alterar o fix do prune. Testes e evidências locais ficam fora da allowlist. Conferir diff e árvore antes de publicar; não criar outro repositório ou importar histórico alheio. Não usar `git add -A` no projeto existente.
2. Somente depois da revisão do fix, nova autorização específica e confirmação do registro/commit exato, disparar manualmente **Build público Documenso 2.21.1**, com `confirm_public_build=true`. O próprio workflow obtém seu commit público exato por git HTTPS, sem gravar token no checkout. O token efêmero do GitHub só é fornecido ao passo final de release, com `contents:write` limitado a esse repositório. Nenhum segredo de VPS/SMTP/banco é cadastrado no CI.
3. O driver baixa o archive `8707e33c124e4b1a68dde92d5e05178c9aabd0be` do GitHub oficial, confere hash `32e46cd9604aadd2864b97900367134ef8a47c4fd5352c2573ab07dd1c8d27f2`, inspeciona todos os nomes e rejeita links/arquivos especiais. Confere os quatro originais e a ausência do helper; aplica o patch e verifica cada hash final. O lock original permanece `92767f6b48c0710364669c0270015a3d3f4e4b8ebbc00ac931d97041fe4b1fce`.
4. Obtém apenas os dois tarballs de bootstrap fixados no lock: Turbo e plataforma Linux 2.10.5, validando o SRI mais forte. Puxa a imagem `documenso/documenso@sha256:04ac1003006e1086404e5b3aa9d748e84d8c0fd4cc5ee28938d6face9eb799ec`; Node deve ser 24.22.1 e npm 11.19.1. Não instala Node, npm, apk ou ferramenta global.
5. Faz prune oficial em contêiner offline, usando diretamente o binário Linux. O hash do lock derivado deve permanecer `9c2d29755f01aa0d002145521c66d55656309c49d5c2bb29daee3363aabdf775`; compara versão/URL/SRI de cada dependência com o lock original. A lacuna app-tests não pode entrar na closure. Se divergir, encerra sem alterar locks ou procurar outra versão.
6. Adquire a closure exata pelo registro oficial, sem hooks, e valida SRI. Dentro do builder sem rede, carrega cache em lotes e executa `npm ci --offline --ignore-scripts --include=dev --no-audit --no-fund`. Não usa instalação runtime da VPS e não executa lifecycle automaticamente.
7. A etapa de build usa somente chamadas explícitas do pipeline revisado: bins públicos pinados da imagem para Prisma/Skia, `patch-package --error-on-fail`, smoke de Skia/esbuild/sharp, `prisma generate`, `lingui compile`, `react-router typegen`, `tsc`, `react-router build`, Rollup e cópias build/public. Não executa migrate, seed, servidor, OAuth ou chamada a banco. O ambiente possui stubs sintéticos de compilação, não segredos reais. Se qualquer componente nativo ou gerador faltar, o contêiner sem rede falha; não baixa substituto.
8. Só depois das três etapas bem-sucedidas, preserva o pacote build/public + Dockerfile e prepara contexto mínimo novo com esses mesmos arquivos, conferidos por hash. No mesmo executor GitHub, usa docker build --network=none --pull=false com Dockerfile COPY-only sobre a base já puxada pelo digest fixo, sem RUN, ARG, ENTRYPOINT novo ou dependências. Confere image ID, prefixo das layers da base, plataforma, usuário, diretório, ENV e ENTRYPOINT preservados e o CMD esperado. Não inicia a imagem nem executa o servidor.
9. Exporta a imagem local por docker image save, compacta em gzip, calcula hashes em streaming e publica documenso-runtime-image.tar.gz + runtime-image-manifest.json junto aos artefatos anteriores na release pública de nome único `build-RUN_ID-RUN_ATTEMPT`. Cada asset deve ficar estritamente abaixo de 2 GiB; se exceder, a etapa falha sem release. Não usa Actions Artifact, cache pago, push para registry, SSH ou acesso à VPS.

## Imagem pronta para carregar, sem migrations no startup

O novo CMD proposto é:

```json
["sh","-c","export NEXT_PRIVATE_DIRECT_DATABASE_URL=\"${NEXT_PRIVATE_DIRECT_DATABASE_URL:-$NEXT_PRIVATE_DATABASE_URL}\"; HOSTNAME=0.0.0.0 exec node build/server/main.js"]
```

Ele preserva apenas o fallback da URL direta e HOSTNAME do start.sh oficial, sem chamar esse script. O start.sh de referência tem SHA-256 bb1720ba853e21020c86078220e541d8a3d12e3f5d74d74e8b8438430a6911b4 e chama prisma migrate deploy. O novo CMD não executa migrations nem os banners/checks informativos do script. O ENTRYPOINT da base é preservado; se não for o entrypoint padrão Node já previsto, o empacotamento para. O usuário runtime é preservado exatamente como nodejs, conforme captura real; COPY --chown=1001:1001 não é usado para inferir Config.User. Nenhuma configuração ou credencial real entra na imagem do CI.

O manifesto da imagem registra image ID, digest e ID da base, CMD/ENTRYPOINT, usuário, working directory, hash do Dockerfile, hashes do contexto, tamanho e SHA-256 do arquivo exportado. O formato é docker image save compactado, aceito por docker image load. O resultado permanece identificado como runtime_tested=false: exportar uma imagem não homologa seu startup, conexão com banco, PDF ou assinatura.

O empacotamento compartilha o prazo de 24 minutos do controlador e o limite externo de 30 minutos do workflow. Exige folga de disco calculada a partir do tamanho da imagem, contexto, teto de asset e reserva de 1 GiB; repete a conferência antes da exportação e durante a compressão. A memória/CPU/512 PIDs/swap zero dos contêineres de compilação permanecem iguais. O uso efetivo de memória do empacotamento COPY-only pelo daemon Docker do runner ainda não foi medido e não é apresentado como protegido pelo cgroup do compilador. Se disco, tempo, metadados ou tamanho do asset não atenderem aos checks, parar; sem ampliar limites ou repetir automaticamente.

Testes locais dessa proposta: 16 testes offline passaram, usando doubles explícitos para comandos Docker e arquivos sintéticos para save/gzip/hash. Não executaram Docker, compilação, servidor ou rede e não demonstram que a imagem real caberá no limite de 2 GiB ou terminará no prazo.

## Recursos e parada

O runner público standard `ubuntu-24.04` é descrito pela documentação oficial do GitHub como 4 CPUs e 16 GB de memória. Isso é capacidade nominal documentada, não medição ou teste deste build. A política gratuita/eligibilidade da conta precisa ser conferida antes do disparo; não habilitar runner maior, serviço pago ou compra de minutos.

Cada contêiner temporário usa 2 CPUs, 10 GiB de RAM, heap Node de 8 GiB, 512 PIDs e swap adicional zero, rootfs read-only, UID 1001, sem capabilities e sem rede. Só monta source/cache/scripts públicos em leitura e work/out dedicados em escrita, sem socket Docker, banco, certificado, configuração privada ou volume da VPS. O controlador exige 12 GiB de MemAvailable antes de cada contêiner, reserva mínima de 2 GiB durante a etapa e 12 GiB livres de disco inicial. São limites conservadores propostos; se não forem atendidos, encerra, sem reduzir reserva por tentativa.

As etapas compartilham prazo de 24 minutos após pull da imagem; o workflow inteiro tem limite de 30 minutos. Timeout, OOM, divergência de hash/SRI, origem inesperada, falta de disco, dependência ausente ou resultado incerto interrompem a tentativa. Não há retry automático nem aumento de limite; outro disparo exige examinar o resultado e nova decisão. A limpeza trata exclusivamente o CID criado pelo controlador. O runner é descartável e não hospeda serviços do piloto. O resultado de cada CID entra no log do job; em falha, também entram trechos de até 256 KiB dos logs públicos do contêiner e do builder. A retenção desses logs segue a configuração do repositório GitHub. A árvore temporária de uma falha não é publicada automaticamente; em sucesso, a release preserva build, manifesto, resultados e log completo.

Aquisição exige GitHub oficial/codeload, registro `registry.npmjs.org` e Docker Hub para a imagem pinada, incluindo endpoints de autenticação/CDN operados pelo Docker necessários ao pull. O token GitHub é usado exclusivamente para release no próprio repositório. Não há credencial de Docker Hub; se autenticação adicional, gasto, outra origem ou dependência fora do lock for exigida, parar. Não há enforcement por firewall customizado: o código limita origens da aquisição Python e o Docker recebe somente a referência pinada; a compilação fica efetivamente sem rede.

## Depois de uma compilação bem-sucedida

Baixar release e os dois manifestos por commit/run exatos, verificar hashes/inventário e revisar ausência de segredos antes de transferir artefatos para a VPS. Release pública não equivale a implantação. A VPS usará docker image load --input documenso-runtime-image.tar.gz e verificará o image ID e CMD contra runtime-image-manifest.json; não executará docker build, npm ou compilação. A referência da base é preservada nas layers, enquanto o ID da nova imagem será diferente. Os helpers privados antigos não podem tratar esse resultado como se possuísse os gates do executor antigo.

Publicação na VPS permanece etapa separada, com aprovação específica, liberação dos alvos compartilhados e preservação da imagem/configuração anterior. Antes de promover, conferir que o compose efetivo não sobrescreve CMD/ENTRYPOINT para reintroduzir start.sh ou migrations. Não executar migrations. Conferir imagem, CSS/assets, PDF aprovado, campos, papéis, configuração e rollback sem restaurar banco/assinaturas. Validar desktop, celular, paisagem e zoom 200%, inclusive guia expandido e documento legível, antes de Luiz assinar pessoalmente os dois papéis. Este pacote não homologa aparência, email, conteúdo jurídico, assinatura, recuperação ou arquivamento.

A logomarca da página usa a configuração nativa da equipe. Este build não altera branding; o estado real da marca será revalidado na promoção, sem presumir necessidade de novo upload ou ativação. O logo público permanece disponível para conferência. Outros envelopes da mesma equipe podem receber a configuração nativa. O email pertence ao publicador de automação separado; não é enviado ou implantado por este workflow.

## Evidência local e estimativa

Os bytes originais foram lidos diretamente do archive oficial local, verificado pelo SHA-256 completo. A conferência local de patch e sintaxe não executa Docker, npm, build, rede ou GitHub. O resultado e os hashes finais constam de `LOCAL-VALIDATION.json` e `LOCAL-FILES.json`, que não fazem parte da allowlist pública.

Tempo de instalação/build: sem dado experimental neste executor. Os limites de 24/30 minutos são condições de parada, não promessa de conclusão.
