# Milestones

Onde o WatchAI está e o que falta. Cada item diz **o que é**, **por que importa**
e **onde mexer** — para dar para pegar um e fazer sem redescobrir o contexto.

Atualizado em 2026-09-28.

---

## ✅ Feito

### M0 — camada visual (1.0.0)

- [x] Dashboard: header com resumo global, painel SESSIONS, EVENT STREAM, keybar
- [x] Semáforo de 3 lâmpadas por card (a identidade do produto)
- [x] Visões CARDS e LIST, modal de detalhes, ajuda
- [x] Layout responsivo de 20×10 a 300×80, sem vão morto
- [x] Bip pelo servidor de som (toca com a aba em segundo plano)
- [x] Suíte headless + CI


### M1 — temas

- [x] 8 paletas (WatchAI, Light, Dark, Night Owl, Vampire, Cyberpunk, Steampunk, Grey)
- [x] Preview ao vivo: mover a seleção aplica no dashboard inteiro
- [x] Persistência em `~/.config/watchai/config.json`
- [x] Teste que garante que toda paleta fornece cada variável `$aw-*` do TCSS


### M2 — detecção real

- [x] Varredura de processos (`psutil`), em thread, a cada 2 s
- [x] Um card por terminal (tty; no Windows, o shell ancestral)
- [x] Agentes listados dentro do card, cada um com o seu estado
- [x] Desduplicação da árvore de processos (o `codex` são 3 processos, 1 agente)
- [x] Reconhecimento por programa/pacote — um plugin com "claude" no caminho não conta
- [x] Diário do Claude Code e do Codex: READY · WORKING · INPUT · WAITING
- [x] Ciclo do terminal: IDLE → OFFLINE → aviso aos 5 min → some aos 7
- [x] `--mock`, `--theme`, `--version`
- [x] CI em Ubuntu (3.10–3.14), Windows e macOS


### M3 — o aviso chega em você (1.1.0)

- [x] **Semáforo com mais presença**: carcaça tingida da cor acesa e halo atrás
      da lâmpada (fundo da própria cor), largura de 5 → 7 colunas
- [x] **Aviso em READY, INPUT e ERROR**, com **um timbre por estado** — avisar
      os três com o mesmo som obrigaria a olhar a tela para saber qual foi
- [x] **Notificação do sistema** (`notify-send` · `osascript` · toast por
      PowerShell), **só quando o WatchAI não está em foco**: se você já está
      olhando, o pop-up é ruído
- [x] Debounce **por timbre**: rajada do mesmo aviso vira um bip só, mas
      READY seguido de ERROR toca os dois
- [x] `B` liga/desliga os dois e a escolha fica salva entre execuções
- [x] **Tempo real do estado**: `for MM:SS` conta da hora que o diário registrou,
      não de quando o app abriu (carimbo no futuro é aparado, para não virar
      contador negativo)
- [x] **ERROR de verdade no Claude Code**: `isApiErrorMessage` pega limite de
      uso e token expirado — a sessão que parou e não volta sozinha


### M4 — mais agentes

- [x] **Atividade por ferramenta para qualquer agente**: sem diário, o que ele
      está fazendo é o processo filho que ele abriu (`running npm test`),
      ignorando processos auxiliares do próprio agente
- [x] **OpenCode**: leitor escrito a partir do layout do storage
      (`session/{info,message,part}`) — ⚠️ **não validado contra sessão real**
- [x] ~~**Gemini CLI**~~ — **não dá com o que ele grava hoje**: o
      `~/.gemini/tmp/<projeto>/logs.json` registra só as mensagens do usuário,
      sem resposta, sem ferramenta e sem fim de turno


### M5 — permanência e distribuição

- [x] **Histórico do EVENT STREAM entre execuções** (`~/.config/watchai/events.json`)
- [x] **Instalador no repositório**: `scripts/install-linux.sh` (comando no PATH,
      lançador no menu, atalho opcional na área de trabalho, `--uninstall`)
- [x] Ícone versionado em `assets/watchai.svg`
- [x] Landing page atualizada (`docs/index.html`)
- [x] Metadados do pacote (descrição, URLs) e versão 1.1.0
- [x] **Release 1.1.0** publicada (tag `1.1.0`)

---


### M6 — chegar na janela (pós-1.1.0)

- [x] **Semáforo idêntico ao ícone** (`assets/watchai.svg`): carcaça de contorno
      cyan, interior escuro, lâmpada acesa com halo
- [x] **`G` leva você até a janela** da sessão selecionada — `System Events` no
      macOS, `AppActivate` no Windows, `wmctrl`/`xdotool` no X11 (título
      desempata quando o servidor de terminal hospeda várias janelas) e
      `org.freedesktop.Application.Activate` no Wayland — este último **não
      funciona**, como o M10 descobriu: ele responde sucesso e o compositor
      ignora o pedido
- [x] **Sino na tty da sessão**: marca a aba certa e faz a janela piscar na
      dock — é o que resolve o que o Wayland não deixa resolver
- [x] **`N` liga/desliga a notificação** sem mexer no bip, com interruptor
      próprio no rodapé e escolha salva
- [x] **Modo estreito**: sobram nome, projeto e semáforo — o resto do texto sai,
      porque ler três lâmpadas não precisa de texto


### M7 — o semáforo cresce, o Light funciona, o pipx garante os três

- [x] **Lâmpadas com ~10× a área**: duas linhas cheias com os cantos cortados
      (octógono), carcaça de 9 colunas, cores mais vivas
- [x] **Halo ao lado da bola**, não atrás — atrás, ele preenchia os cantos
      cortados e a bola virava retângulo
- [x] **Tema claro corrigido na raiz**: níveis de apagado/tinta/borda dependem
      da polaridade da paleta; contraste medido antes e depois
- [x] **`⇧A`** no lugar do `G`
- [x] **Window Calls**: foco de janela exato no Wayland quando a extensão existe
- [x] **`pipx` verificado nos três sistemas** por job de CI
- [x] Workflow de publicação no PyPI, inerte até `PYPI_READY`
- [x] `.gitignore` auditado


### M8 — detecção para todo mundo, não só para esta máquina

- [x] **17 agentes conhecidos** no registro (Claude Code, Codex, Gemini,
      Antigravity, OpenCode, Aider, Copilot, Grok, DeepSeek, Qwen, Cursor,
      Crush, Goose, Amp, OpenHands, Plandex, Continue), com `gh copilot` como
      subcomando
- [x] **Agentes definidos pelo usuário** na config — o ecossistema muda toda
      semana e ninguém espera release para ver a própria sessão
- [x] Agente **sem terminal** (dentro de uma IDE) vira card identificado pelo
      processo, em vez de card sem nome
- [x] Teste que percorre o registro inteiro: erro de digitação na tabela viraria
      um agente invisível para quem usa aquele CLI


### M9 — a janela funciona em qualquer tamanho, e o card tem fim

- [x] **Responsividade em dois eixos**: largura manda nas colunas, **altura
      manda no tamanho do card**. Abaixo de 130×30 o card de 13 linhas não
      cabia e nenhum aparecia inteiro
- [x] Escada de formatos: full (13) → short (7) → compact (5) → **micro (1
      linha)**, onde sobram o nome e as três lâmpadas deitadas
- [x] **Semáforo deitado** (`● ● ●`) para janelas minúsculas
- [x] Teste que varre de 20×10 a 300×80: nada estoura, keybar e EVENT STREAM
      nunca somem, semáforo sempre presente
- [x] **Sessão sem agente tem prazo** mesmo com a aba aberta — antes, agente
      encerrado com o terminal vivo deixava o card `IDLE` para sempre


### M10 — o card diz a verdade, e diz de onde

Uma leva inteira de "o app afirmava o que não tinha acontecido". Os dois lados
do produto — o semáforo e o `⇧A` — anunciavam sucesso sem conferir, e cada um
falhava no sentido pior: dizendo que a sessão está livre quando ela não está.

- [x] **`⇧A` prometia foco que não acontecia.** No Wayland, o
      `org.freedesktop.Application.Activate` devolve código zero **mesmo quando
      o compositor ignora o pedido** — e o zero era lido como sucesso. Agora o
      foco é conferido relendo a lista de janelas depois do `Activate`; sem a
      Window Calls, no Wayland, o `Activate` do terminal nem é tentado, porque
      ali ele só produziria sucesso falso. Faltava também o `Unminimize`, sem o
      qual nenhuma janela minimizada volta
- [x] **O mesmo erro existia no Windows e no macOS.** O `AppActivate` devolve
      `True`/`False`, mas o PowerShell sai com código zero nos dois casos; e
      `set frontmost` levanta o **app**, não a janela, e não tira nada da Dock.
      Os dois foram reescritos com restauração da janela minimizada e
      verificação do resultado — ⚠️ **sem execução em máquina real** (ver
      pendências)
- [x] **A janela da sessão passou a ser identificada pela tty.** Com um servidor
      de terminal, todas as janelas têm o mesmo PID, e o título é de quem está
      rodando na aba (o agente escreve o que faz, um player escreve a música).
      O WatchAI escreve um título único na tty, vê qual janela ficou com ele e
      devolve o título de antes. Vale para Window Calls, `wmctrl`, `xdotool` e
      AppleScript
- [x] **Pensamento longo deixou de virar "tarefa concluída".** O diário só é
      escrito quando a mensagem fecha, e um pensamento demorado passa dos dois
      minutos do `FRESCOR` sem gastar CPU — a espera é do outro lado da rede.
      Isso acendia o **verde** e apitava "pode vir buscar" no meio da rodada;
      agora é WAITING (âmbar)
- [x] **Limite de uso do codex virou ERROR.** Ele fecha a rodada com
      `task_complete` e põe o motivo **dentro** do evento (`error.message`, com
      `last_agent_message` nulo) — ler só o tipo dava a sessão como concluída
- [x] **O título do card é o caminho da aba**, igual para todas: `~`,
      `~/Projetos/WatchAI`. Antes era o projeto em maiúsculas, e a aba sem
      projeto legível caía no rótulo da tty (`PTS/9`), que não diz nada sobre de
      qual sessão se trata. Caminho fundo é cortado pela esquerda, porque o que
      identifica está no fim
- [x] **O diretório vem do diário, não do processo.** O `cwd` do processo é onde
      a sessão **abriu**: quem entra no projeto depois mantém o processo na home
      para sempre. No codex isso exigiu duas coisas a mais — ele grava o
      diretório como URI `file://` e só de vez em quando, aninhado, e o último
      registro pode estar megabytes antes do fim do arquivo
- [x] **Antigravity reconhecido**: o executável se chama `agy`, e é binário
      nativo — não há caminho de pacote que sirva de segunda chance
- [x] **`scripts/screenshot.py`**: o caminho para refazer as capturas deixou de
      viver só na cabeça de quem já fez


### M11 — pronto para Windows e macOS, e a tela vazia explica a causa (1.2.0)

Uma leva de "o código trata os três sistemas" para "o código trata os três
sistemas **e avisa quando não consegue**". Nenhum item aqui foi verificado em
máquina Windows ou macOS de verdade — isso continua sendo a pendência número um.

- [x] **O toast do Windows parou de falhar em silêncio.** O `stderr` ia para o
      lixo e o código de saída era ignorado: nada na tela e um processo novo a
      cada mudança de estado. Agora a primeira falha **desliga o mecanismo** e
      guarda o motivo
- [x] **Duas causas prováveis do toast atacadas**: o AUMID passou a ser um
      registrado — com um nome inventado, o Windows cria a notificação e
      simplesmente não a mostra — e ficou anotado que o `pwsh` não projeta
      WinRT, por isso o Windows PowerShell 5.1 vem primeiro
- [x] **Plano B para o bip do Windows**: o `System.Media` não existe no `pwsh`,
      e sem alternativa o aviso sumiria para quem usa o PowerShell novo. Cai em
      `[Console]::Beep`, com uma frequência por estado para os três continuarem
      distinguíveis sem olhar
- [x] **Config do Windows no `%APPDATA%`**, com o caminho antigo preservado
      quando já existe: ninguém perde tema e histórico numa atualização
- [x] **A tela vazia diz a causa certa.** "Nenhum agente aberto" e "não consigo
      ler a tabela de processos" mostravam a mesma frase, e quem caía na segunda
      concluía que o app é quebrado. A varredura passou a informar o porquê
      (`sem-psutil`, `restrito`, `erro`) e cada um tem a sua resposta
- [x] **1.2.0 cortada**: 24 commits e 43 entradas que estavam em `[Não lançado]`


### M12 — a fila curta

- [x] **`S` ordena os cards por atenção**, e não vira o padrão: card que muda
      de lugar sozinho desfaz a memória visual. A seleção segue a sessão, não a
      posição
- [x] **A aba exata, onde ela tem endereço**: a aba de um gnome-terminal não é
      endereçável, mas um painel do tmux é — e de quebra, sessões dentro do
      tmux passaram a ser alcançáveis pelo `⇧A`, que antes não achava janela
      nenhuma porque o agente descende do servidor do tmux
- [x] **Snap empacotado** (`snap/snapcraft.yaml` + build no CI que instala e
      roda o que construiu). Em `classic`, porque sob strict o `⇧A` e a
      notificação ficariam de fora do sandbox — falta só o envio à loja, que
      pede conta e revisão manual

      ⚠️ **Metade dessa justificativa não se sustenta** (apurado em 2026-09-28,
      ver item 3 de "O que ainda falta"): a notificação **atravessa** o strict,
      basta `libnotify-bin` em `stage-packages` e a interface `desktop`, que é
      auto-conectada. O comentário no `snapcraft.yaml` precisa ser corrigido

---

### M13 — a varredura só vê sessão, e o diário não depende da pasta

- [x] **Serviço não é sessão.** O `codex` sobe dois daemons no login
      (`app-server --managed-daemon` e o `pid-update-loop` dele), pendurados no
      `systemd --user`, sem tty e sem terminal por trás. Eles casavam com a
      assinatura do agente, viravam card e ainda adotavam o diário da última
      sessão daquela pasta: dois verdes permanentes anunciando "terminou" para
      sessões que nunca existiram. Descarte por **subcomando**
      (`agents.servico`, casado por posição e igualdade — `claude -p "serve the
      build"` continua sendo sessão) e por **linhagem** (`source._varrer`: sem
      tty e pendurado no supervisor sem passar por shell, emulador ou IDE).
      Agente dentro de IDE, que também não tem tty, continua aparecendo
- [x] **O diário de ontem não é emprestado para a sessão de hoje.** Abrir numa
      pasta com histórico acendia o verde na hora, com a atividade de ontem, e
      não saía mais de lá — a lista de candidatos, uma vez completa, nunca era
      refeita. Corte por mtime (`transcript._parear`) mais revarredura periódica
- [x] **Com o `S` ligado, o ENTER abria os detalhes do card errado.** `selected`
      é índice na ordem **da tela**, e quatro leituras liam a ordem de
      descoberta (`dashboard.action_open`, `select_session`, `action_move`,
      `details.action_step`)
- [x] **O `cwd` do processo virou atalho, e deixou de ser requisito**
      (`transcript.atribuir` casa por tipo, não por pasta). Sem ele — snap
      strict, negativa do macOS — o diário é achado entre os recentes e casado
      pelo relógio, e o projeto sai de dentro dele. É o que destrava o
      confinamento strict
- [x] Dois congelamentos de um ciclo: agente que sai no meio da varredura
      (`psutil.Process` levanta e a leitura inteira virava diagnóstico "erro") e
      diário apagado no meio da ordenação por mtime (levava `None` para **todos**
      os agentes daquele tipo)

### M14 — quanto já foi gasto do plano

O que era a prioridade 2. O desenho apurado em 2026-09-28 foi implementado sem
mudanças de rumo; o que apareceu na implementação está marcado abaixo.

- [x] **`providers/limits.py`**: `Janela`, `Consumo`, o normalizador `consumo()`
      e dois leitores defensivos. Leitura a cada **30 s** (não a cada varredura),
      na mesma thread da varredura — abrir rollout é disco
- [x] **Codex, sem configuração nenhuma**: o último `payload.type ==
      "token_count"` do rollout, com `rate_limits` inteiro
- [x] **`watchai --statusline`**: lê o JSON do agente no stdin, guarda o bloco de
      limite em `~/.config/watchai/limits/claude.json` (tmp + rename, com o pid
      no nome do tmp, porque duas sessões escrevem) e imprime a linha de status.
      Nunca levanta: lixo na entrada ou pasta sem permissão viram linha vazia
- [x] **O bloco é guardado como veio.** A normalização é na leitura, não na
      escrita: quando o formato mudar, quem se adapta é o leitor — sem pedir a
      você para reconfigurar nada
- [x] **Os dois nomes valem** (`used_percent` do codex, `used_percentage` do
      Claude Code), e a janela sem `window_minutes` é reconhecida pelo nome
      (`primary`/`five_hour`…). Nome desconhecido **e** sem tamanho fica de fora:
      rotular de 5 h o que pode ser de outro tamanho é inventar
- [x] **Validação de faixa**, já que o número não é conferível: percentual em
      [0, 100], janela positiva e plausível, reset num tempo que existe (aceita
      milissegundos). Reset ruim custa o "zera em", não a barra
- [x] **A idade do dado à vista**, acima de 5 minutos: `(3h ago)`
- [x] **O reset também tem de caber no tamanho da janela.** A faixa de época
      (2020–2100) é frouxa para uma janela de 5 h: um carimbo adulterado saía como
      `zera em 26755d22h`, absurdo desenhado com cara de informação. Achado
      montando um usuário fictício para provar que o caminho serve a qualquer
      instalação
- [x] **Achado na implementação, e não estava no plano: janela vencida.** O caso
      comum, não o raro — você usou o codex ontem, a janela de 5 h virou de
      madrugada e o rollout guarda os 18% de então. `Janela.vencida()` detecta
      pelo próprio `resets_at`, e a tela mostra `—` em vez de um número morto. É
      a mesma armadilha que o Claude Code corrigiu na 2.1.251
- [x] **No header, não no card** (`widgets/header.py`), uma linha por agente com
      número. Cinza até 75%, amarelo aí, vermelho em 90%. Três variantes por
      largura, e nada abaixo de 20 linhas de terminal
- [x] **`sessions_max_height` agora recebe a altura do header**, que deixou de
      ser a constante 3. O header avisa que cresceu (`AppHeader.Grew`) e o
      Dashboard refaz a conta do teto — sem isso, a barra tirava linhas do EVENT
      STREAM caladas
- [x] **Bug que existia antes e a barra descobriu**: `#sessions-area` era
      focável, então assim que o conteúdo passava do teto ela ficava com o `↓`
      para si e a seleção parava de andar. Encurtar a área tornou isso comum.
      `can_focus=False` — as setas são do Dashboard, que já traz o card escolhido
      para a tela
- [x] 34 testes novos, incluindo a interface em **95% e 100%** exercitada com um
      rollout escrito pelo teste, e uma fixture que impede a suíte de olhar o
      consumo real de quem a roda
- [x] **A decisão do 2.5 foi tomada**: a linha de statusline entra, estritamente
      opcional, e o README ganhou a ressalva explícita em vez de perder a frase
      ("não há API, hook, credencial nem configuração de agente envolvida" agora
      diz que há **uma**, opcional, e qual)
- [x] **`watchai --install-statusline` / `--uninstall-statusline`**, porque a
      primeira versão servia a esta máquina e não a qualquer instalação. O que o
      README não conseguia resolver, e o comando resolve:
      - **quem já tem statusline não perde a dela.** A original é embrulhada: o
        WatchAI recebe o JSON, guarda o consumo, chama o comando de antes com a
        mesma entrada e imprime a saída **dele**. O aviso do README ("não troque
        por esta sem querer") era um pedido para a pessoa fazer o trabalho que o
        programa tem de fazer
      - **escreve um comando que o agente consegue chamar**, que não é o mesmo
        que um comando que funciona no seu terminal: o Claude Code executa a
        statusline com o PATH **dele**. Nome puro só onde o executável está num
        `bin` global (pipx, snap, pacote); num venv ou clone, caminho absoluto.
        Descoberto instalando o wheel num venv de estranho: o nome puro dava
        `sh: watchai: not found`, statusline vazia e nenhum erro na tela
      - **escreve no arquivo que o agente aplica**: `settings.local.json` tem
        precedência, e se os dois definem `statusLine` o comando avisa em vez de
        adivinhar. Instalar no arquivo errado deixaria a barra invisível sem erro
        nenhum na tela
      - idempotente, com cópia em `settings.json.watchai.bak`, escrita atômica, e
        sem deixar resíduo nosso ao desinstalar (o `refreshInterval` só entra
        quando o slot estava vazio)
      - embrulhada que trava ou falha não pendura o prompt: 5 s de espera e a
        nossa linha assume
- [x] **Apurado no caminho: plugin do Claude Code não pode trazer `statusLine`.**
      O inventário de componentes de um plugin é Skills, Agents, Hooks, MCP e LSP
      (`claude plugin details`). Então `settings.json` é o único caminho, e não há
      distribuição mais elegante esperando ser descoberta

Fora do escopo do item, e continua valendo: não derivar percentual somando
tokens, não rodar `claude -p` para perguntar, não raspar a TUI, não ler
credencial.

---

## O que ainda falta

Em ordem de prioridade. Cada item diz **de quem é a vez** — o que depende de
você e o que é código.

---

### 1. Publicar no PyPI — **prioridade 1**, e a vez é sua

`pipx install watchai` é a distribuição natural de uma TUI em Python: três
sistemas, zero revisão, zero sandbox. E a extensão do VS Code (item 4) precisa
de um comando que ela possa mandar o usuário instalar.

**Do lado do código, está pronto** (feito em 2026-09-28):

- [x] `twine check` passa no sdist e no wheel
- [x] o `app.tcss` está dentro do wheel — sem ele a tela não existe
- [x] o wheel instalado num **venv limpo** sobe o app, carrega o CSS e detecta
      sessão (não é o `pip install -e .` da máquina de desenvolvimento)
- [x] as 8 referências relativas do README viraram absolutas: o PyPI renderiza o
      `long_description` **fora** do repositório, então caminho relativo vira
      404 na página do pacote
- [x] licença migrada para expressão SPDX (PEP 639); os dois avisos de
      depreciação do setuptools tinham data marcada — 2027-02-18

**A sua parte, três passos:**

1. [ ] **Criar o projeto no PyPI.** Não dá para pré-registrar nome vazio: cria-se
       o *pending publisher* direto em
       <https://pypi.org/manage/account/publishing/> com
       PyPI Project Name `watchai` · Owner `LeandroDukievicz` ·
       Repository `WatchAI` · Workflow `publish.yml` · Environment `pypi`.
       O nome está **livre** (conferido em 2026-09-28).
2. [ ] **Criar o environment `pypi`** em *Settings → Environments*. Sem ele o job
       falha ao pedir o token OIDC.
3. [ ] **Ligar `PYPI_READY=true`** em *Settings → Secrets and variables →
       Actions → Variables*.

Depois disso, publicar é criar a release `v1.2.0` no GitHub — o `publish.yml`
dispara sozinho e sobe por *trusted publishing*, sem token guardado.

⚠️ **Versão no PyPI é irreversível**: `1.2.0` não pode ser reenviada, nem
apagando. Se quiser ensaiar, o mesmo *trusted publisher* aponta para o TestPyPI.

Enquanto isso, o caminho é
`pipx install git+https://github.com/LeandroDukievicz/WatchAI.git`.

Em aberto (decisão de conteúdo): o README tem 46 KB e vira a página inteira do
pacote. Funciona, mas é longo para vitrine — dá para ter um `README-pypi.md`
curto e deixar o longo no GitHub.

---

### 2. Verificar macOS e Windows — a maior dívida, e dá para atacar de Linux

O CI roda a suíte nos três sistemas, mas **ninguém nunca abriu o app** num Mac
ou num Windows. Suíte verde não diz nada sobre janela levantando nem sobre
notificação aparecendo. Os riscos concretos, por ordem de probabilidade:

- **Windows não tem tty nenhuma.** A identidade do terminal depende inteiramente
  de achar o shell ancestral — e o descarte de daemon do M13 depende dos mesmos
  dois sinais. Testado com tabela de processos injetada, nunca contra a tabela
  real do Windows.
- **O toast do Windows falha em silêncio.** Se o AUMID não estiver registrado, o
  toast é criado, não dá erro e não aparece — está documentado em `notify.py`.
- **macOS**: o `⇧A` usa `AXRaise`/`AXMinimized` via System Events, que exige
  permissão de acessibilidade concedida à mão.

**Como testar tendo só Linux.** Em três faixas, da mais barata para a mais cara:

- [ ] **(a) Fazer o CI provar muito mais do que prova hoje — é onde está o maior
      retorno, e é só código.** Hoje **nenhum teste toca a tabela de processos
      real**: todos injetam uma fonte falsa. Dá para mudar isso e roda igual nos
      três sistemas: suba um processo cuja linha de comando o `identify` casa —
      `sys.executable /tmp/…/claude`, porque `python` é runtime e o
      `_basename(argv[1])` vira `claude` — e rode uma `PsutilSource().snapshot()`
      de verdade, conferindo que ele aparece com a identidade de terminal certa.
      Isso testa o caminho do shell ancestral **no Windows real**, que é o risco
      número um. Junto: invocar o script do toast no runner e conferir que o tipo
      WinRT carrega (é exatamente a falha silenciosa), e anexar um
      `app.export_screenshot()` por sistema como artefato do CI, para dar para
      olhar a renderização de cada um.
- [ ] **(b) VM de Windows local, grátis e legal.** ISO de avaliação de 90 dias da
      Microsoft em QEMU/KVM (ou no LXD, que você já tem). Cobre o que o CI nunca
      vai cobrir: janela minimizada voltando, `AppActivate` indo para a janela
      certa com várias abertas, e o toast aparecendo de fato.
- [ ] **(c) macOS não tem caminho bom a partir do Linux.** VM de macOS em
      hardware não-Apple esbarra na licença da Apple — não recomendo. Sobram
      três opções honestas: pedir emprestado um Mac por uma hora, alugar um Mac
      na nuvem (as instâncias `mac` da AWS têm mínimo de 24 h, então é uma
      despesa real), ou **recrutar um testador**: abrir uma issue "Verificação em
      macOS" com um roteiro de cinco passos e linkar do README. É como projeto
      pequeno resolve isso, e as três perguntas que importam cabem num
      checklist: janela minimizada volta? Com várias janelas do mesmo terminal,
      vai para a certa? Quando falha, o recado diz `refused` em vez de
      `window raised`?

**Até (b) e (c) acontecerem, o README e a loja devem dizer "Linux".** Anunciar
suporte a três sistemas com dois nunca abertos é prometer o que não se verificou.

---

### 3. Snap Store — a análise de 2026-09-28 mudou a recomendação

**O que já está pronto:** conta na loja ativa (`ldukie`, com `package_register`),
nome `watchai` livre, e o CI constrói o snap, instala e roda o binário.

**Três achados que mudam o plano:**

1. **A justificativa escrita para `classic` está meio errada.** O comentário do
   `snapcraft.yaml` diz que a notificação não atravessa o sandbox. Atravessa:
   `libnotify-bin` em `stage-packages` mais a interface `desktop`
   (auto-conectada) e o `notify-send` funciona.
2. **Mas havia um bloqueio maior, e real.** Nos perfis AppArmor instalados nesta
   máquina, o que a `system-observe` libera de `/proc` de outros processos é
   `cmdline, comm, exe, stat, status, statm, io, cgroup, auxv, fdinfo/*,
   oom_score, schedstat, smaps_rollup, autogroup, attr/current`. **`cwd` não está
   na lista.** Num snap strict o `proc.cwd()` devolvia `None` para tudo, e o
   WatchAI perdia o projeto e todo o estado de diário. **Resolvido no M13** — é
   o que torna o strict viável.
3. **`classic` provavelmente seria recusado.** A lista oficial de categorias
   aceitas é compiladores, IDEs, linguagens, emuladores de terminal /
   multiplexadores / shells, agentes de nuvem e ferramentas de workspace —
   WatchAI não é nenhum. E dois itens da lista de **negados** batem direto: "pede
   acesso a dotfiles sem explorar alternativas" (`~/.claude`, `~/.codex`) e
   "extensões do GNOME shell" (o `⇧A` fala com a Window Calls). A revisão começa
   em ~2 semanas e escala para revisor sênior + arquiteto fora das categorias.

**O caminho recomendado, agora que o M13 existe:**

- [ ] Migrar o `snap/snapcraft.yaml` para **`confinement: strict`**, com
      `system-observe` (conexão manual), `audio-playback`, `desktop` +
      `libnotify-bin`, e `personal-files` de **leitura** em
      `$HOME/.claude/projects` e `$HOME/.codex/sessions`. Só o `personal-files`
      pede revisão, e é do tipo rotineiro.
- [ ] **Helper de "home real".** Num snap strict o `HOME` aponta para a pasta
      privada do pacote. São quatro chamadas a corrigir via `SNAP_REAL_HOME`:
      `transcript.py:726`, `config.py:39`, `live.py:57` e `live.py:72` — as duas
      últimas só encurtam caminho para `~`, mas mostrariam caminho errado.
      (No `classic` o `HOME` é o real: conferido com
      `snap run --shell snapcraft`. Isto é dívida só do strict.)
- [ ] Aceitar a perda do `⇧A` sob strict: ele degrada para o sino na tty e a
      marcação de título, que já são o caminho de fallback. É o único preço.
- [ ] Registrar o nome e publicar em `edge` primeiro.
- [ ] Corrigir `docs/publicacao-snap.html`, que descreve um `snapcraft.yaml`
      strict que não é mais o do repositório e ainda manda editar o
      `Transcripts.__init__` à mão.

**Nota de escopo que ajuda a decidir:** a Snap Store só distribui Linux — que é
justamente a parte verificada. O risco de plataforma ali é baixo; o bloqueio era
burocrático, e o M13 o derrubou.

---

### 4. Extensão do VS Code

Viável, e tem uma peça que **só ela** consegue entregar: dentro do VS Code o
agente roda no terminal integrado, e a extensão tem `terminal.show()`. Casando
`Terminal.processId` com o `window_pid`/tty da sessão, o "me leve até lá" vira
exato nos três sistemas, sem D-Bus — resolvendo justamente o caso em que o `⇧A`
hoje não consegue prometer nada (Wayland sem a extensão Window Calls).

Três desenhos foram considerados; o escolhido é o terceiro:

| | o que é | esforço | veredito |
|---|---|---|---|
| A | comando que abre o `watchai` num terminal integrado | ~1 dia | ganho quase nulo: já dá para digitar `watchai` |
| B | reimplementar a detecção em TypeScript | semanas | duplica ~1.500 linhas de lógica |
| **C** | **núcleo Python emite JSON, extensão desenha** | ~1 semana | **o certo** |

- [ ] **`watchai --json`** (lado Python, e útil sozinho): imprime o snapshot de
      sessões como NDJSON. Reaproveita o `LiveProvider` inteiro — hoje não existe
      nenhuma saída que não seja a TUI. ~100–150 linhas. Serve também para
      scripts, barra do waybar/i3 e teste de integração.
- [ ] **Extensão** (TypeScript): `TreeView` na barra lateral com um item por
      sessão e o semáforo como ícone, `StatusBarItem` com o resumo (`◐2 ●1`),
      clique revelando o terminal, notificação nativa em READY/INPUT/ERROR.
- [ ] Armadilhas de publicação já levantadas: o nome `watchai.watchai` está livre
      no Marketplace; **o ícone do `package.json` não pode ser SVG** (o
      `docs/brand/watchai-icon.svg` precisa virar PNG 128×128, e imagens do
      README precisam ser URLs https não-SVG); e **a partir de 1º/12/2026 os PATs
      globais do Azure DevOps são aposentados** — a publicação automatizada tem
      que nascer em Microsoft Entra ID.
- [ ] Atrito honesto: a extensão é Node e o núcleo é Python. Ela procura
      `watchai` no PATH e, se não achar, oferece `pipx install watchai` — **o que
      só funciona depois do item 1**.

---

### 5. Casar processo e diário do Claude Code pelo PID

`~/.claude/sessions/<pid>.json`, indexado por **PID** — achado durante o
levantamento do M14 e confirmado nesta máquina em 2026-09-29:

```json
{ "pid": 113747, "sessionId": "71d61609-…", "cwd": "/home/leandro-dukievicz",
  "kind": "interactive", "entrypoint": "cli", "status": "idle",
  "name": "leandro-dukievicz-2b", "version": "2.1.278",
  "startedAt": 1790713132469, "updatedAt": 1790713132599,
  "statusUpdatedAt": 1790713132599 }
```

Isso dá, para o Claude Code, o casamento **exato** processo→diário — no lugar da
heurística de relógio do M13 —, mais o `cwd` sem depender do `proc.cwd()`, mais
um `status` de primeira mão e um `kind: "interactive"` que separa sessão de
não-sessão. O arquivo é `-rw-rw-r--`; o `.key` ao lado dele é `600` e não
interessa.

⚠️ Vale medir antes de trocar: a heurística de relógio do M13 está funcionando, e
a pasta só existe para o Claude Code. O ganho é precisão num caso conhecido (duas
sessões na mesma pasta), não um bug aberto.

- [ ] `ClaudeCode.arquivos()` passa a preferir o `sessionId` do PID quando houver
- [ ] `status` e `kind` do arquivo entram como sinal na decisão de estado
- [ ] a heurística de relógio continua, para quem não tem esse arquivo

---

### 6. Miudezas

- [ ] **O `--help` da linha de comando ainda está em português**, ao contrário da
      tela, que é toda em inglês. Não é bug, é decisão de produto — mas se o app
      vai para loja e Marketplace, vale alinhar (`__main__.py`).

---

## Fora de escopo (decidido)

- **Validar o leitor do OpenCode e escrever um para o Antigravity.** Tirados da
  lista em 2026-09-23. A ressalva do OpenCode continua onde importa — no
  docstring do leitor e no README —, então quem usar aquele CLI e vir estado
  errado sabe onde olhar; e o Antigravity segue na camada de processos, com
  projeto, tempo e CPU, mas sem estado de diário.

- **Integração por API, hook ou plugin dos agentes.** A regra do produto é não
  conectar nada: só processo e arquivo local.
- **Sessões de outro usuário ou dentro de container.** A varredura vê só os
  processos do usuário que rodou o WatchAI.
- **Ler a tela do terminal** (PTY, scrollback). Resolveria o INPUT com certeza,
  mas é exatamente o tipo de intrusão que o projeto evita.

---

## Limites conhecidos (não são bugs)

- Para agentes **sem diário**, o `for MM:SS` conta da descoberta, não do
  acontecimento — o disco não guarda essa hora.
- Dois agentes **do mesmo tipo no mesmo diretório** compartilham o diário mais
  recente; o segundo cai na camada de processos.
- INPUT é inferido: ferramenta pendente + processo parado há 8 s. Uma ferramenta
  lenta que não gasta CPU aparece como INPUT.
- `cwd` pode ser negado no macOS para processos que não são seus. Deixou de
  ser limitante: sem pasta, o diário é achado pelo relógio e o projeto sai de
  dentro dele. Quem fica sem diário é só quem não tem diário nenhum.
- **Duas abas no mesmo projeto têm o mesmo título**, já que o título é o
  caminho. Quem as distingue é o terminal no canto do card (`pts/4` contra
  `pts/7`) — foi o que deu função a ele.
- O **Antigravity** aparece e mostra projeto, tempo e CPU, mas não estado de
  diário: ele não grava um.
- O aviso não dispara pelas sessões que já estavam abertas quando o WatchAI
  subiu: só pelo que muda depois.
