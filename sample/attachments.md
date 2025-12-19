---
title: "Images and documents"
alignment: left
---

![PNG image with caption](figure/interoperability.png)

Prefer PNG over SVG if both are available in the same directory:

![SVG image with caption](figure/interoperability.svg)

Extracted editable draw.io diagram with `render_drawio=False`, uploaded PNG image with `render_drawio=True`:

![Embedded draw.io image](figure/diagram.drawio.png)

Editable draw.io diagram with `render_drawio=False`, static image with `render_drawio=True`:

![Editable or rendered draw.io image](figure/diagram.drawio)

Editable Mermaid diagram with `render_mermaid=False`, static image with `render_mermaid=True`:

![Editable or rendered Mermaid diagram](figure/class.mmd)

Static image hosted at an external location:

![External image](http://confluence.atlassian.com/images/logo/confluence_48_trans.png)

Code block that produces an editable Mermaid diagram with `render_mermaid=False`, or a static image with `render_mermaid=True`:

```mermaid
classDiagram
Entity <|-- Product
Entity <|-- Customer
Entity <|-- Vendor
Vendor <|-- Store
Entity <|-- Project
```

[PDF document](docs/sample.pdf)

[Word processor document](docs/sample.docx)

[Spreadsheet document](docs/sample.xlsx)

[LibreOffice Writer document](docs/sample.odt)

[LibreOffice Calc document](docs/sample.ods)
