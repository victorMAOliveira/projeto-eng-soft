# eh_ui

Componente de apresentação do EstágioHub: macros Jinja reutilizáveis (cards,
tabelas, *badge* de serviço, alertas...), filtros de formatação pt-BR e a
folha de estilos `eh_ui.css`. É o que permite à interface mostrar, em cada
painel, qual microsserviço forneceu os dados.

## Interface fornecida

| Símbolo | Tipo | Descrição |
|---|---|---|
| `templates_dir()` | função | Pasta a registrar no *loader* Jinja; macros em `eh_ui/macros.html`. |
| `static_dir()` | função | Pasta com `eh_ui.css`. |
| `register_filters(env)` | função | Instala os filtros abaixo e a global `EH_SERVICES`. |
| `SERVICES`, `ServiceMeta` | dados | Rótulo, cor, descrição e banco de cada microsserviço. |
| `service_color`, `service_label` | funções/filtros | Cor e rótulo do serviço. |
| `status_label`, `modality_label`, `brl`, `date_br`, `datetime_br`, `pct` | funções/filtros | Formatação pt-BR. |

Macros (`{% import "eh_ui/macros.html" as ui %}`):

| Macro | Uso |
|---|---|
| `ui.card(title, service, subtitle, id, classes, actions)` | Painel com *badge* do serviço; usar com `{% call %}`. |
| `ui.service_badge(service)` | *Badge* discreto com o nome do serviço (lido de `X-Served-By`). |
| `ui.table(headers, rows, empty)` | Tabela responsiva com estado vazio. |
| `ui.alert(message, kind, title)` | Alerta `info`, `success`, `warning` ou `error`. |
| `ui.status_pill(status)` | Selo colorido do status (candidatura, vaga, serviço). |
| `ui.score_bar(score, label)` | Barra de *score* 0..1 (recomendação). |
| `ui.stat(label, value, service, hint)` | Indicador numérico do dashboard. |
| `ui.service_card(name, status, detail)` | Card de legenda / status de microsserviço. |
| `ui.empty_state(message, hint)` | Mensagem de lista vazia. |

## Interface requerida

- `Jinja2 >= 3.1`. O CSS usa `color-mix()` (navegadores atuais).

## Exemplo de uso

```python
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
import eh_ui

templates = Jinja2Templates(directory="templates")
templates.env.loader = ChoiceLoader([templates.env.loader, FileSystemLoader(eh_ui.templates_dir())])
eh_ui.register_filters(templates.env)
```

```jinja
{% import "eh_ui/macros.html" as ui %}
{% call ui.card("Vagas recomendadas", service=served_by) %} ... {% endcall %}
```

## Serviços que reutilizam

`web-frontend`.
