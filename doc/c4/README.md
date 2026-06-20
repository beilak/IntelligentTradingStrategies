# C4 diagrams

The current C4 source of truth is the D2 files in this directory tree.
The older PlantUML and PNG files are kept as historical artifacts.

Diagram labels are intentionally written in Russian and kept short for readability.
The text in parentheses explains the role of a node.
Diagram text is rendered in Times New Roman with solid black color.

The diagrams are based on:

- `docker-compose.yml`
- `infra/nginx/nginx.conf`
- FastAPI entrypoints under `services/*/app/main.py` and `its/services/*/app/main.py`
- shared runtime modules under `its/authz`, `its/event_log`, `its/observability`, `its/db`, `its/data_loader`, `its/strategies`, `its/ga`, and `its/execution`

Included levels:

- Level 1: System Context - `1_system_context_diagram/1_context.d2`
- Level 2: Current Container View - `2_container_diagram/2_container.d2`
- Level 2: Target Container View - `2_container_diagram/2_target_container.d2`
- Level 3: Backend Component View - `3_component_diagram/3_backend_components.d2`

Modeling notes:

- Every `docker-compose.yml` service is treated as an independent microservice.
- The local Docker Compose deployment is a dev/test topology where services run on one machine.
- Local volumes and local model files are temporary implementation details.
- In the target architecture, persistent state is stored in PostgreSQL-backed service stores.
- Class/code-level C4 diagrams are intentionally not included.

Recommended render settings:

- Use SVG for review.
- Render with a scale large enough for text review.
- Use Times New Roman font files when rendering SVG.

Render examples:

```bash
d2 --layout=elk --font-regular "/System/Library/Fonts/Supplemental/Times New Roman.ttf" --font-italic "/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf" --font-bold "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf" --font-semibold "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf" doc/c4/1_system_context_diagram/1_context.d2 doc/c4/1_system_context_diagram/1_context.svg

d2 --layout=elk --font-regular "/System/Library/Fonts/Supplemental/Times New Roman.ttf" --font-italic "/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf" --font-bold "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf" --font-semibold "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf" doc/c4/2_container_diagram/2_container.d2 doc/c4/2_container_diagram/2_container.svg

```
