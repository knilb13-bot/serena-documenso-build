# Proposta local de build remoto do piloto

Estado: pacote-base publicado no repositório separado, commit `8e779b5759aff87e82b7377f4b4ef84093ec5e52`. Este estado local contém uma proposta adicional de diagnóstico de registro, ainda não publicada nem executada. Não há prova de compilação concluída ou memória mínima.

O executor deste pacote é o repositório **público e separado** já existente, `knilb13-bot/serena-documenso-build`, em runner GitHub hospedado `ubuntu-24.04`. Publicação e execução respeitam a autorização explícita do proprietário e a revisão independente. Este README não amplia essa autorização. Nenhum repositório de app/site será reutilizado.

## Conteúdo a publicar

Publicar exclusivamente os caminhos de `public-files.json`. Não adicionar diretórios irmãos, histórico de trabalho, `.git` local, relatórios do piloto, AGENTS locais, Vault, PDF, envelope, destinatários, bancos, tokens, chaves ou dados de cliente. A lista não inclui este diretório de verificação local. O archive oficial não precisa entrar no repositório: o runner o obtém por commit fixo e confere SHA-256.

- `.github/workflows/build.yml`: build somente por `workflow_dispatch`, confirmação explícita e repositório exato; limite externo total de 30 minutos. O `push` da branch exata `codex/pilot-signing-ui` é uma proposta de diagnóstico de registro: o único job exige explicitamente evento manual e deve ser ignorado no push. Sem cron/PR, Actions checkout ou instalação global.
- `remote_build.py`: aquisição limitada, validações, controlador dos três contêineres isolados, contexto público e hashes. Sem argumento imprime somente plano. `build` exige o executor CI exato e recusa token no ambiente do passo de build.
- `container-build.mjs`: funções derivadas do pipeline já revisado; prune, instalação e build offline. Sem SSH, dados ou credenciais do servidor.
- `patches/signing-ui.patch`: comparação dos cinco arquivos com os bytes do tar oficial fixado. Quatro arquivos substituídos e um helper novo; PDF/envelope/campos/autenticação não fazem parte do patch.
- `patch-manifest.json`: identidade upstream e hashes originais/finais do patch, logo e recursos propostos.
- `Dockerfile.output`: contexto futuro, sem RUN; copia apenas build/public sobre a mesma imagem runtime fixada. Não é aplicado pelo workflow.
- `assets/serena-nobre.png`: mesma logomarca pública aprovada, sem redesenho.
- `LICENSE`: texto AGPLv3 preservado byte a byte do archive oficial.

## Proposta limitada de diagnóstico de registro

O arquivo manual existe na branch padrão, mas as leituras do registro e a tentativa REST retornaram ausência de workflow. Permissões gerais e a lista de políticas consultadas não explicaram a ausência. A causa continua não comprovada. Acrescentar o evento oficial push é uma experiência diagnóstica proposta, não uma correção demonstrada ou uma exigência documentada do GitHub.

Após revisão independente, uma publicação desta alteração na branch exata pode fazer o GitHub avaliar o arquivo e registrar o workflow ou expor erro de template. O único job possui três condições simultâneas: `github.event_name == 'workflow_dispatch'`, `inputs.confirm_public_build == true` e repositório exato. Em push, a primeira condição é falsa; a configuração deve ignorar o job antes da alocação de runner. Essa propriedade ainda precisa ser observada no GitHub. Não há job diagnóstico, comando de build ou release permitido pelo push.

O diagnóstico fica limitado a uma publicação desta alteração e às leituras do run/registro resultantes. Aceite: registro aparece ou diagnóstico de template permite apontar uma causa; eventual execução do evento push deve ter o único job ignorado, sem runner ou steps executados. Se continuar sem registro/diagnóstico ou aparecer job de push executável, parar e reconciliar. Não repetir push, renomear arquivo, mudar permissões ou adicionar outros eventos por tentativa. Uma compilação real continua exclusivamente manual, limitada à única execução autorizada de até 30 minutos.

## Execução proposta após autorização

1. Reconciliar o pacote já publicado com sua baseline e a revisão independente. A proposta diagnóstica muda somente workflow e README públicos; não cria outro repositório nem importa diretórios/histórico alheios. Conferir diff e árvore antes de publicar. Não usar `git add -A` no projeto existente.
2. Somente depois de confirmar o registro do workflow e as condições da execução autorizada, disparar manualmente **Build público Documenso 2.21.1**, com `confirm_public_build=true`. O próprio workflow obtém seu commit público exato por git HTTPS, sem gravar token no checkout. O token efêmero do GitHub só é fornecido ao passo final de release, com `contents:write` limitado a esse repositório. Nenhum segredo de VPS/SMTP/banco é cadastrado no CI.
3. O driver baixa o archive `8707e33c124e4b1a68dde92d5e05178c9aabd0be` do GitHub oficial, confere hash `32e46cd9604aadd2864b97900367134ef8a47c4fd5352c2573ab07dd1c8d27f2`, inspeciona todos os nomes e rejeita links/arquivos especiais. Confere os quatro originais e a ausência do helper; aplica o patch e verifica cada hash final. O lock original permanece `92767f6b48c0710364669c0270015a3d3f4e4b8ebbc00ac931d97041fe4b1fce`.
4. Obtém apenas os dois tarballs de bootstrap fixados no lock: Turbo e plataforma Linux 2.10.5, validando o SRI mais forte. Puxa a imagem `documenso/documenso@sha256:04ac1003006e1086404e5b3aa9d748e84d8c0fd4cc5ee28938d6face9eb799ec`; Node deve ser 24.22.1 e npm 11.19.1. Não instala Node, npm, apk ou ferramenta global.
5. Faz prune oficial em contêiner offline, usando diretamente o binário Linux. O hash do lock derivado deve permanecer `9c2d29755f01aa0d002145521c66d55656309c49d5c2bb29daee3363aabdf775`; compara versão/URL/SRI de cada dependência com o lock original. A lacuna app-tests não pode entrar na closure. Se divergir, encerra sem alterar locks ou procurar outra versão.
6. Adquire a closure exata pelo registro oficial, sem hooks, e valida SRI. Dentro do builder sem rede, carrega cache em lotes e executa `npm ci --offline --ignore-scripts --include=dev --no-audit --no-fund`. Não usa instalação runtime da VPS e não executa lifecycle automaticamente.
7. A etapa de build usa somente chamadas explícitas do pipeline revisado: bins públicos pinados da imagem para Prisma/Skia, `patch-package --error-on-fail`, smoke de Skia/esbuild/sharp, `prisma generate`, `lingui compile`, `react-router typegen`, `tsc`, `react-router build`, Rollup e cópias build/public. Não executa migrate, seed, servidor, OAuth ou chamada a banco. O ambiente possui stubs sintéticos de compilação, não segredos reais. Se qualquer componente nativo ou gerador faltar, o contêiner sem rede falha; não baixa substituto.
8. Só depois das três etapas bem-sucedidas, empacota build/public e Dockerfile sem outros diretórios, gera manifesto por arquivo e SHA-256. Publica uma release pública de nome único `build-RUN_ID-RUN_ATTEMPT`, com asset menor que 2 GiB, manifesto, resultados e log público. Não usa Actions Artifact nem cache pago; não publica imagem/serviço e não acessa a VPS.

## Recursos e parada

O runner público standard `ubuntu-24.04` é descrito pela documentação oficial do GitHub como 4 CPUs e 16 GB de memória. Isso é capacidade nominal documentada, não medição ou teste deste build. A política gratuita/eligibilidade da conta precisa ser conferida antes do disparo; não habilitar runner maior, serviço pago ou compra de minutos.

Cada contêiner temporário usa 2 CPUs, 10 GiB de RAM, heap Node de 8 GiB, 512 PIDs e swap adicional zero, rootfs read-only, UID 1001, sem capabilities e sem rede. Só monta source/cache/scripts públicos em leitura e work/out dedicados em escrita, sem socket Docker, banco, certificado, configuração privada ou volume da VPS. O controlador exige 12 GiB de MemAvailable antes de cada contêiner, reserva mínima de 2 GiB durante a etapa e 12 GiB livres de disco inicial. São limites conservadores propostos; se não forem atendidos, encerra, sem reduzir reserva por tentativa.

As etapas compartilham prazo de 24 minutos após pull da imagem; o workflow inteiro tem limite de 30 minutos. Timeout, OOM, divergência de hash/SRI, origem inesperada, falta de disco, dependência ausente ou resultado incerto interrompem a tentativa. Não há retry automático nem aumento de limite; outro disparo exige examinar o resultado e nova decisão. A limpeza trata exclusivamente o CID criado pelo controlador. O runner é descartável e não hospeda serviços do piloto. O resultado de cada CID entra no log do job; em falha, também entram trechos de até 256 KiB dos logs públicos do contêiner e do builder. A retenção desses logs segue a configuração do repositório GitHub. A árvore temporária de uma falha não é publicada automaticamente; em sucesso, a release preserva build, manifesto, resultados e log completo.

Aquisição exige GitHub oficial/codeload, registro `registry.npmjs.org` e Docker Hub para a imagem pinada, incluindo endpoints de autenticação/CDN operados pelo Docker necessários ao pull. O token GitHub é usado exclusivamente para release no próprio repositório. Não há credencial de Docker Hub; se autenticação adicional, gasto, outra origem ou dependência fora do lock for exigida, parar. Não há enforcement por firewall customizado: o código limita origens da aquisição Python e o Docker recebe somente a referência pinada; a compilação fica efetivamente sem rede.

## Depois de uma compilação bem-sucedida

Baixar release e manifesto por commit/run exatos, verificar hashes e inventário antes de transferir qualquer artefato para a VPS. Release pública não equivale a implantação. O próximo executor deve conferir que nenhum segredo entrou no bundle ou log, que o ambiente público coincide com a baseline atual, e que a imagem runtime continuará a pinada. A promoção deve usar um contexto novo e revisado; os helpers privados antigos de upload esperam gates de outro executor e não podem receber este resultado como se esses gates existissem.

Publicação na VPS permanece etapa separada, com aprovação específica, liberação dos alvos compartilhados e preservação da imagem/configuração anterior. Não executar migrations. Conferir imagem, CSS/assets, PDF aprovado, campos, papéis, configuração e rollback sem restaurar banco/assinaturas. Validar desktop, celular, paisagem e zoom 200%, inclusive guia expandido e documento legível, antes de Luiz assinar pessoalmente os dois papéis. Este pacote não homologa aparência, email, conteúdo jurídico, assinatura, recuperação ou arquivamento.

A logomarca da página usa a configuração nativa da equipe. Este build não ativa branding: a configuração da equipe do piloto precisa ser aplicada pelo método nativo autenticado, com baseline, escopo da equipe e autorização próprios. Outros envelopes da mesma equipe podem receber a marca. O logo público permanece disponível no pacote para essa operação futura. O email pertence ao publicador de automação separado; não é enviado ou implantado por este workflow.

## Evidência local e estimativa

Os bytes originais foram lidos diretamente do archive oficial local, verificado pelo SHA-256 completo. A conferência local de patch e sintaxe não executa Docker, npm, build, rede ou GitHub. O resultado e os hashes finais constam de `LOCAL-VALIDATION.json` e `LOCAL-FILES.json`, que não fazem parte da allowlist pública.

Tempo de instalação/build: sem dado experimental neste executor. Os limites de 24/30 minutos são condições de parada, não promessa de conclusão.
