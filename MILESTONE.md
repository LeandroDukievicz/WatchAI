# Milestones

Onde o WatchAI está e o que falta. Cada item diz **o que é**, **por que importa**
e **onde mexer** — para dar para pegar um e fazer sem redescobrir o contexto.

Atualizado em 2026-09-22.

---

## ✅ Feito

### M0 — camada visual (1.0.0)

- [x] Dashboard: header com resumo global, painel SESSIONS, EVENT STREAM, keybar
- [x] Semáforo de 3 lâmpadas por card (a identidade do produto)
- [x] Visões CARDS e LIST, modal de detalhes, ajuda
- [x] Layout responsivo de 20×10 a 300×80, sem vão morto
- [x] Bip pelo servidor de som ao entrar em READY (toca com a aba em segundo plano)
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

---

## M3 — o aviso chega em você

O produto responde "quem terminou e quem precisa de você". Hoje ele **mostra**,
mas só **avisa** em READY — e o INPUT, que é literalmente "parou esperando
você", passa em silêncio.

- [ ] **Bip em INPUT e ERROR**, não só em READY
      `app.py:ALERT_STATUSES` já é um `frozenset` — a mudança é de uma linha,
      mas precisa de som diferente por estado (senão não dá para distinguir sem
      olhar) e de teste para não bipar em rajada.

- [ ] **Notificação do sistema** para quando o WatchAI está numa aba que você não vê
      `notify-send` (Linux) · `osascript -e 'display notification'` (macOS) ·
      toast por PowerShell (Windows). Mesmo desenho do `sound.py`: descobrir o
      que existe na máquina, degradar em silêncio, nunca travar a UI.
      Ligar/desligar junto com o bip (`B`) ou em tecla própria.

- [ ] **Tempo real do estado** — hoje `for MM:SS` conta desde que o WatchAI
      **viu**, não desde que aconteceu; abrir o app zera todos os contadores.
      As entradas do diário têm `timestamp`: dá para recuperar a hora verdadeira
      da última mudança. Mexe em `providers/transcript.py` (devolver o instante
      junto do estado) e em `live.py` (usar como `status_since`).
      Limite honesto: só para agentes com diário; os outros continuam contando
      da descoberta.

- [ ] **ERROR de verdade no Claude Code** — hoje só o Codex sinaliza erro.
      Verificado nos transcripts desta máquina: entradas com
      `isApiErrorMessage: true` trazem exatamente os casos que interessam —
      `"You've hit your session limit · resets 10:30pm"` e
      `"API Error: 401 OAuth access token has expired"`. É o estado que mais
      merece aviso: a sessão parou e não volta sozinha.

- [ ] **Ordenar os cards por atenção** (opcional, decidir antes de fazer)
      Hoje a ordem é a de descoberta. Quem pede você primeiro subir para o topo
      ajuda com muitas sessões — mas card que dança de lugar sozinho atrapalha a
      memória visual. Talvez só como tecla de ordenação, não como padrão.

---

## M4 — mais agentes com estado fino

Gemini, OpenCode e Aider hoje vivem só da camada de processos: aparecem, mostram
projeto e tempo, e alternam entre WORKING e READY. Falta o "o que está fazendo".

- [ ] **OpenCode** — `opencode 1.17.9` está instalado aqui, mas
      `~/.local/share/opencode/storage/` só tem `migration/` e `session_diff/`:
      esta instalação não gravou sessão nenhuma desde agosto. **Bloqueado até
      abrir uma sessão real** e mapear o que a versão atual escreve (pode ser o
      `opencode.db`, SQLite — legível com a stdlib).

- [ ] **Aider** — grava `.aider.chat.history.md` na pasta do projeto. Não está
      instalado aqui, então o formato não foi verificado. **Precisa de uma
      sessão real** antes de escrever o leitor.

- [x] ~~**Gemini CLI**~~ — **não dá com o que ele grava hoje.** O
      `~/.gemini/tmp/<projeto>/logs.json` registra **só as mensagens do
      usuário** (todas com `type: "user"`), sem resposta, sem ferramenta e sem
      fim de turno. Dá para saber quando você falou com ele pela última vez, não
      o que ele está fazendo. Fica na camada de processos até o formato mudar.

Cada leitor novo é uma classe em `providers/transcript.py` com dois métodos
(`arquivo(cwd)` e `ler(caminho)`) e uma linha no `Transcripts.__init__` — o
resto do sistema não muda.

---

## M5 — permanência e distribuição

- [ ] **Histórico do EVENT STREAM entre execuções** — hoje ele começa vazio a
      cada abertura, então o que aconteceu enquanto o app estava fechado se
      perde. Guardar os últimos ~200 eventos junto da config
      (`config.py` já resolve caminho e escrita tolerante a falha).

- [ ] **Instalador no repositório** — o comando `watchai` e o atalho de área de
      trabalho existem **só nesta máquina** (`~/.local/bin/watchai`,
      `~/.local/share/applications/watchai.desktop`, ícone SVG em
      `~/.local/share/icons/hicolor/scalable/apps/`). Nada disso está
      versionado: quem clonar o repo não tem. Falta um `scripts/install-linux.sh`
      (e o `.desktop` de exemplo) no projeto.

- [ ] **Publicar** — `pipx install watchai` / PyPI, para não depender de clonar
      o repositório e criar venv na mão.

- [ ] **Validar Windows e macOS de verdade** — o código trata os dois
      (identidade de terminal pelo shell quando não há tty, agente reconhecido
      pelo caminho do pacote) e o CI roda a suíte nos três, mas **ninguém abriu
      o app num Windows ou num Mac ainda**. Até lá, é código testado, não
      software verificado.

- [ ] **Release 1.1.0** — o CHANGELOG está em `[Não lançado]` com temas +
      detecção real. Falta decidir a versão, marcar a tag e publicar.

- [ ] **Atualizar a landing page** (`docs/index.html`) — ela ainda descreve o
      WatchAI como "protótipo visual" com dados mockados, o que deixou de ser
      verdade.

---

## Fora de escopo (decidido)

- **Integração por API, hook ou plugin dos agentes.** A regra do produto é não
  conectar nada: só processo e arquivo local.
- **Sessões de outro usuário ou dentro de container.** A varredura vê só os
  processos do usuário que rodou o WatchAI.
- **Ler a tela do terminal** (PTY, scrollback). Resolveria o INPUT com certeza,
  mas é exatamente o tipo de intrusão que o projeto evita.

---

## Limites conhecidos (não são bugs)

- `for MM:SS` conta da descoberta, não do acontecimento — item de M3.
- Dois agentes **do mesmo tipo no mesmo diretório** compartilham o diário mais
  recente; o segundo cai na camada de processos.
- INPUT é inferido: ferramenta pendente + processo parado há 8 s. Uma ferramenta
  lenta que não gasta CPU aparece como INPUT.
- `cwd` pode ser negado no macOS para processos que não são seus — o card cai
  para o rótulo do terminal.
