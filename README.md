<div align="center">

<img src="docs/brand/watchai.png" alt="WatchAI" width="620">

**Monitor de sessões de IA no terminal.**
Claude Code, Codex, Gemini, OpenCode, Aider, Copilot — todas numa tela só.

[![tests](https://github.com/LeandroDukievicz/WatchAI/actions/workflows/tests.yml/badge.svg)](https://github.com/LeandroDukievicz/WatchAI/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.10%20%E2%80%93%203.14-blue)
![license](https://img.shields.io/badge/license-MIT-green)

</div>

![WatchAI em 150×36](docs/screenshot.png)

---

> ### ⚠️ Versão 1.0.0 — camada visual
>
> **Todos os dados são mockados.** Não existe descoberta de processos, PID, PTY,
> hooks, logs, APIs nem integração com nenhuma IA. Os estados mudam sozinhos a
> cada 5–12 s apenas para avaliar a interface em movimento. A arquitetura já está
> pronta para receber dados reais — ver [Roadmap](#roadmap).

## O problema

Você dispara uma tarefa no Claude Code, vai para outra janela enquanto ele
trabalha, e esquece. Dez minutos depois descobre que ele terminou em dois — ou
que travou esperando você confirmar um comando. Com três ou quatro sessões de IA
abertas ao mesmo tempo, o custo vira atenção fragmentada.

O WatchAI coloca todas numa tela só e responde de longe, sem leitura:
**quem está trabalhando, quem terminou e quem precisa de você.**

## Instalação

Requisitos: **Python 3.10+** e um terminal com Unicode.

```bash
git clone git@github.com:LeandroDukievicz/WatchAI.git
cd WatchAI
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Uso

```bash
python main.py       # ou:  watchai  ·  python -m watchai
```

Truecolor (`COLORTERM=truecolor`) dá as cores exatas; sem ele o Textual aproxima
para 256/16 cores. Nada depende de ligatures — só símbolos Unicode simples
(`● ○ ◐ ◓ ◑ ◒ ◆ ◇ ▲ ▸ ▶ ─ │ ╭ ╮ ╰ ╯`). Testado com JetBrains Mono, Fira Code,
Cascadia, Hack, Meslo e Ubuntu Mono.

---

# Funcionalidades

A tela tem quatro regiões fixas:

```
 ╭─ ◆ WatchAI  SESSION MONITOR ─────────────────────────────────╮
 │ ACTIVE 05 │ ◐ WORKING 01  ● READY 01  …         21:25:46     │   ① cabeçalho
 ╰──────────────────────────────────────────────────────────────╯
  ▸ SESSIONS 06 ─────────────────────────── CARDS │ LIST            ② título do painel
 ╭─ ▶ CLAUDE CODE ──────────────╮  ╭─ CODEX ───────────────────╮
 │  ◐ WORKING        for 04:12  │  │  ● READY       for 01:42  │    ③ painel SESSIONS
 ╰──────────────────────── #03 ─╯  ╰───────────────────── #01 ─╯
 ╭─ EVENT STREAM ───────────────────────────────────────────────╮
 │ 21:25:19 ◆ OPENCODE INPUT    waiting for confirmation        │   ④ event stream
 ╰──────────────────────────────────────────────────────────────╯
  ↑↓ NAV │ ENTER OPEN │ TAB PANEL │ T THEMES │ V VIEW │ R REFRESH …    ⑤ keybar
```

## ① Cabeçalho — resumo global

```
╭─ ◆ WatchAI  SESSION MONITOR ──────────────────────────────────────────────────╮
│ ACTIVE 05 │ ◐ WORKING 01  ● READY 01  ◆ INPUT 01  ◇ WAITING 01  ▲ ERROR 01  ○ OFFLINE 01   21:25:46 │
╰───────────────────────────────────────────────────────────────────────────────╯
```

- **ACTIVE** — quantas sessões não estão OFFLINE.
- **Um chip por estado**, em ordem fixa (WORKING, READY, INPUT, WAITING, ERROR,
  OFFLINE), para a posição não dançar quando os números mudam. Estado com zero
  fica apagado; com contagem, acende na cor do estado. Os que pedem você
  (READY, INPUT, ERROR) vêm em negrito.
- **STARTING só aparece quando existe** — é transitório demais para ocupar espaço fixo.
- **Relógio** à direita, atualizado a cada 0,5 s.
- O cabeçalho se adapta à largura: perde o subtítulo `SESSION MONITOR` abaixo de
  48 colunas, depois troca `◐ WORKING 01` por `◐ 1`, e em último caso abandona o
  relógio para manter os chips.

## ② Título do painel

```
 ▸ SESSIONS 06 ─────────────────────────────────────────── CARDS │ LIST
```

Mostra quantas sessões existem, qual visão está ativa (`CARDS` ou `LIST`, em
cyan) e — pelo `▸` e pela régua acesa — se o painel de sessões está em foco ou
se o foco está no EVENT STREAM (`TAB`).

## ③ Painel SESSIONS

### Visão CARDS (padrão)

```
╭─ ▶ CLAUDE CODE ────────────────────────╮
│  ◐ WORKING           for 04:12  ╭───╮  │
│                                 │ ● │  │
│  project  telegram-downloader   │ ● │  │
│  activity generating telegram…  │ ● │  │
│  elapsed  00:12:44              ╰───╯  │
╰────────────────────────────────── #03 ─╯
```

| Elemento | O que é |
|---|---|
| Título na borda | Nome da IA. Ganha `▶` e vira cyan quando é o card selecionado |
| `#03` na borda | Número da sessão |
| `◐ WORKING` | Estado: símbolo animado + label, sempre na cor do estado |
| `for 04:12` | Há quanto tempo está **neste** estado (não é o tempo de sessão) |
| `project` | Projeto em que a sessão trabalha |
| `activity` | O que está fazendo agora |
| `elapsed` | Tempo total de sessão (`HH:MM:SS`) |
| Semáforo | As 3 lâmpadas — ver [seção própria](#o-semáforo) |

- **A moldura carrega o estado**: verde (READY), magenta (INPUT) e vermelho
  (ERROR) acendem forte e ganham uma tinta de fundo; WORKING e WAITING ficam em
  tons apagados (é o estado normal, não deve chamar atenção); OFFLINE quase some.
- **Selecionado** ganha fundo levemente mais claro e título cyan — mas a moldura
  **mantém a cor do estado**: um READY selecionado continua verde.
- **`for MM:SS` fica em negrito depois de 1 minuto** em READY, INPUT e ERROR — é
  o "terminou há dois minutos e você ainda não voltou".
- **Sessão OFFLINE** mostra `—` em project e elapsed.
- **Textos longos truncam com `…`**, nunca quebram linha.
- Se os cards não couberem na altura, o painel rola (`↑ ↓` seguem a seleção).

### Visão LIST (`V`)

```
   AI         STATUS      PROJECT                                     TIME
 ─────────────────────────────────────────────────────────────────────────
 ▶ CLAUDE     ◐ WORKING   telegram-downloader                        04:12
   CODEX      ● READY     dukie-tech                                 01:42
   GEMINI     ◇ WAITING   research-agent                             03:11
   OPENCODE   ◆ INPUT     devleandro                                 00:27
   AIDER      ▲ ERROR     devsaderiva                                02:51
   COPILOT    ○ OFFLINE   —                                              —
```

A mesma informação em uma linha por sessão — é a visão mais densa, para quando
há muitas sessões. `TIME` é o mesmo contador dos cards (tempo no estado atual) e
segue a mesma regra de negrito. A linha inteira recebe a tinta do estado, e a
selecionada ganha `▶` e nome em cyan.

## ④ EVENT STREAM

```
╭─ EVENT STREAM ─────────────────────────────────────────────────────────╮
│ 21:25:19 ◆ OPENCODE INPUT    waiting for confirmation                  │
│ 21:24:26 ◐ OPENCODE WORKING  editing files                             │
│ 21:24:04 ● CODEX    READY    task completed                            │
│ 21:23:16 ◐ CODEX    WORKING  applying patch                            │
│ 21:22:55 ▲ AIDER    ERROR    test suite failed (exit 1)                │
╰────────────────────────────────────────────────────────────────────────╯
```

O histórico de todas as sessões junto, **mais novo em cima** (guarda os últimos
200 eventos). O evento mais recente vem em destaque; os demais, apagados.

- **`TAB` move o foco para cá** — a borda acende em cyan e aparece `↑↓ scroll` no
  rodapé da caixa. Com o foco aqui, `↑ ↓` rolam o histórico em vez de trocar de
  sessão. Ao sair (`TAB` de novo) ele volta ao topo, para nunca ficar preso
  mostrando eventos velhos.
- **Cresce com o terminal**: ocupa toda a altura que sobra depois dos cards —
  quanto mais alto o terminal, mais histórico visível.
- **Encolhe por colunas**: abaixo de 56 colunas esconde a coluna de estado;
  abaixo de 34, também o nome da sessão, preservando hora e mensagem.

## ⑤ Keybar

```
 ↑↓ NAV │ ENTER OPEN │ TAB PANEL │ T THEMES │ V VIEW │ R REFRESH │ B BIP │ ? HELP │ Q QUIT
```

Rodapé de atalhos que se adapta à largura: quando não cabe, descarta os itens
menos importantes primeiro (`B`, depois `R`, `T`, `TAB`…) e, em último caso, mostra só
as teclas sem descrição. O item do bip reflete o estado: `B BIP` ligado,
`B MUDO` (apagado) desligado.

## Detalhes da sessão (`ENTER`)

```
╭─ SESSION DETAILS ──────────────────────────────────────────────────────╮
│  GEMINI                                                                │
│  STATUS     ◇ WAITING                    for 03:11  ·  since 21:22:46  │
│  SESSION    #02                                                        │
│  PID        190114                                                     │
│  PROJECT    research-agent                                             │
│  DIRECTORY  ~/research-agent                                           │
│  STARTED    21:16:37                                                   │
│  ELAPSED    00:09:20                                                   │
│                                                                        │
│  CURRENT ACTIVITY                                                      │
│  waiting for API response                                              │
│                                                                        │
│  EVENTS                                                                │
│  21:22:46 ◇ waiting for API response                                   │
│  21:21:17 ◐ reading repository                                         │
│  21:19:57 ◐ user prompt                                                │
│                                                                        │
│  ESC back   ←→ prev/next session                                       │
╰────────────────────────────────────────────────────────────────────────╯
```

Modal com tudo sobre uma sessão: além do estado (com o horário em que entrou
nele), o PID, o diretório, quando começou e os **últimos 4 eventos só dela**.

- O dashboard continua vivo atrás, escurecido — os semáforos e contadores seguem
  atualizando enquanto o modal está aberto.
- **`← →` trocam de sessão sem fechar**, circulando (depois da última volta para a
  primeira), e a seleção do dashboard acompanha.
- Sessão OFFLINE mostra `—` nos campos que perderam sentido.

## Ajuda (`?`)

Modal com a lista de teclas. Fecha com `ESC` ou `?`.

## O semáforo

Cada card carrega um semáforo de 3 lâmpadas — é a leitura "de longe", antes de
ler qualquer texto. É também a identidade do produto.

```
╭───╮
│ ● │  vermelha · ERROR
│ ● │  amarela  · WORKING, WAITING, STARTING e INPUT (piscando)
│ ● │  verde    · READY
╰───╯
```

Como num semáforo de verdade, as lâmpadas apagadas não somem: ficam num tom bem
escuro da própria cor. OFFLINE apaga as três e escurece a carcaça. INPUT é o
único que pisca (1 s aceso, 1 s apagado) — é o estado que depende de você.
Abaixo de 60 colunas o semáforo sai (não cabe) e quem dá o estado é a barra
lateral colorida.

## O bip de READY

Quando uma sessão **entra** em READY, o app toca um bip curto — a ideia é você
saber sem estar olhando.

O som sai pelo **servidor de som** (PipeWire/PulseAudio), não pelo bell do
terminal (`\a`). Essa escolha é o ponto todo: bell vira flash visual em vários
emuladores, costuma vir desligado e não ajuda com a aba em segundo plano. Um
stream de áudio normal toca independente de foco.

- `B` liga/desliga; o rodapé mostra `B BIP` ou `B MUDO`. Religar confirma com um bip.
- Uma rajada de READY vira um bip só (janela de 1 s), sem enfileirar áudio.
- Não bipa na abertura por uma sessão que já nasceu READY, nem em outros estados.
- Ordem de preferência: `pw-play` → `paplay` → `ffplay`, tocando um bip do tema do
  sistema. Sem nenhum deles, tenta `canberra-gtk-play`; em último caso, o bell do terminal.
- Para avisar também em INPUT ou ERROR, inclua os estados em `ALERT_STATUSES`
  ([`src/watchai/app.py`](src/watchai/app.py)).

## Temas (`T`)

Oito paletas, trocáveis com o app rodando:

```
╭─ THEMES ─────────────────────────────────╮
│                                          │
│   ▶ WatchAI     ◐ ● ◆ ◇ ▲ ○ ◌  •         │
│     Light       ◐ ● ◆ ◇ ▲ ○ ◌            │
│     Dark        ◐ ● ◆ ◇ ▲ ○ ◌            │
│     Night Owl   ◐ ● ◆ ◇ ▲ ○ ◌            │
│     Vampire     ◐ ● ◆ ◇ ▲ ○ ◌            │
│     Cyberpunk   ◐ ● ◆ ◇ ▲ ○ ◌            │
│     Steampunk   ◐ ● ◆ ◇ ▲ ○ ◌            │
│     Grey        ◐ ● ◆ ◇ ▲ ○ ◌            │
│                                          │
│   ↑↓ preview   ENTER apply   ESC cancel  │
│                                          │
╰──────────────────────────────────────────╯
```

| Tema | O que é |
|---|---|
| **WatchAI** | o original: fundo quase preto e neon cyan/magenta (padrão) |
| **Light** | fundo claro — as tintas de estado viram pastel em vez de sumir |
| **Dark** | escuro neutro, sem neon |
| **Night Owl** | azul-petróleo com verdes suaves |
| **Vampire** | Dracula (o roxo `#BD93F9` entra como acento secundário) |
| **Cyberpunk** | preto arroxeado, cyan e magenta saturados |
| **Steampunk** | sépia e latão, com verdete no lugar do cyan |
| **Grey** | sem matiz nenhum: os estados se separam só por brilho |

![Light, Vampire, Cyberpunk e Steampunk](docs/themes.png)

- **Mover a seleção aplica o tema na hora** — o dashboard inteiro atrás do modal
  troca de cor, então dá para comparar antes de decidir. `ENTER` confirma,
  `ESC` desfaz e volta para o tema em que você estava.
- Cada linha mostra os símbolos dos estados **nas cores daquela paleta**; o `•`
  marca o tema em que você estava ao abrir.
- A escolha **fica salva** em `$XDG_CONFIG_HOME/watchai/config.json` (ou
  `~/.config/watchai/config.json`) e volta na próxima execução. Arquivo
  corrompido, disco cheio ou tema desconhecido caem no padrão, sem derrubar a TUI.
- O tema **não muda símbolo nem label** — só cor. O **Grey** é a prova: mesmo sem
  matiz nenhum, `◐ WORKING` e `▲ ERROR` continuam distinguíveis, que é a garantia
  de quem não enxerga cor.

## Linguagem visual dos estados

Cor **e** símbolo **e** label — dá para ler sem depender só de cor.

| Estado | Símbolo | Cor | Semáforo | Significado | Card |
|---|---|---|---|---|---|
| READY | `●` (pulso lento) | verde | **verde** | terminou, pronta p/ nova instrução | borda verde + tinta + label/tempo em negrito |
| WORKING | `◐◓◑◒` (giro lento) | cyan | **amarela** | executando | borda cyan apagada, sem negrito (calmo) |
| WAITING | `◇` | amarelo | **amarela** | esperando processo externo | borda âmbar apagada |
| INPUT | `◆` (pulso lento) | magenta | **amarela piscando** | esperando ação do usuário | borda magenta + tinta |
| ERROR | `▲` (estático) | vermelho | **vermelha** | problema detectado | borda vermelha + tinta |
| OFFLINE | `○` (apagado) | cinza escuro | todas apagadas | sessão encerrada | quase some no fundo |
| STARTING | `◌ ○` | cyan secundário | **amarela** | acabou de iniciar | borda apagada |

Todas as animações são discretas e guiadas pelo mesmo relógio de 0,5 s: o giro do
WORKING, o pulso lento de READY e INPUT (~4,5 s por ciclo) e o `◌ ○` alternando do
STARTING. ERROR e OFFLINE são estáticos de propósito.

As cores da tabela são as do tema **WatchAI**; os outros temas remapeiam a cor de
cada estado, nunca o símbolo nem o label.

Regra de ouro da paleta: neon só em status, título, seleção e teclas. O resto é
branco suave e cinza.

## Navegação

| Tecla | Ação |
|---|---|
| `↑ ↓` (`k j`) | seleciona sessão — nas colunas do grid, move uma linha inteira |
| `← →` (`h l`) | navega entre cards da mesma linha (sem efeito com 1 coluna) |
| `ENTER` | abre os detalhes da sessão selecionada |
| `ESC` | volta / fecha o modal |
| `TAB` | alterna o painel **SESSIONS ⇄ EVENTS** |
| `T` | abre o seletor de temas (preview ao vivo; `ENTER` salva, `ESC` desfaz) |
| `V` | alterna **CARDS ⇄ LIST** |
| `R` | refresh — no protótipo, avança a simulação na hora |
| `B` | liga/desliga o bip de READY |
| `?` | ajuda |
| `Q` / `Ctrl+C` | sai |

Detalhes que o teclado respeita:

- Com o foco no **EVENT STREAM**, `↑ ↓` rolam o histórico e `ENTER` não abre nada —
  o painel de sessões volta com `TAB`.
- Descendo na **última linha incompleta** do grid, a seleção cai no último card em
  vez de não fazer nada.
- A seleção é sempre trazida para a área visível quando o painel rola.
- Dentro dos detalhes, `← →` trocam de sessão em vez de navegar no grid.

**Mouse:** clique seleciona (em card ou em linha da LIST), duplo clique abre os
detalhes.

## Responsividade

Por largura:

| Largura | Layout |
|---|---|
| ≥ 130 | 3 cards por linha |
| 90–129 | 2 cards por linha |
| 60–89 | 1 card por linha |
| < 60 | compacto: sem caixa, barra lateral na cor do estado, 4 linhas por sessão (sem semáforo) |

Por altura: a área de sessões encolhe até o conteúdo e o EVENT STREAM ocupa tudo
que sobra — quanto mais alto o terminal, mais histórico, e nunca um vão morto no
meio. Se as sessões não couberem, a área rola em vez de empurrar o stream para
fora: o stream nunca fica com menos que suas 6 linhas de eventos, e header e
keybar ficam sempre visíveis. Testado de 20×10 a 300×80.

## A simulação (só no protótipo)

Para avaliar a interface em movimento, um simulador troca o estado de uma sessão
aleatória a cada **5–12 s**, seguindo transições plausíveis (de WORKING sai-se
mais para READY do que para ERROR; de OFFLINE só se volta por STARTING, que se
resolve em ~4 s). A atividade textual acompanha o estado novo. `R` força o
próximo passo na hora.

---

## Arquitetura

```
WatchAI/
├── main.py                      # entrada: python main.py
├── pyproject.toml               # pacote, deps e config do pytest
├── src/watchai/
│   ├── app.py                   # App: tema, tick (0,5 s), bindings, bip de READY
│   ├── theme.py                 # as 8 paletas + paleta ativa ($aw-* para o TCSS)
│   ├── layout.py                # breakpoints (LARGE/MEDIUM/SMALL/TINY) + teto da área
│   ├── format.py                # ellipsize, HH:MM:SS, mm:ss
│   ├── sound.py                 # bip (descobre o player do sistema)
│   ├── config.py                # preferências salvas (~/.config/watchai/config.json)
│   ├── models/                  # Status (cor/símbolo/label), Session, SessionStore
│   ├── mock/sessions.py         # 6 sessões + MockSimulator
│   ├── widgets/
│   │   ├── status_light.py      # StatusLight + render_status()  ← fonte única dos estados
│   │   ├── traffic_light.py     # TrafficLight (semáforo de 3 lâmpadas)
│   │   ├── session_card.py      # SessionCard (normal / compacto)
│   │   ├── session_row.py       # linha da visão LIST
│   │   ├── event_stream.py      # EVENT STREAM
│   │   ├── header.py            # cabeçalho + resumo global
│   │   ├── keybar.py            # rodapé de atalhos (responsivo)
│   │   └── panel_title.py       # "▸ SESSIONS 06 ─── CARDS │ LIST"
│   ├── screens/                 # dashboard.py · details.py · help.py · themes.py
│   └── styles/app.tcss          # todo o CSS
├── tests/                       # suíte headless (conftest silencia o áudio)
└── docs/                        # marca e screenshot
```

Três regras que o código segue:

1. **O estado mora no enum.** `Status` carrega label, cor, símbolo e prioridade de
   atenção. Nenhum widget hardcoda cor ou símbolo de estado — todos consultam o enum,
   e todo desenho de estado passa por `status_light.render_status()`.
2. **As cores moram no tema.** `theme.py` é a fonte única: o TCSS recebe as mesmas
   cores como variáveis `$aw-*` e quem desenha com Rich resolve a cor **na hora de
   renderizar** (`colors().cyan`), nunca no import — é isso que deixa trocar de
   tema com o app rodando.
3. **A UI só lê do store.** Os widgets reagem a dois reativos do app — `tick`
   (animação) e `version` (dados mudaram) — e nunca mexem no modelo.

## Testes

```bash
pip install -e ".[dev]"
pytest
```

24 testes headless (sem terminal real, **sem tocar áudio** e sem ler nem escrever
a sua config — `tests/conftest.py` neutraliza o player e aponta o `XDG_CONFIG_HOME`
para um diretório temporário). Cobrem breakpoints e navegação, troca de
visão/painel/modais, mapeamento do semáforo e o piscar do INPUT, as regras do bip
(dispara, silencia, debounce, máquina sem player), o layout sem vão morto, a
garantia de que o EVENT STREAM nunca é empurrado para fora da tela e os temas
(preview, cancelamento, persistência, e a checagem de que toda paleta fornece
cada variável `$aw-*` que o TCSS usa — uma faltando derruba a tela inteira).

CI no GitHub Actions cobrindo Python 3.10, 3.11, 3.12, 3.13 e 3.14.

## Roadmap

A UI só lê de `SessionStore` e reage a `tick` e `version`. Para trocar o mock por
dados reais:

1. um *provider* que descubra/atualize `Session` e chame `store.transition(...)` /
   `store.log(...)`;
2. incrementar `app.version` a cada mudança (é o que também dispara o bip);
3. remover `MockSimulator` do `WatchAIApp`.

Nenhum widget precisa mudar.

## Licença

[MIT](LICENSE) © Leandro Dukievicz
