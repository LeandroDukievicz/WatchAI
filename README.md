<div align="center">

<img src="docs/brand/watchai.png" alt="WatchAI" width="620">

**Monitor de sessões de IA no terminal.**
Claude Code, Codex, Gemini, OpenCode, Aider, Copilot — todas numa tela só.

[![tests](https://github.com/LeandroDukievicz/WatchAI/actions/workflows/tests.yml/badge.svg)](https://github.com/LeandroDukievicz/WatchAI/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
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

### Teclas

| Tecla | Ação |
|---|---|
| `↑ ↓` (`k j`) | seleciona sessão (nas colunas do grid, move uma linha) |
| `← →` (`h l`) | navega entre cards da mesma linha |
| `ENTER` | detalhes da sessão (dentro: `← →` troca de sessão) |
| `ESC` | volta / fecha modal |
| `TAB` | alterna painel **SESSIONS ⇄ EVENTS** (em EVENTS, `↑ ↓` rolam o histórico) |
| `V` | alterna **CARDS ⇄ LIST** |
| `R` | refresh — no protótipo, avança a simulação na hora |
| `B` | liga/desliga o bip de READY |
| `?` | ajuda |
| `Q` | sai |

Mouse: clique seleciona, duplo clique abre os detalhes.

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
escuro da própria cor. OFFLINE apaga as três e escurece a carcaça. Abaixo de 60
colunas o semáforo sai (não cabe) e quem dá o estado é a barra lateral colorida.

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

O contador `for 01:42` no card = há quanto tempo a sessão está **neste** estado.
Em READY/INPUT/ERROR ele fica em negrito depois de 1 minuto ("terminou e você
ainda não voltou").

Regra de ouro da paleta: neon só em status, título, seleção e teclas. O resto é
branco suave e cinza.

## Responsividade

| Largura | Layout |
|---|---|
| ≥ 130 | 3 cards por linha |
| 90–129 | 2 cards por linha |
| 60–89 | 1 card por linha |
| < 60 | compacto: sem caixa, barra lateral na cor do estado, 4 linhas por sessão (sem semáforo) |

Textos longos truncam com `…` (nunca quebram). `V` (LIST) é a visão mais densa.

Na vertical não há vão morto: a área de sessões encolhe até o conteúdo e o EVENT
STREAM ocupa tudo que sobra — quanto mais alto o terminal, mais histórico. Se as
sessões não couberem, a área rola em vez de empurrar o stream para fora: o stream
nunca fica com menos que suas 6 linhas, e header e keybar ficam sempre visíveis.

## Arquitetura

```
WatchAI/
├── main.py                      # entrada: python main.py
├── pyproject.toml               # pacote, deps e config do pytest
├── src/watchai/
│   ├── app.py                   # App: tema, tick (0,5 s), bindings, bip de READY
│   ├── theme.py                 # paleta + Theme (variáveis $aw-* para o TCSS)
│   ├── layout.py                # breakpoints (LARGE/MEDIUM/SMALL/TINY) + teto da área
│   ├── format.py                # ellipsize, HH:MM:SS, mm:ss
│   ├── sound.py                 # bip (descobre o player do sistema)
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
│   ├── screens/                 # dashboard.py · details.py · help.py
│   └── styles/app.tcss          # todo o CSS
├── tests/                       # suíte headless (conftest silencia o áudio)
└── docs/                        # marca e screenshot
```

Três regras que o código segue:

1. **O estado mora no enum.** `Status` carrega label, cor, símbolo e prioridade de
   atenção. Nenhum widget hardcoda cor ou símbolo de estado — todos consultam o enum,
   e todo desenho de estado passa por `status_light.render_status()`.
2. **As cores moram no tema.** `theme.py` é a fonte única: o TCSS recebe as mesmas
   cores como variáveis `$aw-*` e os widgets que desenham com Rich importam as
   constantes de lá.
3. **A UI só lê do store.** Os widgets reagem a dois reativos do app — `tick`
   (animação) e `version` (dados mudaram) — e nunca mexem no modelo.

## Testes

```bash
pip install -e ".[dev]"
pytest
```

17 testes headless (sem terminal real e **sem tocar áudio** — `tests/conftest.py`
neutraliza o player para toda a suíte). Cobrem breakpoints e navegação,
troca de visão/painel/modais, mapeamento do semáforo e o piscar do INPUT, as
regras do bip (dispara, silencia, debounce, máquina sem player), o layout sem vão
morto e a garantia de que o EVENT STREAM nunca é empurrado para fora da tela.

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
